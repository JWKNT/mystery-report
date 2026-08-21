#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from validate_agents import SCORE_AXES, SELECTION_AXES, normalized, validate_file


ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / "data"
RAW = DATA / "raw_agents"
AUDIT = DATA / "audit"


def main() -> int:
    aggregate = json.loads((DATA / "aggregate.json").read_text())
    verification = json.loads((AUDIT / "singleton-verification-final.json").read_text())
    verification_summary = json.loads((AUDIT / "verification-summary.json").read_text())
    raw_paths = sorted(RAW.glob("agent_*.json"))
    errors: list[str] = []

    invalid_files = {
        path.name: file_errors
        for path in raw_paths
        if (file_errors := validate_file(path))
    }
    if len(raw_paths) != 100:
        errors.append(f"expected 100 raw files, found {len(raw_paths)}")
    if invalid_files:
        errors.append(f"invalid agent files: {sorted(invalid_files)}")

    agent_ids: list[str] = []
    for path in raw_paths:
        payload = json.loads(path.read_text())
        agent_ids.append(payload["agent_id"])
        if set(payload["axes"]) != set(SELECTION_AXES):
            errors.append(f"{path.name}: wrong selection axes")
        if any(len(payload["axes"][axis]) != 100 for axis in SELECTION_AXES):
            errors.append(f"{path.name}: selection list is not length 100")
        for work in payload["works"]:
            scores = work.get("scores", {})
            if set(scores) != set(SCORE_AXES) or any(
                type(scores[axis]) is not int or not 0 <= scores[axis] <= 100
                for axis in SCORE_AXES
            ):
                errors.append(f"{path.name}: malformed score record")
                break
    if len(set(agent_ids)) != 100:
        errors.append("agent IDs are not unique")

    method = aggregate["method"]
    expected_weights = {
        "influence": 0.10,
        "ambition": 0.35,
        "fairness": 0.25,
        "traditionality": 0.10,
        "originality": 0.20,
    }
    if method["weights"] != expected_weights:
        errors.append("aggregate weights differ from the final specification")
    if method["selection_axes"] != list(SELECTION_AXES):
        errors.append("aggregate selection axes differ from the final specification")
    if method.get("rank_adjustment_axes") != ["ambition", "fairness", "originality"]:
        errors.append("aggregate rank-adjustment axes differ from the final specification")
    if method["prior_strength"] != 10:
        errors.append("aggregate prior strength is not ten")
    if method.get("rank_adjustment_max") != 5.0 or method.get("unselected_censored_rank") != 101:
        errors.append("rank adjustment differs from the agreed ±5 / censored-rank-101 method")
    if method.get("lower_bound_z") != 1.645:
        errors.append("consensus ranking is not using the agreed one-sided 95% lower bound")
    if method.get("confidence_support_denominator") != "sqrt(actual agent support)":
        errors.append("confidence penalty is not based on actual support")

    works = aggregate["works"]
    raw_selections = aggregate["raw_selections"]
    identities = [(normalized(w["title"]), normalized(w["creator"]), w["medium"]) for w in works]
    if len(identities) != len(set(identities)):
        errors.append("duplicate normalized canonical work identities remain")
    if any(w["medium"] in {"tv_season", "tv_episode"} for w in works):
        errors.append("TV season or episode canonical rows remain")
    if [w["overall_rank"] for w in works] != list(range(1, len(works) + 1)):
        errors.append("overall ranks are not contiguous")

    observation_scores: dict[tuple[int, int], dict[str, int]] = {}
    observation_ranks: dict[tuple[int, int], dict[str, int]] = defaultdict(dict)
    for row in aggregate["observations"]:
        key = (row["agent_number"], row["cluster_index"])
        if key in observation_scores:
            errors.append("duplicate retained agent-work observation")
        observation_scores[key] = row["scores"]
        observation_ranks[key] = row["ranks"]

    def rank_adjusted(key: tuple[int, int], axis: str) -> float:
        score = observation_scores[key][axis]
        if axis not in {"ambition", "fairness", "originality"}:
            return float(score)
        rank = observation_ranks[key].get(axis, 101)
        return max(0.0, min(100.0, score + 5 * (50.5 - rank) / 49.5))

    global_raw_means = {
        axis: statistics.fmean(scores[axis] for scores in observation_scores.values())
        for axis in SCORE_AXES
    }
    global_means = {
        axis: statistics.fmean(rank_adjusted(key, axis) for key in observation_scores)
        for axis in SCORE_AXES
    }
    observation_composites = [
        sum(expected_weights[axis] * rank_adjusted(key, axis) for axis in SCORE_AXES)
        for key in observation_scores
    ]
    global_composite_sd = statistics.pstdev(observation_composites)
    if any(not math.isclose(global_raw_means[axis], method["global_raw_axis_means"][axis], abs_tol=1e-9) for axis in SCORE_AXES):
        errors.append("global raw axis means do not reproduce from retained observations")
    if any(not math.isclose(global_means[axis], method["global_axis_means"][axis], abs_tol=1e-9) for axis in SCORE_AXES):
        errors.append("global rank-adjusted axis means do not reproduce from retained observations")
    if not math.isclose(global_composite_sd, method["global_composite_sd"], abs_tol=1e-9):
        errors.append("global composite standard deviation does not reproduce")

    keys_by_cluster: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for key in observation_scores:
        keys_by_cluster[key[1]].append(key)
    for work in works:
        support = work["support"]
        if not 1 <= support <= 100:
            errors.append(f"invalid support for {work['title']}")
            break
        keys = keys_by_cluster[work["cluster_index"]]
        for axis in SCORE_AXES:
            expected_raw = statistics.fmean(observation_scores[key][axis] for key in keys)
            expected_rank_adjusted = statistics.fmean(rank_adjusted(key, axis) for key in keys)
            if not math.isclose(expected_raw, work["raw_scores"][axis], abs_tol=1e-9):
                errors.append(f"raw mean mismatch for {work['title']} / {axis}")
                break
            if not math.isclose(expected_rank_adjusted, work["rank_adjusted_scores"][axis], abs_tol=1e-9):
                errors.append(f"rank-adjusted mean mismatch for {work['title']} / {axis}")
                break
            expected_axis = (support * expected_rank_adjusted + 10 * global_means[axis]) / (support + 10)
            if not math.isclose(expected_axis, work["adjusted_scores"][axis], abs_tol=1e-9):
                errors.append(f"adjustment mismatch for {work['title']} / {axis}")
                break
        expected_posterior = sum(expected_weights[axis] * work["adjusted_scores"][axis] for axis in SCORE_AXES)
        expected_penalty = 1.645 * global_composite_sd / math.sqrt(support)
        expected_consensus = expected_posterior - expected_penalty
        if not math.isclose(expected_posterior, work["posterior_composite"], abs_tol=1e-9):
            errors.append(f"posterior composite mismatch for {work['title']}")
            break
        if not math.isclose(expected_penalty, work["confidence_penalty"], abs_tol=1e-9):
            errors.append(f"confidence penalty mismatch for {work['title']}")
            break
        if not math.isclose(expected_consensus, work["adjusted_composite"], abs_tol=1e-9):
            errors.append(f"consensus score mismatch for {work['title']}")
            break

    selection_groups: dict[tuple[int, str], list[int]] = defaultdict(list)
    for row in raw_selections:
        if row["axis"] not in SELECTION_AXES:
            errors.append("invalid raw selection axis")
            break
        selection_groups[(row["agent_number"], row["axis"])].append(row["rank"])
        if any(type(row["scores"][axis]) is not int or not 0 <= row["scores"][axis] <= 100 for axis in SCORE_AXES):
            errors.append("invalid raw selection scores")
            break
    group_lengths = Counter(map(len, selection_groups.values()))
    collected_selections = aggregate.get("collected_raw_selection_count")
    excluded_selections = aggregate.get("excluded_raw_selection_count")
    if collected_selections != 40_000:
        errors.append(f"expected exactly 40000 collected placements, found {collected_selections}")
    if len(raw_selections) != collected_selections - excluded_selections:
        errors.append("retained placement count does not reconcile with audited exclusions")
    if len(selection_groups) != 400 or any(length < 0 or length > 100 for length in group_lengths):
        errors.append(f"unexpected selection group shape: {dict(group_lengths)}")
    if sum(100 - len(ranks) for ranks in selection_groups.values()) != excluded_selections:
        errors.append("missing retained placements do not match the audited exclusion count")
    for key, ranks in selection_groups.items():
        if len(ranks) != len(set(ranks)) or any(not 1 <= rank <= 100 for rank in ranks):
            errors.append(f"selection ranks are invalid or duplicated for {key}")
            break

    if len(verification) != len(aggregate["singletons"]) or any(not row["status"].startswith("verified_") for row in verification):
        errors.append("retained singleton verification is incomplete")
    configured_exclusions = json.loads((AUDIT / "exclusions.json").read_text())
    if verification_summary["unverified_retained"] != 0 or verification_summary["excluded_records"] != len(configured_exclusions):
        errors.append("singleton verification summary is inconsistent")

    excluded_titles = {row["title"] for row in verification_summary["exclusions"]}
    if excluded_titles != {row["title"] for row in configured_exclusions}:
        errors.append("exclusion set differs from the reviewed exclusion set")
    retained_titles = {work["title"] for work in works}
    if excluded_titles & retained_titles:
        errors.append("an excluded canonical title remains in the retained corpus")

    report = {
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "checks": {
            "raw_agent_files": len(raw_paths),
            "valid_agent_files": len(raw_paths) - len(invalid_files),
            "unique_agent_ids": len(set(agent_ids)),
            "selection_axes": list(method["selection_axes"]),
            "influence_is_selection_axis": "influence" in method["selection_axes"],
            "retained_works": len(works),
            "unique_agent_work_observations": aggregate["unique_agent_work_observation_count"],
            "ranked_selections": len(raw_selections),
            "collected_ranked_selections": collected_selections,
            "excluded_ranked_selections": excluded_selections,
            "selection_group_lengths": dict(sorted(group_lengths.items())),
            "identity_merges": len(aggregate["merge_log"]),
            "series_rollup_decisions": len(aggregate["series_rollup_log"]),
            "within_agent_merges": len(aggregate["within_agent_merges"]),
            "retained_singletons": len(verification),
            "unverified_singletons": verification_summary["unverified_retained"],
            "excluded_records": verification_summary["excluded_records"],
            "malformed_observations": 0,
            "tv_component_rows": sum(w["medium"] in {"tv_season", "tv_episode"} for w in works),
            "duplicate_canonical_identities": len(identities) - len(set(identities)),
            "rank_adjustment_max": method.get("rank_adjustment_max"),
            "lower_bound_z": method.get("lower_bound_z"),
            "global_composite_sd": method.get("global_composite_sd"),
            "minimum_top_25_support": min(work["support"] for work in works[:25]),
            "minimum_top_100_support": min(work["support"] for work in works[:100]),
            "top_100_below_ten_support": sum(work["support"] < 10 for work in works[:100]),
        },
    }
    output = AUDIT / "final-integrity.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
