#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from itertools import combinations
from pathlib import Path

from validate_agents import SCORE_AXES, SELECTION_AXES, validate_file


def quartiles(values: list[int]) -> dict[str, float | int]:
    ordered = sorted(values)
    return {
        "min": ordered[0],
        "mean": round(statistics.fmean(ordered), 2),
        "median": statistics.median(ordered),
        "max": ordered[-1],
        "distinct": len(set(ordered)),
    }


def audit_file(path: Path) -> dict:
    errors = validate_file(path)
    if errors:
        return {"file": path.name, "valid": False, "errors": errors}
    payload = json.loads(path.read_text())
    sets = {axis: set(payload["axes"][axis]) for axis in SELECTION_AXES}
    union = set().union(*sets.values())
    pairwise = {}
    identical_pairs = []
    for left, right in combinations(SELECTION_AXES, 2):
        intersection = len(sets[left] & sets[right])
        pairwise[f"{left}__{right}"] = {
            "intersection": intersection,
            "jaccard": round(intersection / len(sets[left] | sets[right]), 3),
        }
        if sets[left] == sets[right]:
            identical_pairs.append([left, right])
    unique_to_axis = {
        axis: len(sets[axis] - set().union(*(sets[other] for other in SELECTION_AXES if other != axis)))
        for axis in SELECTION_AXES
    }
    works = payload["works"]
    medium_counts = Counter(work["medium"] for work in works)
    era_counts = Counter(
        "pre_1950" if work["year"] < 1950
        else "1950_1979" if work["year"] < 1980
        else "1980_2009" if work["year"] < 2010
        else "2010_present"
        for work in works
    )
    return {
        "file": path.name,
        "agent_id": payload["agent_id"],
        "valid": True,
        "work_records": len(works),
        "union_size": len(union),
        "union_matches_works": union == {work["work_id"] for work in works},
        "identical_axis_pairs": identical_pairs,
        "pairwise_overlap": pairwise,
        "unique_to_axis": unique_to_axis,
        "score_distributions": {
            axis: quartiles([work["scores"][axis] for work in works])
            for axis in SCORE_AXES
        },
        "medium_counts": dict(sorted(medium_counts.items())),
        "era_counts": dict(sorted(era_counts.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", type=Path, nargs="+")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = {"agents": [audit_file(path) for path in args.files]}
    result["pilot_passes_structural_checks"] = all(
        item.get("valid")
        and item.get("union_matches_works")
        and not item.get("identical_axis_pairs")
        for item in result["agents"]
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    print(rendered, end="")
    return 0 if result["pilot_passes_structural_checks"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
