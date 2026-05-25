"""CSV parsing and source classification."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class IPRow:
    ip: str
    raw_source: str
    dns_hostnames: list[str] = field(default_factory=list)
    netblocks: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)

    @property
    def has_dns(self) -> bool:
        return bool(self.dns_hostnames)

    @property
    def has_netblock(self) -> bool:
        return bool(self.netblocks)

    @property
    def has_keyword(self) -> bool:
        return bool(self.keywords)


def classify_entry(entry: str) -> tuple[str, str]:
    """Classify a single source entry. Returns (type, value)."""
    entry = entry.strip()
    if entry.startswith("DNS-"):
        return ("dns", entry[4:].strip())
    if entry.startswith("Netblock-"):
        return ("netblock", entry[9:].strip())
    return ("keyword", entry)


def parse_row(ip: str, source: str) -> IPRow:
    row = IPRow(ip=ip.strip(), raw_source=source)
    if not source:
        return row
    parts = [p.strip() for p in source.split(",") if p.strip()]
    for part in parts:
        kind, value = classify_entry(part)
        if not value:
            continue
        if kind == "dns":
            row.dns_hostnames.append(value)
        elif kind == "netblock":
            row.netblocks.append(value)
        else:
            row.keywords.append(value)
    return row


def read_csv(path: Path) -> list[IPRow]:
    rows: list[IPRow] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return rows
        ip_key = next((k for k in reader.fieldnames if "ip" in k.lower()), reader.fieldnames[0])
        src_key = next((k for k in reader.fieldnames if "source" in k.lower()), reader.fieldnames[-1])
        for r in reader:
            ip = r.get(ip_key, "").strip()
            src = r.get(src_key, "") or ""
            if not ip:
                continue
            rows.append(parse_row(ip, src))
    return rows
