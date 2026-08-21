#!/usr/bin/env python3
"""Build the compact static JavaScript payload for the v4 explorer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"
AUDIT_DIR = DATA_DIR / "audit"
DEFAULT_OUTPUT = DATA_DIR / "consensus-data.js"
AXES = ("influence", "ambition", "fairness", "traditionality", "originality")
SELECTION_AXES = ("ambition", "fairness", "traditional_mystery", "originality")
RANK_ADJUSTMENT_AXES = ("ambition", "fairness", "originality")
SELECTION_TO_SCORE_AXIS = {
    "ambition": "ambition",
    "fairness": "fairness",
    "traditional_mystery": "traditionality",
    "originality": "originality",
}
LABELS = {
    "influence": ("Influence", "Influence"),
    "ambition": ("Ambition", "Ambition"),
    "fairness": ("Fairness", "Fairness"),
    "traditionality": ("Traditionality", "Traditionality"),
    "originality": ("Originality", "Originality"),
}
SELECTION_LABELS = {
    "ambition": "Ambition",
    "fairness": "Fairness",
    "traditional_mystery": "Traditional mystery",
    "originality": "Originality",
}


def rounded(value: float | None, digits: int = 6) -> float | None:
    return None if value is None else round(value, digits)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aggregate", type=Path, default=DATA_DIR / "aggregate.json")
    parser.add_argument("--verification", type=Path, default=AUDIT_DIR / "verification-summary.json")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    aggregate = json.loads(args.aggregate.read_text())
    verification = json.loads(args.verification.read_text())
    strings: list[str] = []
    string_ids: dict[str, int] = {}

    def string_id(value: str) -> int:
        if value not in string_ids:
            string_ids[value] = len(strings)
            strings.append(value)
        return string_ids[value]

    works = []
    work_index_by_cluster: dict[int, int] = {}
    for index, work in enumerate(aggregate["works"]):
        work_index_by_cluster[work["cluster_index"]] = index
        works.append([
            work["overall_rank"],
            string_id(work["title"]),
            string_id(work["original_title"]) if work["original_title"] else -1,
            string_id(work["creator"]),
            work["year"],
            string_id(work["medium"]),
            rounded(work["adjusted_composite"]),
            rounded(work["posterior_composite"]),
            rounded(work["raw_composite"]),
            rounded(work["confidence_penalty"]),
            work["support"],
            rounded(work["support_rate"]),
            *[rounded(work["adjusted_scores"][axis]) for axis in AXES],
            *[rounded(work["rank_adjusted_scores"][axis]) for axis in AXES],
            *[rounded(work["raw_scores"][axis]) for axis in AXES],
            *[work["selection_counts"][axis] for axis in SELECTION_AXES],
            *[rounded(work["mean_selection_ranks"][axis]) for axis in SELECTION_AXES],
        ])

    axis_index = {axis: index for index, axis in enumerate(SELECTION_AXES)}
    selections = []
    for selection in aggregate["raw_selections"]:
        work_index = work_index_by_cluster.get(selection["cluster_index"])
        if work_index is None:
            continue
        selections.append([
            selection["agent_number"],
            string_id(selection["agent_id"]),
            axis_index[selection["axis"]],
            selection["rank"],
            string_id(selection["raw_title"]),
            string_id(selection["raw_creator"]),
            selection["raw_year"],
            string_id(selection["raw_medium"]),
            work_index,
            *[selection["scores"][axis] for axis in AXES],
        ])

    payload = {
        "meta": {
            "version": 4,
            "generated": "2026-08-20",
            "agents": aggregate["agent_count"],
            "works": len(works),
            "observations": aggregate["unique_agent_work_observation_count"],
            "selections": len(selections),
            "verified_singletons": verification["retained_singletons"],
            "excluded": verification["excluded_records"],
            "priorStrength": aggregate["method"]["prior_strength"],
            "rankAdjustmentMax": aggregate["method"]["rank_adjustment_max"],
            "lowerBoundZ": aggregate["method"]["lower_bound_z"],
            "globalCompositeSd": rounded(aggregate["method"]["global_composite_sd"]),
        },
        "axes": [
            {
                "key": axis,
                "label": LABELS[axis][0],
                "short": LABELS[axis][1],
                "weight": aggregate["method"]["weights"][axis],
                "selectionAxis": axis in SELECTION_TO_SCORE_AXIS.values(),
                "rankAdjusted": axis in RANK_ADJUSTMENT_AXES,
                "globalMean": rounded(aggregate["method"]["global_axis_means"][axis]),
                "globalRawMean": rounded(aggregate["method"]["global_raw_axis_means"][axis]),
            }
            for axis in AXES
        ],
        "selectionAxes": list(SELECTION_AXES),
        "selectionLists": [
            {
                "key": selection_axis,
                "label": SELECTION_LABELS[selection_axis],
                "scoreAxis": SELECTION_TO_SCORE_AXIS[selection_axis],
                "rankAdjusted": selection_axis in RANK_ADJUSTMENT_AXES,
            }
            for selection_axis in SELECTION_AXES
        ],
        "strings": strings,
        "works": works,
        "selections": selections,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "window.MYSTERY_CONSENSUS_DATASETS=window.MYSTERY_CONSENSUS_DATASETS||{};"
        "window.MYSTERY_CONSENSUS_DATASETS.v4="
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + ";window.MYSTERY_CONSENSUS_DATA=window.MYSTERY_CONSENSUS_DATASETS.v4;\n"
    )
    print(json.dumps(payload["meta"], indent=2))


if __name__ == "__main__":
    main()
