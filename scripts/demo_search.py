import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import wasl.config  # noqa: F401  pins caches/temp to D: before torch/HF load

from wasl import retrieval
from wasl.samples import CASES

for name, card in CASES.items():
    print(f"\n=== {name}: {card.city.value} | budget {card.budget.value} SAR ===")
    res = retrieval.search_all(card.needs, card, k=5)
    for need in card.needs:
        print(f"- {need.id} [{need.role}]")
        for c in res[need.id]:
            p = retrieval.practitioners()[c.practitioner_id]
            b = c.score_breakdown
            flags = ("" if c.is_available else " UNAVAILABLE") + ("" if c.location_match else " LOC-MISMATCH")
            print(f"    {c.score:.3f} {p.id} {p.name} ({p.city}) ~{c.estimated_cost} SAR | spec {b.specialty:.2f} "
                  f"works {b.past_work_similarity:.2f} loc {b.location:.1f} bud {b.budget:.2f} avail {b.availability:.2f}{flags}")
print("\nmodels:", retrieval.active_models(), "| fallbacks:", retrieval.FALLBACKS_USED or "none")
