"""Async DNS resolution for hostname attribution."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import dns.asyncresolver
import dns.exception

log = logging.getLogger(__name__)


@dataclass
class DNSResult:
    hostname: str
    addresses: list[str]
    confirmed: bool
    error: str | None = None


_resolver: dns.asyncresolver.Resolver | None = None


def _get_resolver() -> dns.asyncresolver.Resolver:
    global _resolver
    if _resolver is None:
        r = dns.asyncresolver.Resolver()
        r.timeout = 5.0
        r.lifetime = 8.0
        _resolver = r
    return _resolver


async def resolve_one(hostname: str, sem: asyncio.Semaphore) -> DNSResult:
    async with sem:
        addrs: list[str] = []
        err: str | None = None
        resolver = _get_resolver()
        log.debug("DNS resolve: %s", hostname)
        for rdtype in ("A", "AAAA"):
            try:
                ans = await resolver.resolve(hostname, rdtype, raise_on_no_answer=False)
                if ans.rrset is not None:
                    addrs.extend(r.address for r in ans)
            except (dns.exception.DNSException, asyncio.TimeoutError) as e:
                err = f"{type(e).__name__}: {e}"
        result = DNSResult(
            hostname=hostname,
            addresses=addrs,
            confirmed=bool(addrs),
            error=err if not addrs else None,
        )
        if result.confirmed:
            log.debug("DNS %s → [%s]", hostname, ", ".join(addrs))
        else:
            log.debug("DNS %s → no result (err=%s)", hostname, err)
        return result


async def resolve_many(hostnames: list[str], concurrency: int = 50) -> list[DNSResult]:
    sem = asyncio.Semaphore(concurrency)
    return await asyncio.gather(*(resolve_one(h, sem) for h in hostnames))
