#!/usr/bin/env python3
"""Reconcile and aggregate the v3 scored mystery consensus responses."""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


AXES = ("influence", "ambition", "fairness", "originality")
SELECTION_AXES = ("ambition", "fairness", "originality")
WEIGHTS = {
    "influence": 0.10,
    "ambition": 0.40,
    "fairness": 0.25,
    "originality": 0.25,
}
PRIOR_STRENGTH = 10
RANK_ADJUSTMENT_MAX = 5.0
LOWER_BOUND_Z = 1.645
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent.parent / "data" / "v3"
AUDIT_DIR = DATA_DIR / "audit"

ALLOWED_MEDIA = {
    "novel", "book_series", "novella", "short_story", "film", "tv_series",
    "anime", "cartoon", "comic", "manga", "video_game", "visual_novel",
    "web_serial", "radio_drama", "audio_drama", "stage_play", "podcast",
    "documentary", "other",
}

# Alternate English titles and common abbreviations that are safe across agents.
ALIASES = [
    ("The Hollow Man", "The Three Coffins"),
    ("The Black Spectacles", "The Problem of the Green Capsule"),
    ("The Seven Deaths of Evelyn Hardcastle", "The 7½ Deaths of Evelyn Hardcastle"),
    ("The Seven and a Half Deaths of Evelyn Hardcastle", "The 7½ Deaths of Evelyn Hardcastle"),
    ("999: Nine Hours, Nine Persons, Nine Doors", "Nine Hours, Nine Persons, Nine Doors"),
    ("Zero Escape: Nine Hours, Nine Persons, Nine Doors", "Nine Hours, Nine Persons, Nine Doors"),
    ("Obra Dinn", "Return of the Obra Dinn"),
    ("Case Closed", "Detective Conan"),
    ("The Long Halloween", "Batman: The Long Halloween"),
    ("The Dancing Men", "The Adventure of the Dancing Men"),
    ("The Mystery of Notting Hill", "The Notting Hill Mystery"),
    ("Who Killed Roger Rabbit?", "Who Censored Roger Rabbit?"),
    ("Alan Wake II", "Alan Wake 2"),
    ("The Water Mill House Murders", "The Mill House Murders"),
    ("The Sign of Four", "The Sign of the Four"),
    ("Glass Onion", "Glass Onion: A Knives Out Mystery"),
    ("Curtain", "Curtain: Poirot's Last Case"),
    ("The Adventure of the Speckled Band", "The Speckled Band"),
    ("Zero Time Dilemma", "Zero Escape: Zero Time Dilemma"),
    ("The ABC Murders", "The A.B.C. Murders"),
    ("Summertime Rendering", "Summer Time Rendering"),
    ("Gokumon Island", "Death on Gokumon Island"),
    ("The Southern Reach Trilogy", "The Southern Reach Series"),
    ("The Tragedy of X", "The X Tragedy"),
    ("The Tragedy of Y", "The Y Tragedy"),
    ("Eight Detectives", "The Eighth Detective"),
    ("A Judgement in Stone", "A Judgment in Stone"),
]


def normalize(value: str) -> str:
    value = value.replace("½", " half ").replace("&", " and ")
    value = unicodedata.normalize("NFKD", value)
    value = "".join(character for character in value if not unicodedata.combining(character))
    value = value.casefold()
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    value = re.sub(r"^(the|a|an)\s+", "", value)
    return re.sub(r"\s+", " ", value)


ALIAS_LOOKUP: dict[str, str] = {}
for left, right in ALIASES:
    canonical = min(normalize(left), normalize(right))
    ALIAS_LOOKUP[normalize(left)] = canonical
    ALIAS_LOOKUP[normalize(right)] = canonical


def normalized_title(value: str) -> str:
    return ALIAS_LOOKUP.get(normalize(value), normalize(value))


MEDIA_FAMILIES = {
    "novel": "prose",
    "book_series": "prose",
    "novella": "prose",
    "short_story": "prose",
    "web_serial": "prose",
    "video_game": "interactive",
    "visual_novel": "interactive",
    "radio_drama": "audio",
    "audio_drama": "audio",
    "podcast": "audio",
}


def medium_family(value: str) -> str:
    return MEDIA_FAMILIES.get(value, value)


