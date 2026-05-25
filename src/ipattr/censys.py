"""Censys keyword attribution: webpage scrape primary, API v2 fallback."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

SCRAPE_URL = "https://search.censys.io/hosts/{ip}"
API_URL = "https://search.censys.io/api/v2/hosts/{ip}"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


@dataclass
class CensysResult:
    ip: str
    matched_keywords: list[str] = field(default_factory=list)
    source: str = "none"  # "scrape" | "api" | "none"
    confirmed: bool = False
    error: str | None = None
    evidence: str = ""  # short snippet


def _match_keywords(haystack: str, keywords: list[str]) -> tuple[list[str], str]:
    text = haystack.lower()
    hits: list[str] = []
    snippet = ""
    for kw in keywords:
        k = kw.lower().strip()
        if not k:
            continue
        idx = text.find(k)
        if idx >= 0:
            hits.append(kw)
            if not snippet:
                start = max(0, idx - 40)
                end = min(len(haystack), idx + len(kw) + 40)
                snippet = haystack[start:end].replace("\n", " ").strip()
    return hits, snippet


async def scrape_host(client: httpx.AsyncClient, ip: str, keywords: list[str]) -> CensysResult:
    res = CensysResult(ip=ip, source="scrape")
    log.debug("%s → Censys scrape", ip)
    try:
        r = await client.get(
            SCRAPE_URL.format(ip=ip),
            headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
            follow_redirects=True,
            timeout=20.0,
        )
        log.debug("%s → Censys scrape HTTP %s", ip, r.status_code)
        if r.status_code != 200:
            res.error = f"HTTP {r.status_code}"
            return res
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(" ", strip=True)
        hits, snippet = _match_keywords(text, keywords)
        res.matched_keywords = hits
        res.confirmed = bool(hits)
        res.evidence = snippet
        log.debug("%s → Censys scrape hits=%s", ip, hits)
    except httpx.HTTPError as e:
        res.error = f"{type(e).__name__}: {e}"
        log.debug("%s → Censys scrape error: %s", ip, res.error)
    return res


async def api_host(
    client: httpx.AsyncClient,
    ip: str,
    keywords: list[str],
    auth: tuple[str, str],
) -> CensysResult:
    res = CensysResult(ip=ip, source="api")
    log.debug("%s → Censys API", ip)
    try:
        r = await client.get(
            API_URL.format(ip=ip),
            headers={"Accept": "application/json"},
            auth=auth,
            timeout=20.0,
        )
        log.debug("%s → Censys API HTTP %s", ip, r.status_code)
        if r.status_code != 200:
            res.error = f"HTTP {r.status_code}"
            return res
        data = r.json()
        text = json.dumps(data, ensure_ascii=False)
        hits, snippet = _match_keywords(text, keywords)
        res.matched_keywords = hits
        res.confirmed = bool(hits)
        res.evidence = snippet
        log.debug("%s → Censys API hits=%s", ip, hits)
    except (httpx.HTTPError, ValueError) as e:
        res.error = f"{type(e).__name__}: {e}"
        log.debug("%s → Censys API error: %s", ip, res.error)
    return res


class CensysLookup:
    def __init__(self, concurrency: int = 8) -> None:
        self._sem = asyncio.Semaphore(concurrency)
        self._client: httpx.AsyncClient | None = None
        api_id = os.getenv("CENSYS_API_ID", "").strip()
        api_secret = os.getenv("CENSYS_API_SECRET", "").strip()
        self._auth: tuple[str, str] | None = (api_id, api_secret) if api_id and api_secret else None

    async def __aenter__(self) -> "CensysLookup":
        limits = httpx.Limits(max_connections=64, max_keepalive_connections=16)
        self._client = httpx.AsyncClient(limits=limits, http2=False)
        return self

    async def __aexit__(self, *exc) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def lookup(self, ip: str, keywords: list[str]) -> CensysResult:
        assert self._client is not None, "use as async context manager"
        if not keywords:
            return CensysResult(ip=ip, source="none", error="no keywords")
        async with self._sem:
            scrape = await scrape_host(self._client, ip, keywords)
            if scrape.confirmed:
                return scrape
            if self._auth is None:
                if scrape.error is None and not scrape.confirmed:
                    return scrape  # scrape worked, just no match
                return scrape
            api = await api_host(self._client, ip, keywords, self._auth)
            if api.confirmed:
                return api
            return api if api.error is None else scrape
