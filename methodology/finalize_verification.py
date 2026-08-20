#!/usr/bin/env python3
"""Combine automatic and targeted singleton evidence; fail if any remain."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
AUDIT_DIR = BASE_DIR.parent / "data" / "audit"

MANUAL_SOURCES = {
    "The Picture from the Past": "https://en.wikipedia.org/wiki/Paul_Halter",
    "Root Double: Before Crime * After Days": "https://en.wikipedia.org/wiki/Root_Double:_Before_Crime_*_After_Days",
    "Six Crimes Without a Murderer": "https://www.penguinrandomhouse.com/books/839024/six-crimes-without-a-murderer-by-pierre-boileau/",
    "The Player on the Other Side": "https://openlibrary.org/works/OL14857727W/The_Player_on_the_Other_Side_(An_Ellery_Queen_Mystery)",
    "The Tiger's Head": "https://en.wikipedia.org/wiki/Paul_Halter",
    "NieR: Automata": "https://en.wikipedia.org/wiki/Nier:_Automata",
    "S-Town": "https://podcasts.apple.com/us/podcast/s-town/id1212558767",
    "The Physicists": "https://www.schauspielhaus.ch/de/archiv/13139/die-physiker",
    "Underworld USA Trilogy": "https://www.penguinrandomhouse.com/series/DCH/underworld-usa-trilogy/",
    "The King Is Dead": "https://en.wikipedia.org/wiki/The_King_Is_Dead_(novel)",
    "The Truth about the Savolta Case": "https://en.wikipedia.org/wiki/The_Truth_about_the_Savolta_Case",
    "Shadow of the Colossus": "https://en.wikipedia.org/wiki/Shadow_of_the_Colossus",
    "What Remains of Edith Finch": "https://annapurnainteractive.com/games/what-remains-of-edith-finch",
    "The Infectious Madness of Doctor Dekker": "https://en.wikipedia.org/wiki/The_Infectious_Madness_of_Doctor_Dekker",
    "The Zodiac Trial": "https://store.steampowered.com/app/1513120/The_Zodiac_Trial/",
    "Detective School Q": "https://www.kodansha.co.jp/comic/products/0000006314",
    "The Last Policeman trilogy": "https://www.simonandschuster.com/books/The-Last-Policeman/Ben-H-Winters/The-Last-Policeman-Trilogy/9781594746741",
    "The Black Watchmen": "https://store.steampowered.com/app/349220/The_Black_Watchmen/",
    "Doubt: A Parable": "https://www.pulitzer.org/winners/john-patrick-shanley",
    "The White Vault": "https://en.wikipedia.org/wiki/The_White_Vault",
    "The Avenging Chance": "https://bookbrainz.org/work/e2c7cd97-7d50-4605-a27b-29d79b3320c7",
    "The Tea Leaf": "https://www.lybrary.com/the-tea-leaf-p-926101.html",
    "The Infatuations": "https://www.penguinrandomhouse.com/books/219846/the-infatuations-by-javier-marias/",
    "The Black Tapes": "https://podcasts.apple.com/us/podcast/the-black-tapes/id997522893",
    "The Private Eye": "https://www.simonandschuster.com/books/Private-Eye-Deluxe-Edition/Marcos-Martin/9781632155726",
    "The Circular Ruins": "https://en.wikipedia.org/wiki/The_Circular_Ruins",
    "The Border-Line Case": "https://margeryallingham.com/book/mr-campion-criminologist/",
    "Noroi: The Curse": "https://tv.apple.com/us/movie/noroi-the-curse/umc.cmc.60o3q8ge7igy1uwl2gk1i5fnf",
    "The Two Bottles of Relish": "https://en.wikipedia.org/wiki/In_the_Land_of_Time,_and_Other_Fantasy_Tales",
    "Gideon Falls": "https://imagecomics.com/comics/releases/gideon-falls-1",
    "The Walten Files": "https://thewaltenfiles.wiki.gg/wiki/The_Walten_Files",
    "Blade Runner": "https://en.wikipedia.org/wiki/Blade_Runner_(1997_video_game)",
    "Antichamber": "https://store.steampowered.com/app/219890/Antichamber/",
    "Truly Devious trilogy": "https://maureenjohnsonbooks.com/the-truly-devious-series/",
    "Cocoon": "https://annapurnainteractive.com/games/cocoon",
    "The Path": "https://www.tale-of-tales.com/ThePath/presskit/ToT-ThePath-FactSheet.pdf",
    "Mirror": "https://www.bfi.org.uk/film/97341aa7-c937-57bf-9011-99bb084472b9/mirror",
    "The Vorrh Trilogy": "https://www.publishersweekly.com/9781101873786",
    "Unavowed": "https://wadjeteyegames.com/games/unavowed/",
    "Homunculus": "https://www.penguinrandomhouse.com/series/NCU/homunculus/",
    "Like a Velvet Glove Cast in Iron": "https://en.wikipedia.org/wiki/Like_a_Velvet_Glove_Cast_in_Iron",
    "The Summer Hikaru Died": "https://yenpress.com/titles/9798855414486-the-summer-hikaru-died-chapter-21",
    "The Long Night": "https://www.goodreads.com/work/editions/56052030-the-long-night",
    "Continuity of Parks": "https://en.wikipedia.org/wiki/Continuidad_de_los_parques",
    "The Colonel's Bequest": "https://en.wikipedia.org/wiki/The_Colonel%27s_Bequest",
    "The Portopia Serial Murder Case": "https://en.wikipedia.org/wiki/The_Portopia_Serial_Murder_Case",
    "The Plotters": "https://klwave.or.kr/klw/books/101534/featuredView.do",
    "Axolotl": "https://www.educ.ar/recursos/154248/axolotl-de-julio-cortazar",
    "Detective Grimoire": "https://www.detectivegrimoire.sfbgames.com/",
    "The Lost Files of Sherlock Holmes: The Case of the Serrated Scalpel": "https://www.arthur-conan-doyle.com/index.php/The_Lost_Files_of_Sherlock_Holmes:_The_Case_of_the_Serrated_Scalpel",
    "The Demon of the Lonely Isle": "https://books.google.com/books/about/The_Demon_of_the_Lonely_Isle.html?id=KCgtEQAAQBAJ",
    "The Hole": "https://www.yes24.com/Product/goods/25452191",
    "The Investigation": "https://www.simonandschuster.com/books/The-Investigation/J-M-Lee/9781605988467",
    "Seven Years of Darkness": "https://library.ltikorea.or.kr/originalworks/100097",
}


def manual_sources() -> dict[str, str]:
    sources = dict(MANUAL_SOURCES)
    for name in ("manual_sources_a.json", "manual_sources_b.json", "manual_sources_c.json"):
        path = BASE_DIR / name
        if not path.exists():
            continue
        records = json.loads(path.read_text())
        if not isinstance(records, dict) or not all(
            isinstance(title, str) and isinstance(url, str) and url.startswith(("https://", "http://"))
            for title, url in records.items()
        ):
            raise RuntimeError(f"Invalid targeted verification file: {path}")
        sources.update(records)
    return sources


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(character for character in value if not unicodedata.combining(character))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.casefold())).strip()


def key(work: dict[str, object]) -> tuple[str, str, int, str]:
    return normalized(str(work["title"])), normalized(str(work["creator"])), int(work["year"]), str(work["medium"])


def main() -> None:
    works = json.loads((AUDIT_DIR / "singletons.json").read_text())
    automatic = json.loads((AUDIT_DIR / "singleton-verification.json").read_text())
    automatic_records_by_key = {key(record["work"]): record for record in automatic}
    automatic_by_key = {
        key(record["work"]): record for record in automatic if record.get("status") == "verified"
    }
    targeted_sources = manual_sources()
    results = []
    automatic_count = 0
    manual_count = 0
    missing = []
    for work in works:
        record = automatic_by_key.get(key(work))
        if record:
            results.append({"work": work, "status": "verified_automatic", "evidence": record["evidence"]})
            automatic_count += 1
            continue
        composite_key = f'{work["title"]} — {work["creator"]} — {work["year"]} — {work["medium"]}'
        source = targeted_sources.get(composite_key) or targeted_sources.get(work["title"])
        if not source:
            missing.append(f'{work["title"]} — {work["creator"]} ({work["year"]}, {work["medium"]})')
            continue
        results.append({
            "work": work,
            "status": "verified_targeted",
            "evidence": {"source": "Targeted catalogue/reference verification", "url": source,
                         "basis": "title plus creator and/or release metadata"},
        })
        manual_count += 1
    if missing:
        raise RuntimeError("Unverified retained singletons:\n" + "\n".join(missing))
    current_automatic = [
        automatic_records_by_key.get(key(work), {"work": work, "status": "unverified"})
        for work in works
    ]
    (AUDIT_DIR / "singleton-verification.json").write_text(
        json.dumps(current_automatic, ensure_ascii=False, indent=2) + "\n"
    )
    (AUDIT_DIR / "singleton-verification-final.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n"
    )
    (AUDIT_DIR / "unverified-singletons.json").write_text("[]\n")
    exclusions = json.loads((AUDIT_DIR / "exclusions.json").read_text())
    summary = {
        "retained_singletons": len(results),
        "verified_automatically": automatic_count,
        "verified_with_targeted_sources": manual_count,
        "unverified_retained": 0,
        "excluded_records": len(exclusions),
        "exclusions": exclusions,
    }
    (AUDIT_DIR / "verification-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
