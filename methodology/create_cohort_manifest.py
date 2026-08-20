#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def main() -> None:
    config = json.loads((BASE_DIR / "cohort_config.json").read_text())
    agents = []
    for cohort, details in config.items():
        first, last = details["agent_numbers"]
        for number in range(first, last + 1):
            agents.append({
                "agent_number": number,
                "agent_id": f"scorer-{number:03d}",
                "cohort": cohort,
                "cohort_label": details["label"],
                "lens": details["lens"],
            })
    agents.sort(key=lambda item: item["agent_number"])
    if [item["agent_number"] for item in agents] != list(range(1, 101)):
        raise ValueError("cohort configuration must cover agent numbers 1 through 100 exactly once")
    manifest = {
        "generalist_agents": 35,
        "lens_assisted_agents": 65,
        "lens_instruction": (
            "Use the assigned lens to widen initial candidate discovery and counter familiarity bias. "
            "It is not a quota, eligibility restriction, score bonus, or limit on the final rankings. "
            "The final four selection lists must remain honest global top-100 judgments under the common rubric."
        ),
        "agents": agents,
    }
    (BASE_DIR / "cohort_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
