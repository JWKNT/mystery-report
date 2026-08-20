#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Any


SCORE_AXES = ("influence", "ambition", "fairness", "originality")
SELECTION_AXES = ("ambition", "fairness", "originality")
ALLOWED_MEDIA = {
    "novel", "book_series", "novella", "short_story", "film", "tv_series",
    "anime", "cartoon", "comic", "manga", "video_game", "visual_novel",
    "web_serial", "radio_drama", "audio_drama", "stage_play", "podcast",
    "documentary", "other",
}
WORK_KEYS = {"work_id", "title", "original_title", "creator", "year", "medium", "scores"}


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(character for character in value if not unicodedata.combining(character))
    value = value.casefold().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    value = re.sub(r"^(the|a|an)\s+", "", value)
    return re.sub(r"\s+", " ", value)


def validate_file(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        return [f"invalid JSON: {exc}"]

    if not isinstance(payload, dict) or set(payload) != {"agent_id", "works", "axes"}:
        return ["top-level keys must be exactly agent_id, works, and axes"]
    if not isinstance(payload["agent_id"], str) or not payload["agent_id"].strip():
        errors.append("agent_id is missing")

    works = payload.get("works")
    if not isinstance(works, list) or not 100 <= len(works) <= 300:
        errors.append("works must contain between 100 and 300 records")
        works = works if isinstance(works, list) else []

    by_id: dict[str, dict[str, Any]] = {}
    identities: set[tuple[str, str, str]] = set()
    for index, work in enumerate(works, 1):
        label = f"work {index}"
        if not isinstance(work, dict):
            errors.append(f"{label}: not an object")
            continue
        if set(work) != WORK_KEYS:
            errors.append(f"{label}: unexpected or missing fields")
            continue
        work_id = work.get("work_id")
        if not isinstance(work_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,99}", work_id):
            errors.append(f"{label}: invalid work_id")
            continue
        if work_id in by_id:
            errors.append(f"{label}: duplicate work_id {work_id!r}")
        by_id[work_id] = work
        for field in ("title", "creator"):
            if not isinstance(work.get(field), str) or not work[field].strip():
                errors.append(f"{label}: {field} must be a nonempty string")
        if not isinstance(work.get("original_title"), str):
            errors.append(f"{label}: original_title must be a string")
        if type(work.get("year")) is not int or not 1000 <= work["year"] <= 2026:
            errors.append(f"{label}: invalid year")
        if work.get("medium") not in ALLOWED_MEDIA:
            errors.append(f"{label}: invalid medium")
        scores = work.get("scores")
        if not isinstance(scores, dict) or set(scores) != set(SCORE_AXES):
            errors.append(f"{label}: scores must contain exactly the four axes")
        else:
            for axis in SCORE_AXES:
                if type(scores[axis]) is not int or not 0 <= scores[axis] <= 100:
                    errors.append(f"{label}: {axis} score must be an integer from 0 through 100")
        if all(isinstance(work.get(field), str) for field in ("title", "creator", "medium")):
            identity = (normalized(work["title"]), normalized(work["creator"]), work["medium"])
            if identity in identities:
                errors.append(f"{label}: duplicate normalized work identity {work['title']!r}")
            identities.add(identity)

    axes = payload.get("axes")
    if not isinstance(axes, dict) or set(axes) != set(SELECTION_AXES):
        errors.append("axes must contain exactly ambition, fairness, and originality")
        return errors

    referenced: set[str] = set()
    for axis in SELECTION_AXES:
        ranking = axes[axis]
        if not isinstance(ranking, list) or len(ranking) != 100:
            errors.append(f"{axis}: expected exactly 100 work IDs")
            continue
        if len(set(ranking)) != len(ranking):
            errors.append(f"{axis}: duplicate work IDs")
        for rank, work_id in enumerate(ranking, 1):
            if not isinstance(work_id, str) or work_id not in by_id:
                errors.append(f"{axis} rank {rank}: unknown work ID {work_id!r}")
            else:
                referenced.add(work_id)

    unreferenced = sorted(set(by_id) - referenced)
    if unreferenced:
        errors.append(f"unreferenced work records: {', '.join(unreferenced[:10])}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    paths = sorted(args.directory.glob("agent_*.json"), key=lambda path: int(path.stem.split("_")[1]))
    failures = 0
    for path in paths:
        errors = validate_file(path)
        if errors:
            failures += 1
            print(f"FAIL {path.name}: {'; '.join(errors)}")
        else:
            print(f"OK   {path.name}")
    print(f"SUMMARY files={len(paths)} valid={len(paths) - failures} invalid={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