def matching_bucket_family(value: str) -> str:
    if value in {"film", "documentary", "anime", "tv_series", "cartoon"}:
        return "screen"
    return medium_family(value)


def creator_key(value: str) -> tuple[str, ...]:
    ignored = {"and", "with", "the"}
    return tuple(sorted(token for token in normalize(value).split() if token not in ignored))


def creators_related(left: str, right: str) -> bool:
    left_key = set(creator_key(left))
    right_key = set(creator_key(right))
    if not left_key or not right_key:
        return False
    overlap = left_key & right_key
    return bool(overlap) and len(overlap) >= min(len(left_key), len(right_key)) / 2


def canonical_tv_title(value: str) -> str:
    season_words = "one|two|three|four|five|six|seven|eight|nine|ten"
    return re.sub(
        rf"\s*[:,\-]?\s*(season|series)\s+(\d+|{season_words})\s*$",
        "",
        value,
        flags=re.IGNORECASE,
    ).strip()


@dataclass(frozen=True)
class Identity:
    title: str
    original_title: str
    creator: str
    year: int
    medium: str


@dataclass
class Observation:
    agent_number: int
    agent_id: str
    local_id: str
    raw_identity: Identity
    identity: Identity
    scores: dict[str, int]
    ranks: dict[str, int]


class UnionFind:
    def __init__(self, size: int):
        self.parent = list(range(size))

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def identity_from_work(work: dict[str, Any]) -> Identity:
    identity = Identity(
        title=work["title"].strip(),
        original_title=work["original_title"].strip(),
        creator=work["creator"].strip(),
        year=work["year"],
        medium=work["medium"],
    )
    title = normalize(identity.title)
    creator = normalize(identity.creator)

    if identity.medium == "tv_series":
        identity = Identity(
            canonical_tv_title(identity.title), identity.original_title,
            identity.creator, identity.year, "tv_series",
        )
        title = normalize(identity.title)

    # Verified aliases and work-unit corrections that cannot be inferred from
    # punctuation alone.  These map component/series or publication-metadata
    # variants to the broad coherent work requested by the study rules.
    if title in {"southern reach trilogy", "southern reach series", "annihilation"} and creator == "jeff vandermeer" and identity.medium in {"novel", "book_series"}:
        return Identity("The Southern Reach Series", "", "Jeff VanderMeer", 2014, "book_series")
    if title == "remembrance of earth s past" and creator in {"liu cixin", "cixin liu"}:
        return Identity("Remembrance of Earth's Past", "", "Liu Cixin", 2006, "book_series")
    if title == "death notice" and creator == "zhou haohui" and identity.medium in {"novel", "book_series"}:
        return Identity("Death Notice", "", "Zhou Haohui", 2009, "book_series")
    if title in {"new york trilogy", "city of glass"} and creator == "paul auster" and identity.medium in {"novel", "novella", "book_series"}:
        return Identity("The New York Trilogy", "", "Paul Auster", 1985, "book_series")
    if title in {"southern reach trilogy", "southern reach series"} and creator == "jeff vandermeer":
        return Identity("The Southern Reach Series", "", "Jeff VanderMeer", 2014, "book_series")
    if title in {"summer time rendering", "summertime rendering"} and creator == "yasuki tanaka":
        return Identity("Summer Time Rendering", identity.original_title, "Yasuki Tanaka", 2017, "manga")
    if title in {"abc murders", "a b c murders"} and creator == "agatha christie":
        return Identity("The A.B.C. Murders", "", "Agatha Christie", 1936, "novel")
    if title in {"gokumon island", "death on gokumon island"} and creator == "seishi yokomizo":
        return Identity("Death on Gokumon Island", identity.original_title, "Seishi Yokomizo", 1947, "novel")
    if title == "columbo" and creator_key(identity.creator) == creator_key("Richard Levinson and William Link"):
        return Identity("Columbo", "", "Richard Levinson and William Link", 1968, "tv_series")
    if title == "mill house murders" and creator == "yukito ayatsuji":
        return Identity("The Mill House Murders", identity.original_title, "Yukito Ayatsuji", 1988, "novel")
    if title == "stanley parable" and creator == "davey wreden":
        return Identity("The Stanley Parable", "", "Davey Wreden", 2013, "video_game")
    if title == "manuscript found in saragossa" and creator == "jan potocki":
        return Identity("The Manuscript Found in Saragossa", identity.original_title, "Jan Potocki", 1805, "novel")
    if title == "equal danger" and creator == "leonardo sciascia":
        return Identity("Equal Danger", identity.original_title, "Leonardo Sciascia", 1966, "novel")
    if title == "seven moons of maali almeida" and creator == "shehan karunatilaka":
        return Identity("The Seven Moons of Maali Almeida", "", "Shehan Karunatilaka", 2020, "novel")
    if title == "hamlet" and creator == "william shakespeare":
        return Identity("Hamlet", "", "William Shakespeare", 1603, "stage_play")
    if title == "this house has people in it" and creator == "alan resnick":
        return Identity("This House Has People in It", "", "Alan Resnick", 2016, "web_serial")
    if title == "eighth detective" and creator == "takemaru abiko":
        return Identity("The 8 Mansion Murders", "8 no Satsujin", "Takemaru Abiko", 1989, "novel")
    if title in {
        "danganronpa", "danganronpa series", "danganronpa trigger happy havoc",
        "danganronpa 2 goodbye despair", "danganronpa v3 killing harmony",
    } and creator in {
        "kazutaka kodaka", "kazutaka kodaka and spike chunsoft",
        "spike chunsoft and kazutaka kodaka", "spike chunsoft kazutaka kodaka",
        "spike chunsoft",
    }:
        return Identity("Danganronpa", "", "Kazutaka Kodaka", 2010, "video_game")
    if title in {
        "zero escape", "nine hours nine persons nine doors",
        "zero escape virtue s last reward", "zero escape zero time dilemma",
    } and creator == "kotaro uchikoshi":
        return Identity("Zero Escape", "", "Kotaro Uchikoshi", 2009, "video_game")
    if title in {
        "case of the golden idol", "rise of the golden idol",
        "golden idol series", "golden idol saga",
    } and creator in {
        "color gray games", "andrejs klavins and color gray games",
        "andrejs and ernests klavins", "andrejs klavins and ernests klavins",
    }:
        return Identity("The Golden Idol Series", "", "Color Gray Games", 2022, "video_game")
    if title == "border line case" and creator == "margery allingham":
        return Identity("The Border-Line Case", "", "Margery Allingham", 1933, "short_story")
    return identity


