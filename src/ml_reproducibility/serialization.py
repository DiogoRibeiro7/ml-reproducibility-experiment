"""Deterministic, platform-independent serialisation of scientific artifacts.

Every scientific output must have identical bytes regardless of the operating system
that produced it. Python text mode translates ``\\n`` into ``os.linesep`` on write, and
:meth:`pandas.DataFrame.to_csv` defaults to the same platform newline. Artifacts written
on Windows would therefore differ from the canonical Linux bytes and fail the release
gate on line endings alone, even when every scientific value is identical.

All scientific writes go through this module so that the byte representation is a
property of the experiment rather than of the machine that ran it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

import pandas as pd

LINE_TERMINATOR: Final[str] = "\n"
CSV_FLOAT_FORMAT: Final[str] = "%.12g"


def canonical_json_bytes(payload: Any) -> bytes:
    """Return deterministic JSON bytes with sorted keys and LF newlines."""

    return json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")


def write_json(destination: Path, payload: Any) -> None:
    """Write deterministic JSON bytes, bypassing platform newline translation."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(canonical_json_bytes(payload))


def write_text(destination: Path, text: str) -> None:
    """Write UTF-8 text with LF newlines on every platform."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(text.encode("utf-8"))


def write_csv(frame: pd.DataFrame, destination: Path) -> None:
    """Write a result table using the canonical CSV byte representation."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(
        destination,
        index=False,
        float_format=CSV_FLOAT_FORMAT,
        lineterminator=LINE_TERMINATOR,
    )
