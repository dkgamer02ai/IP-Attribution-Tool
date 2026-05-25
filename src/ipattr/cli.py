"""Command-line interface."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import argparse
from dotenv import load_dotenv

from .attribute import run_attribution
from .logging_setup import setup_logging
from .output import display_table, write_csv
from .parse import read_csv

log = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="ip-attribution",
        description="Attribute IPs via DNS, Netblock, or Censys keyword lookup.",
    )
    p.add_argument(
        "-i", "--input", required=True, type=Path,
        help="Input CSV (ip_address,source).",
    )
    p.add_argument(
        "-o", "--output", type=Path, default=Path("output/attribution.csv"),
        help="Output CSV path (default: output/attribution.csv).",
    )
    p.add_argument(
        "--debug", action="store_true",
        help="Enable DEBUG logging and save full log to file.",
    )
    p.add_argument(
        "--log-file", type=Path, default=None, metavar="PATH",
        help="Log file path (debug only; default: logs/attribution_<timestamp>.log).",
    )
    p.add_argument("--dns-concurrency", type=int, default=50)
    p.add_argument("--censys-concurrency", type=int, default=8)
    p.add_argument(
        "--limit", type=int, default=0,
        help="Process only first N rows (0 = all).",
    )
    p.add_argument("--no-progress", action="store_true", help="Disable progress bar.")
    return p.parse_args(argv)


async def _run(args: argparse.Namespace) -> int:
    log_file = setup_logging(debug=args.debug, log_file=args.log_file)

    if args.debug and log_file:
        log.info("Debug log: [bold]%s[/bold]", log_file)

    rows = read_csv(args.input)
    if args.limit > 0:
        rows = rows[: args.limit]
    if not rows:
        print(f"No rows in {args.input}", file=sys.stderr)
        return 1

    log.info("Loaded [bold]%d[/bold] IPs from %s", len(rows), args.input)

    results = await run_attribution(
        rows,
        dns_concurrency=args.dns_concurrency,
        censys_concurrency=args.censys_concurrency,
        show_progress=not args.no_progress,
    )

    write_csv(args.output, results)
    display_table(results, args.output)
    return 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