def valid_work(work: Any) -> bool:
    if not isinstance(work, dict):
        return False
    expected = {"work_id", "title", "original_title", "creator", "year", "medium", "scores"}
    if set(work) != expected:
        return False
    if not isinstance(work["work_id"], str) or not work["work_id"].strip():
        return False
    if not isinstance(work["title"], str) or not work["title"].strip():
        return False
    if not isinstance(work["original_title"], str):
        return False
    if not isinstance(work["creator"], str) or not work["creator"].strip():
        return False
    if type(work["year"]) is not int or not 1000 <= work["year"] <= 2026:
        return False
    if work["medium"] not in ALLOWED_MEDIA:
        return False
    if not isinstance(work["scores"], dict) or set(work["scores"]) != set(AXES):
        return False
    return all(type(work["scores"][axis]) is int and 0 <= work["scores"][axis] <= 100 for axis in AXES)


def load_observations(raw_dir: Path) -> tuple[list[Observation], dict[str, Any]]:
    observations: list[Observation] = []
    audit: dict[str, Any] = {
        "files_seen": 0,
        "files_unreadable": [],
        "malformed_observations": [],
        "unknown_axis_references": [],
    }
    paths = sorted(raw_dir.glob("agent_*.json"), key=lambda path: int(path.stem.split("_")[1]))
    for path in paths:
        audit["files_seen"] += 1
        agent_number = int(path.stem.split("_")[1])
        try:
            payload = json.loads(path.read_text())
        except Exception as exc:
            audit["files_unreadable"].append({"file": path.name, "error": str(exc)})
            continue
        if not isinstance(payload, dict):
            audit["files_unreadable"].append({"file": path.name, "error": "top level is not an object"})
            continue
        agent_id = payload.get("agent_id")
        works = payload.get("works")
        axes = payload.get("axes")
        if not isinstance(agent_id, str) or not isinstance(works, list) or not isinstance(axes, dict):
            audit["files_unreadable"].append({"file": path.name, "error": "missing top-level fields"})
            continue

        by_id: dict[str, dict[str, Any]] = {}
        for index, work in enumerate(works, 1):
            if not valid_work(work):
                audit["malformed_observations"].append({"file": path.name, "work_index": index})
                continue
            # Duplicate IDs are malformed as a unit: do not let one silently replace another.
            if work["work_id"] in by_id:
                audit["malformed_observations"].append({
                    "file": path.name, "work_index": index, "reason": "duplicate work_id"
                })
                by_id.pop(work["work_id"], None)
                continue
            by_id[work["work_id"]] = work

        ranks_by_id: dict[str, dict[str, int]] = defaultdict(dict)
        for axis in SELECTION_AXES:
            ranking = axes.get(axis)
            if not isinstance(ranking, list):
                continue
            for rank, local_id in enumerate(ranking, 1):
                if local_id in by_id:
                    ranks_by_id[local_id].setdefault(axis, rank)
                else:
                    audit["unknown_axis_references"].append({
                        "file": path.name, "axis": axis, "rank": rank, "work_id": local_id
                    })
        for local_id, work in by_id.items():
            if local_id not in ranks_by_id:
                audit["malformed_observations"].append({
                    "file": path.name, "work_id": local_id, "reason": "unreferenced work"
                })
                continue
            observations.append(Observation(
                agent_number=agent_number,
                agent_id=agent_id,
                local_id=local_id,
                raw_identity=Identity(
                    title=work["title"].strip(),
                    original_title=work["original_title"].strip(),
                    creator=work["creator"].strip(),
                    year=work["year"],
                    medium=work["medium"],
                ),
                identity=identity_from_work(work),
                scores={axis: work["scores"][axis] for axis in AXES},
                ranks=ranks_by_id[local_id],
            ))
    return observations, audit


