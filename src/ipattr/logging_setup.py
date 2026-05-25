from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from rich.logging import RichHandler

from ._console import progress_console


def setup_logging(debug: bool = False, log_file: Path | None = None) -> Path | None:
    if debug and log_file is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = Path(f"logs/attribution_{ts}.log")

    rich_handler = RichHandler(
        console=progress_console,
        show_path=False,
        rich_tracebacks=True,
        markup=True,
        log_time_format="[%X]",
    )
    rich_handler.setLevel(logging.DEBUG if debug else logging.INFO)

    handlers: list[logging.Handler] = [rich_handler]

    if debug and log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s  %(levelname)-8s  %(name)s  %(message)s")
        )
        handlers.append(file_handler)

    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=handlers,
        force=True,
    )

    return log_file
