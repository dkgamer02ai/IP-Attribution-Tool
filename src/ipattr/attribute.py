"""Attribution orchestrator. Priority: DNS > Netblock > Censys."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from ._console import progress_console
from .censys import CensysLookup, CensysResult
from .dns_check import resolve_many
from .parse import IPRow

log = logging.getLogger(__name__)


@dataclass
class Attribution:
    ip: str
    method: str  # "DNS" | "Netblock" | "Censys" | "Unknown"
    confirmed: bool
    evidence: str = ""
    dns_hits: list[str] = field(default_factory=list)
    censys_hits: list[str] = field(default_factory=list)
    censys_source: str = ""  # "scrape" | "api" | ""
    error: str = ""


async def _attribute_row(
    row: IPRow,
    censys: CensysLookup,
    dns_concurrency: int,
) -> Attribution:
    log.info("Processing [bold]%s[/bold]", row.ip)

    if row.has_dns:
        n = len(row.dns_hostnames)
        log.info("  %s → DNS (%d hostname%s)", row.ip, n, "s" if n != 1 else "")
        log.debug("  %s → DNS hostnames: %s", row.ip, row.dns_hostnames)
        dns_results = await resolve_many(row.dns_hostnames, concurrency=dns_concurrency)
        hits = [d.hostname for d in dns_results if d.confirmed]
        if hits:
            evidence_parts = [
                f"{d.hostname} -> {','.join(d.addresses)}"
                for d in dns_results
                if d.confirmed
            ]
            log.info("  %s → [green]✓ DNS[/green] confirmed (%d hit(s))", row.ip, len(hits))
            return Attribution(
                ip=row.ip,
                method="DNS",
                confirmed=True,
                evidence="; ".join(evidence_parts)[:500],
                dns_hits=hits,
            )
        log.debug("  %s → DNS no match", row.ip)

    if row.has_netblock and not row.has_keyword:
        log.info("  %s → [yellow]Netblock[/yellow] (skipped, no keyword)", row.ip)
        return Attribution(
            ip=row.ip,
            method="Netblock",
            confirmed=False,
            evidence="netblock present, skipped",
        )

    if row.has_keyword:
        log.info("  %s → Censys keywords: %s", row.ip, row.keywords)
        cres: CensysResult = await censys.lookup(row.ip, row.keywords)
        if cres.confirmed:
            log.info("  %s → [cyan]✓ Censys[/cyan] confirmed (source=%s)", row.ip, cres.source)
        else:
            log.debug("  %s → Censys no match (source=%s error=%s)", row.ip, cres.source, cres.error)
        return Attribution(
            ip=row.ip,
            method="Censys" if cres.confirmed else "Unknown",
            confirmed=cres.confirmed,
            evidence=cres.evidence or (cres.error or ""),
            censys_hits=cres.matched_keywords,
            censys_source=cres.source if cres.confirmed else "",
            error=cres.error or "",
        )

    log.debug("  %s → Unknown (no method matched)", row.ip)
    return Attribution(ip=row.ip, method="Unknown", confirmed=False)


async def run_attribution(
    rows: list[IPRow],
    *,
    dns_concurrency: int = 50,
    censys_concurrency: int = 8,
    show_progress: bool = True,
) -> list[Attribution]:
    async with CensysLookup(concurrency=censys_concurrency) as censys:
        if show_progress:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                TextColumn("[dim]{task.percentage:>3.0f}%[/dim]"),
                TimeElapsedColumn(),
                TextColumn("[dim]ETA[/dim]"),
                TimeRemainingColumn(),
                console=progress_console,
                transient=False,
            ) as progress:
                task_id = progress.add_task("[cyan]Attributing IPs...", total=len(rows))

                async def _wrap(row: IPRow) -> Attribution:
                    result = await _attribute_row(row, censys, dns_concurrency)
                    progress.advance(task_id)
                    return result

                results = await asyncio.gather(*[_wrap(r) for r in rows])
        else:
            tasks = [_attribute_row(r, censys, dns_concurrency) for r in rows]
            results = await asyncio.gather(*tasks)

    return list(results)