def title_candidates(identity: Identity) -> set[str]:
    candidates = set()
    for value in (identity.title, identity.original_title):
        if not value:
            continue
        candidate = normalized_title(value)
        candidates.add(candidate)
        unqualified = re.sub(
            r"\s+(film|novel|novella|book|tv series|television series|series|video game|game|anime|manga)$",
            "", candidate,
        ).strip()
        if unqualified:
            candidates.add(normalized_title(unqualified))
    # A title written entirely in a non-Latin script can normalize to an empty
    # string under the ASCII-oriented matcher.  Empty strings are not identity
    # evidence: retaining one would put every such work from the same medium
    # and nearby year into a shared bucket and create transitive false merges.
    return {candidate for candidate in candidates if candidate}


def compatible_media(left: Identity, right: Identity) -> bool:
    if left.medium == right.medium:
        return True
    if medium_family(left.medium) == medium_family(right.medium) in {"prose", "interactive", "audio"}:
        return True
    pair = {left.medium, right.medium}
    return pair <= {"film", "documentary"} or pair <= {"film", "anime"} or pair <= {"tv_series", "cartoon"}


def titles_match(left: str, right: str) -> bool:
    if left == right:
        return True
    if min(len(left), len(right)) < 8:
        return False
    return SequenceMatcher(None, left, right).ratio() >= 0.93


def should_merge(left: Identity, right: Identity) -> bool:
    if not compatible_media(left, right) or abs(left.year - right.year) > 1:
        return False
    left_titles = title_candidates(left)
    right_titles = title_candidates(right)
    if left_titles & right_titles:
        return left.medium == right.medium or creators_related(left.creator, right.creator)
    creators_match = normalize(left.creator) == normalize(right.creator)
    return creators_match and any(titles_match(a, b) for a in left_titles for b in right_titles)


