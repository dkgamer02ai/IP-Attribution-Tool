from __future__ import annotations

import csv
from pathlib import Path

from rich import box
from rich.panel import Panel
from rich.table import Table

from ._console import out_console
from .attribute import Attribution

OUTPUT_FIELDS = [
    "ip",
    "method",
    "confirmed",
    "censys_source",
    "dns_hits",
    "censys_hits",
    "evidence",
    "error",
]

_METHOD_STYLE: dict[str, str] = {
    "DNS": "[bold green]DNS[/bold green]",
    "Censys": "[bold cyan]Censys[/bold cyan]",
    "Netblock": "[bold yellow]Netblock[/bold yellow]",
    "Unknown": "[dim white]Unknown[/dim white]",
}


def write_csv(path: Path, results: list[Attribution]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        w.writeheader()
        for r in results:
            w.writerow(
                {
                    "ip": r.ip,
                    "method": r.method,
                    "confirmed": "true" if r.confirmed else "false",
                    "censys_source": r.censys_source,
                    "dns_hits": ";".join(r.dns_hits),
                    "censys_hits": ";".join(r.censys_hits),
                    "evidence": r.evidence,
                    "error": r.error,
                }
            )


def display_table(results: list[Attribution], output_path: Path) -> None:
    table = Table(
        title="[bold bright_white]IP Attribution Results[/bold bright_white]",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold white on dark_blue",
        border_style="bright_blue",
        row_styles=["on grey7", ""],
        highlight=False,
        expand=False,
    )

    table.add_column("IP Address", style="bold white", no_wrap=True, min_width=17)
    table.add_column("Method", justify="center", min_width=9)
    table.add_column("OK", justify="center", width=4)
    table.add_column("DNS Hits", overflow="fold", max_width=38)
    table.add_column("Censys", justify="center", width=9)
    table.add_column("Evidence", overflow="fold", max_width=42)
    table.add_column("Error", style="red", overflow="fold", max_width=22)

    confirmed_count = 0
    method_counts: dict[str, int] = {}

    for r in results:
        if r.confirmed:
            confirmed_count += 1
        method_counts[r.method] = method_counts.get(r.method, 0) + 1

        ok = "[bold green]✓[/bold green]" if r.confirmed else "[red]✗[/red]"
        method = _METHOD_STYLE.get(r.method, r.method)
        if not r.dns_hits:
            dns = "[dim]-[/dim]"
        elif len(r.dns_hits) <= 2:
            dns = "; ".join(r.dns_hits)
        else:
            dns = f"{'; '.join(r.dns_hits[:2])} [dim](+{len(r.dns_hits) - 2} more)[/dim]"
        censys_src = f"[cyan]{r.censys_source}[/cyan]" if r.censys_source else "[dim]-[/dim]"
        ev = r.evidence
        evidence = (ev[:59] + "…") if len(ev) > 60 else (ev or "[dim]-[/dim]")
        error = r.error or ""

        table.add_row(r.ip, method, ok, dns, censys_src, evidence, error)

    out_console.print()
    out_console.print(table)

    total = len(results)
    unconfirmed = total - confirmed_count
    method_parts = "  ".join(
        f"{_METHOD_STYLE.get(k, k)} [dim]{v}[/dim]"
        for k, v in sorted(method_counts.items())
    )

    summary = (
        f"[bold]Total[/bold] {total}   "
        f"[bold green]Confirmed[/bold green] {confirmed_count}   "
        f"[bold red]Unconfirmed[/bold red] {unconfirmed}   "
        f"[dim]│[/dim]   {method_parts}"
    )
    out_console.print(Panel(summary, border_style="bright_blue", expand=False))
    out_console.print(f"[dim]Output saved:[/dim] [bold bright_white]{output_path}[/bold bright_white]\n")
