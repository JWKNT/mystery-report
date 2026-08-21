#!/usr/bin/env python3
"""Refresh v3 singleton metadata while preserving its verification evidence."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
AUDIT_DIR = BASE_DIR.parent.parent / "data" / "v3" / "audit"


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(character for character in value if not unicodedata.combining(character))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.casefold())).strip()


def work_key(work: dict[str, object]) -> tuple[str, str, int, str]:
    return (
        normalized(str(work["title"])),
        normalized(str(work["creator"])),
        int(work["year"]),
        str(work["medium"]),
    )


def refresh(path: Path, works: list[dict[str, object]]) -> None:
    records = json.loads(path.read_text())
    records_by_key = {work_key(record["work"]): record for record in records}
    work_keys = {work_key(work) for work in works}
    if set(records_by_key) != work_keys:
        missing = work_keys - set(records_by_key)
        stale = set(records_by_key) - work_keys
        raise RuntimeError(f"Verification keys changed: missing={missing}, stale={stale}")

    refreshed = []
    for work in works:
        record = records_by_key[work_key(work)]
        updated = dict(record)
        updated["work"] = work
        refreshed.append(updated)
    path.write_text(json.dumps(refreshed, ensure_ascii=False, indent=2) + "\n")


def main() -> None:
    works = json.loads((AUDIT_DIR / "singletons.json").read_text())
    refresh(AUDIT_DIR / "singleton-verification.json", works)
    refresh(AUDIT_DIR / "singleton-verification-final.json", works)


if __name__ == "__main__":
    main()