def build_clusters(observations: list[Observation]) -> tuple[list[list[Identity]], dict[Identity, int], Counter[Identity]]:
    identity_counts = Counter(observation.identity for observation in observations)
    identities = list(identity_counts)
    union_find = UnionFind(len(identities))

    # Exact title/creator matches are the same work even when agents disagree
    # about a translation year or classify prose, interactive, or audio forms
    # at adjacent levels of specificity.  Grouping here also handles creator
    # name order while keeping adaptations in different forms separate.
    exact_groups: dict[tuple[str, tuple[str, ...], str], list[int]] = defaultdict(list)
    for index, identity in enumerate(identities):
        family = medium_family(identity.medium)
        for title in title_candidates(identity):
            exact_groups[(title, creator_key(identity.creator), family)].append(index)
    for indices in exact_groups.values():
        for other in indices[1:]:
            union_find.union(indices[0], other)

    buckets: dict[tuple[str, int], list[int]] = defaultdict(list)
    for index, identity in enumerate(identities):
        for title in title_candidates(identity):
            for year in (identity.year - 1, identity.year, identity.year + 1):
                buckets[(f"{matching_bucket_family(identity.medium)}:{title}", year)].append(index)

    pairs: set[tuple[int, int]] = set()
    for indices in buckets.values():
        for offset, left_index in enumerate(indices):
            for right_index in indices[offset + 1:]:
                pair = tuple(sorted((left_index, right_index)))
                if pair in pairs:
                    continue
                pairs.add(pair)
                if should_merge(identities[left_index], identities[right_index]):
                    union_find.union(left_index, right_index)

    by_root: dict[int, list[Identity]] = defaultdict(list)
    for index, identity in enumerate(identities):
        by_root[union_find.find(index)].append(identity)
    clusters = list(by_root.values())
    identity_to_cluster = {
        identity: cluster_index
        for cluster_index, cluster in enumerate(clusters)
        for identity in cluster
    }
    return clusters, identity_to_cluster, identity_counts


def choose_canonical(cluster: list[Identity], counts: Counter[Identity]) -> Identity:
    return sorted(cluster, key=lambda identity: (
        0 if identity.medium == "book_series" else 1,
        -counts[identity],
        len(identity.title),
        identity.year,
        identity.title.casefold(),
    ))[0]


def load_exclusions(path: Path) -> set[tuple[str, int, str]]:
    if not path.exists():
        return set()
    records = json.loads(path.read_text())
    return {(normalized_title(item["title"]), item["year"], item["medium"]) for item in records}


def rank_adjustment(axis: str, ranks: dict[str, int]) -> float:
    """Return a bounded ordinal correction on the original 0–100 scale.

    Selection-list rank 1 adds five points, rank 100 subtracts five, and a
    work scored through another axis but absent from this list is treated as
    the conservatively censored rank 101. Influence has no selection list and
    therefore receives no rank correction.
    """
    if axis not in SELECTION_AXES:
        return 0.0
    rank = ranks.get(axis, 101)
    return RANK_ADJUSTMENT_MAX * (50.5 - rank) / 49.5


def rank_adjusted_score(observation: Observation, axis: str) -> float:
    return max(0.0, min(100.0, observation.scores[axis] + rank_adjustment(axis, observation.ranks)))


