# IP Attribution Tool

Attribute IPs from a CSV using DNS, Netblock, or Censys keyword lookup.

## Input format

CSV with two columns:

```
ip_address,source
```

`source` is a comma-separated list of entries. Each entry is one of:

- `DNS-<hostname>` — resolve hostname; if any A/AAAA returned, attribution is confirmed.
- `Netblock-<cidr>` — currently skipped.
- `<keyword>` (no prefix) — Censys host page is scraped; keyword matched against any field. Falls back to the Censys v2 host API if credentials are set in `.env`.

Priority when multiple kinds exist for one IP: **DNS > Netblock > Censys**. First confirmed method wins.

## Setup

```bash
uv sync
cp .env.example .env  # optional, only needed for Censys API fallback
```

## Run

```bash
uv run main.py input/test_ip_set_1.csv -o output/attribution.csv
```

Useful flags:

- `--limit N` — process only first N rows
- `--dns-concurrency 50` — parallel DNS lookups
- `--censys-concurrency 8` — parallel Censys requests
- `--no-progress` — disable progress bar

Output CSV columns: `ip, method, confirmed, censys_source, dns_hits, censys_hits, evidence, error`.
