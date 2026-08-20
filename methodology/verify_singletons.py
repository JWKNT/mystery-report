#!/usr/bin/env python3
"""Conservatively verify support-one works against public catalogues."""

from __future__ import annotations

import concurrent.futures
import html
import json
import re
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

import requests


BASE_DIR = Path(__file__).resolve().parent
AUDIT_DIR = BASE_DIR.parent / "data" / "audit"
INPUT = AUDIT_DIR / "singletons.json"
OUTPUT = AUDIT_DIR / "singleton-verification.json"
UNVERIFIED = AUDIT_DIR / "unverified-singletons.json"
USER_AGENT = "MysteryConsensusVerifier/3.0 (local research dataset)"
PROSE = {"novel", "book_series", "novella", "short_story", "web_serial", "other"}
SCREEN = {"film", "tv_series", "anime", "cartoon", "documentary"}


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(character for character in value if not unicodedata.combining(character))
    value = html.unescape(re.sub(r"<[^>]+>", " ", value)).casefold().replace("&", " and ")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value)).strip()


def similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, normalized(left), normalized(right)).ratio()


def creator_tokens(value: str) -> set[str]:
    ignored = {"and", "the", "with", "studios", "studio", "games", "productions", "company"}
    return {token for token in normalized(value).split() if len(token) >= 4 and token not in ignored}


def year_matches(text: str, year: int, tolerance: int = 2) -> bool:
    return any(str(candidate) in text for candidate in range(year - tolerance, year + tolerance + 1))


def get_json(url: str, params: dict[str, Any] | None = None) -> Any:
    last_error: Exception | None = None
    for attempt in range(5):
        try:
            response = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=25)
            if response.status_code == 429 or response.status_code >= 500:
                delay = min(12.0, float(response.headers.get("Retry-After", 0) or 0) or 1.5 * (2 ** attempt))
                time.sleep(delay)
                continue
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt < 4:
                time.sleep(1.5 * (2 ** attempt))
    if last_error:
        raise last_error
    response.raise_for_status()
    return response.json()


def wikipedia(work: dict[str, Any]) -> dict[str, Any] | None:
    data = get_json("https://en.wikipedia.org/w/api.php", {
        "action": "query", "generator": "search",
        "gsrsearch": f'\"{work["title"]}\" \"{work["creator"]}\"', "gsrlimit": 5,
        "prop": "extracts", "exintro": 1, "explaintext": 1, "format": "json",
    })
    wanted_creator = creator_tokens(work["creator"])
    for page in data.get("query", {}).get("pages", {}).values():
        page_title = page.get("title", "")
        haystack = normalized(f'{page_title} {page.get("extract", "")}')
        wanted_title = normalized(work["title"])
        candidate_title = normalized(page_title)
        title_match = (similarity(work["title"], page_title) >= 0.86
                       or wanted_title in candidate_title or candidate_title in wanted_title)
        creator_match = bool(wanted_creator & set(haystack.split()))
        date_match = year_matches(haystack, int(work["year"]))
        if title_match and (creator_match or date_match):
            return {"source": "Wikipedia", "matched_title": page_title,
                    "url": f'https://en.wikipedia.org/?curid={page["pageid"]}',
                    "basis": "title plus creator or release year"}
    return None


def open_library(work: dict[str, Any]) -> dict[str, Any] | None:
    if work["medium"] not in PROSE:
        return None
    data = get_json("https://openlibrary.org/search.json", {
        "title": work["title"], "limit": 10,
        "fields": "key,title,author_name,first_publish_year",
    })
    wanted_creator = creator_tokens(work["creator"])
    for item in data.get("docs", []):
        if similarity(work["title"], item.get("title", "")) < 0.90:
            continue
        creator_match = bool(wanted_creator & set(normalized(" ".join(item.get("author_name", []))).split()))
        year = item.get("first_publish_year")
        date_match = isinstance(year, int) and abs(year - int(work["year"])) <= 3
        if creator_match or date_match:
            return {"source": "Open Library", "matched_title": item.get("title", ""),
                    "url": f'https://openlibrary.org{item["key"]}',
                    "basis": "catalogue title plus author or publication year"}
    return None