def aggregate(observations: list[Observation], exclusions_path: Path) -> dict[str, Any]:
    if not observations:
        raise ValueError("No valid work observations")
    clusters, identity_to_cluster, identity_counts = build_clusters(observations)
    canonicals = [choose_canonical(cluster, identity_counts) for cluster in clusters]

    grouped: dict[tuple[int, int], list[Observation]] = defaultdict(list)
    for observation in observations:
        grouped[(observation.agent_number, identity_to_cluster[observation.identity])].append(observation)

    unique_observations: dict[int, list[Observation]] = defaultdict(list)
    merged_within_agent: list[dict[str, Any]] = []
    selection_ranks: dict[int, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    raw_selections: list[dict[str, Any]] = []
    for (agent_number, cluster_index), variants in grouped.items():
        chosen = sorted(variants, key=lambda item: (
            -len(item.ranks),
            sum(item.ranks.values()),
            min(item.ranks.values()),
            item.local_id,
        ))[0]
        unique_observations[cluster_index].append(chosen)

        # Keep every literal source placement for the raw-data view even when
        # two source labels reconcile to one canonical work for scoring.
        for variant in variants:
            for axis, rank in variant.ranks.items():
                raw_selections.append({
                    "agent_number": agent_number,
                    "agent_id": variant.agent_id,
                    "cluster_index": cluster_index,
                    "axis": axis,
                    "rank": rank,
                    "raw_work_id": variant.local_id,
                    "raw_title": variant.raw_identity.title,
                    "raw_creator": variant.raw_identity.creator,
                    "raw_year": variant.raw_identity.year,
                    "raw_medium": variant.raw_identity.medium,
                    "scores": variant.scores,
                })
        combined_ranks: dict[str, int] = {}
        for variant in variants:
            for axis, rank in variant.ranks.items():
                combined_ranks[axis] = min(combined_ranks.get(axis, rank), rank)
        chosen.ranks = combined_ranks
        for axis, rank in combined_ranks.items():
            selection_ranks[cluster_index][axis].append(rank)
        if len(variants) > 1:
            merged_within_agent.append({
                "agent_number": agent_number,
                "canonical": canonicals[cluster_index].title,
                "kept": chosen.local_id,
                "discarded": [item.local_id for item in variants if item is not chosen],
            })

    exclusion_keys = load_exclusions(exclusions_path)
    included_clusters = [
        index for index, canonical in enumerate(canonicals)
        if (normalized_title(canonical.title), canonical.year, canonical.medium) not in exclusion_keys
    ]
    excluded_clusters = sorted(set(range(len(canonicals))) - set(included_clusters))

    all_included_observations = [
        observation
        for cluster_index in included_clusters
        for observation in unique_observations[cluster_index]
    ]
    global_raw_means = {
        axis: statistics.fmean(observation.scores[axis] for observation in all_included_observations)
        for axis in AXES
    }
    global_rank_adjusted_means = {
        axis: statistics.fmean(rank_adjusted_score(observation, axis) for observation in all_included_observations)
        for axis in AXES
    }
    observation_composites = [
        sum(WEIGHTS[axis] * rank_adjusted_score(observation, axis) for axis in AXES)
        for observation in all_included_observations
    ]
    global_composite_mean = statistics.fmean(observation_composites)
    global_composite_sd = statistics.pstdev(observation_composites)
    agent_count = len({observation.agent_number for observation in observations})

    works: list[dict[str, Any]] = []
    for cluster_index in included_clusters:
        canonical = canonicals[cluster_index]
        work_observations = unique_observations[cluster_index]
        raw_means = {
            axis: statistics.fmean(item.scores[axis] for item in work_observations)
            for axis in AXES
        }
        rank_adjusted_means = {
            axis: statistics.fmean(rank_adjusted_score(item, axis) for item in work_observations)
            for axis in AXES
        }
        support = len(work_observations)
        adjusted_scores = {
            axis: (
                support * rank_adjusted_means[axis]
                + PRIOR_STRENGTH * global_rank_adjusted_means[axis]
            ) / (support + PRIOR_STRENGTH)
            for axis in AXES
        }
        raw_composite = sum(WEIGHTS[axis] * raw_means[axis] for axis in AXES)
        posterior_composite = sum(WEIGHTS[axis] * adjusted_scores[axis] for axis in AXES)
        confidence_penalty = LOWER_BOUND_Z * global_composite_sd / math.sqrt(support)
        consensus_score = posterior_composite - confidence_penalty
        works.append({
            "cluster_index": cluster_index,
            **asdict(canonical),
            "support": support,
            "support_rate": support / agent_count,
            "raw_scores": raw_means,
            "rank_adjusted_scores": rank_adjusted_means,
            "adjusted_scores": adjusted_scores,
            "raw_composite": raw_composite,
            "posterior_composite": posterior_composite,
            "confidence_penalty": confidence_penalty,
            "adjusted_composite": consensus_score,
            "selection_counts": {axis: len(selection_ranks[cluster_index][axis]) for axis in SELECTION_AXES},
            "mean_selection_ranks": {
                axis: statistics.fmean(selection_ranks[cluster_index][axis]) if selection_ranks[cluster_index][axis] else None
                for axis in SELECTION_AXES
            },
        })

    works.sort(key=lambda work: (
        -work["adjusted_composite"],
        -work["support"],
        -work["raw_composite"],
        work["year"],
        work["title"].casefold(),
    ))
    for rank, work in enumerate(works, 1):
        work["overall_rank"] = rank

    rank_by_cluster = {work["cluster_index"]: work["overall_rank"] for work in works}
    canonical_by_cluster = {index: asdict(canonical) for index, canonical in enumerate(canonicals)}
    retained_observations = []
    for cluster_index in included_clusters:
        for observation in unique_observations[cluster_index]:
            retained_observations.append({
                "agent_number": observation.agent_number,
                "agent_id": observation.agent_id,
                "cluster_index": cluster_index,
                "source_work_id": observation.local_id,
                "scores": observation.scores,
                "ranks": observation.ranks,
                "canonical": canonical_by_cluster[cluster_index],
                "overall_rank": rank_by_cluster[cluster_index],
            })
    retained_raw_selections = []
    for selection in raw_selections:
        if selection["cluster_index"] not in rank_by_cluster:
            continue
        selection["canonical"] = canonical_by_cluster[selection["cluster_index"]]
        selection["overall_rank"] = rank_by_cluster[selection["cluster_index"]]
        retained_raw_selections.append(selection)

    merge_log = [
        {"from": asdict(identity), "to": asdict(canonicals[index]), "observations": identity_counts[identity]}
        for index, cluster in enumerate(clusters)
        for identity in cluster
        if identity != canonicals[index]
    ]
    return {
        "method": {
            "weights": WEIGHTS,
            "prior_strength": PRIOR_STRENGTH,
            "rank_adjustment_max": RANK_ADJUSTMENT_MAX,
            "unselected_censored_rank": 101,
            "lower_bound_z": LOWER_BOUND_Z,
            "global_raw_axis_means": global_raw_means,
            "global_axis_means": global_rank_adjusted_means,
            "global_composite_mean": global_composite_mean,
            "global_composite_sd": global_composite_sd,
            "selection_axes": list(SELECTION_AXES),
            "rank_adjustment_axes": list(SELECTION_AXES),
            "confidence_support_denominator": "sqrt(actual agent support)",
            "placement_role": "ambition, fairness, and originality select candidates and supply bounded ±5 rank corrections; influence is scored only",
            "ranking_score": "one-sided 95% lower confidence bound of the rank-adjusted Bayesian weighted mean",
        },
        "agent_count": agent_count,
        "valid_observation_count": len(observations),
        "unique_agent_work_observation_count": sum(len(items) for items in unique_observations.values()),
        "collected_raw_selection_count": len(raw_selections),
        "excluded_raw_selection_count": len(raw_selections) - len(retained_raw_selections),
        "works": works,
        "observations": retained_observations,
        "raw_selections": retained_raw_selections,
        "excluded": [asdict(canonicals[index]) for index in excluded_clusters],
        "merge_log": merge_log,
        "within_agent_merges": merged_within_agent,
        "singletons": [work for work in works if work["support"] == 1],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("raw_dir", type=Path, nargs="?", default=DATA_DIR / "raw_agents")
    parser.add_argument("--exclusions", type=Path, default=AUDIT_DIR / "exclusions.json")
    parser.add_argument("--output-dir", type=Path, default=AUDIT_DIR)
    parser.add_argument("--aggregate-output", type=Path, default=DATA_DIR / "aggregate.json")
    args = parser.parse_args()

    observations, ingestion_audit = load_observations(args.raw_dir)
    result = aggregate(observations, args.exclusions)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.aggregate_output.parent.mkdir(parents=True, exist_ok=True)
    args.aggregate_output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    (args.output_dir / "ingestion-audit.json").write_text(json.dumps(ingestion_audit, ensure_ascii=False, indent=2) + "\n")
    (args.output_dir / "identity-merges.json").write_text(json.dumps(result["merge_log"], ensure_ascii=False, indent=2) + "\n")
    (args.output_dir / "within-agent-merges.json").write_text(json.dumps(result["within_agent_merges"], ensure_ascii=False, indent=2) + "\n")
    (args.output_dir / "singletons.json").write_text(json.dumps(result["singletons"], ensure_ascii=False, indent=2) + "\n")

    summary = {
        "agents": result["agent_count"],
        "valid_observations": result["valid_observation_count"],
        "unique_agent_work_observations": result["unique_agent_work_observation_count"],
        "retained_works": len(result["works"]),
        "singletons": len(result["singletons"]),
        "excluded": len(result["excluded"]),
        "identity_merges": len(result["merge_log"]),
        "within_agent_merges": len(result["within_agent_merges"]),
        "malformed_observations": len(ingestion_audit["malformed_observations"]),
        "unknown_axis_references": len(ingestion_audit["unknown_axis_references"]),
        "global_axis_means": result["method"]["global_axis_means"],
        "top_25": [
            {
                "rank": work["overall_rank"],
                "title": work["title"],
                "creator": work["creator"],
                "year": work["year"],
                "medium": work["medium"],
                "weighted_score": round(work["adjusted_composite"], 4),
                "support": work["support"],
            }
            for work in result["works"][:25]
        ],
    }
    (args.output_dir / "audit-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