def imdb(work: dict[str, Any]) -> dict[str, Any] | None:
    if work["medium"] not in SCREEN:
        return None
    slug = quote(work["title"].casefold().replace(" ", "_"), safe="")
    data = get_json(f"https://v2.sg.media-imdb.com/suggestion/x/{slug}.json")
    for item in data.get("d", []):
        year = item.get("y")
        identifier = item.get("id", "")
        if (similarity(work["title"], item.get("l", "")) >= 0.92
                and isinstance(year, int) and abs(year - int(work["year"])) <= 2
                and identifier.startswith("tt")):
            return {"source": "IMDb", "matched_title": item.get("l", ""),
                    "url": f"https://www.imdb.com/title/{identifier}/",
                    "basis": "title and release year"}
    return None


def wikidata(work: dict[str, Any]) -> dict[str, Any] | None:
    data = get_json("https://www.wikidata.org/w/api.php", {
        "action": "wbsearchentities", "search": work["title"], "language": "en",
        "uselang": "en", "limit": 10, "format": "json",
    })
    wanted_creator = creator_tokens(work["creator"])
    candidates = [
        item for item in data.get("search", [])
        if max((similarity(work["title"], name)
                for name in [item.get("label", ""), *item.get("aliases", [])]), default=0) >= 0.90
    ]
    if not candidates:
        return None
    entities = get_json("https://www.wikidata.org/w/api.php", {
        "action": "wbgetentities", "ids": "|".join(item["id"] for item in candidates),
        "props": "claims", "format": "json",
    }).get("entities", {})
    for item in candidates:
        names = [item.get("label", ""), *item.get("aliases", [])]
        description = normalized(item.get("description", ""))
        dates: list[int] = []
        claims = entities.get(item["id"], {}).get("claims", {})
        for property_id in ("P577", "P571"):
            for claim in claims.get(property_id, []):
                value = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
                time = value.get("time", "") if isinstance(value, dict) else ""
                match = re.match(r"[+-](\d{4})-", time)
                if match:
                    dates.append(int(match.group(1)))
        date_match = any(abs(year - int(work["year"])) <= 2 for year in dates)
        if wanted_creator & set(description.split()) or year_matches(description, int(work["year"])) or date_match:
            return {"source": "Wikidata", "matched_title": item.get("label", ""),
                    "url": item.get("concepturi", f'https://www.wikidata.org/wiki/{item["id"]}'),
                    "basis": "entity title plus creator or release-date metadata"}
    return None


def run_source(works: list[dict[str, Any]], pending: set[int], results: list[dict[str, Any]],
               verifier: Callable[[dict[str, Any]], dict[str, Any] | None]) -> None:
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(verifier, works[index]): index for index in sorted(pending)}
        for future in concurrent.futures.as_completed(futures):
            index = futures[future]
            try:
                evidence = future.result()
            except Exception as exc:
                results[index].setdefault("errors", []).append(f"{verifier.__name__}: {type(exc).__name__}: {exc}")
                continue
            if evidence:
                results[index]["status"] = "verified"
                results[index]["evidence"] = evidence
                pending.discard(index)


def main() -> None:
    works = json.loads(INPUT.read_text())
    results = [{"work": work, "status": "unverified"} for work in works]
    pending = set(range(len(works)))
    if OUTPUT.exists():
        prior = json.loads(OUTPUT.read_text())
        prior_verified = {
            (
                normalized(record["work"]["title"]),
                normalized(record["work"]["creator"]),
                record["work"]["year"],
                record["work"]["medium"],
            ): record
            for record in prior
            if record.get("status") == "verified"
        }
        for index, work in enumerate(works):
            key = (normalized(work["title"]), normalized(work["creator"]), work["year"], work["medium"])
            if key in prior_verified:
                results[index] = prior_verified[key]
                pending.discard(index)
    for verifier in (wikipedia, open_library, imdb, wikidata):
        run_source(works, pending, results, verifier)
        print(f"after {verifier.__name__}: verified={len(works) - len(pending)} pending={len(pending)}", flush=True)
    OUTPUT.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n")
    UNVERIFIED.write_text(json.dumps([results[index] for index in sorted(pending)], ensure_ascii=False, indent=2) + "\n")
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
