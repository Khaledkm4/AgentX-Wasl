"""Manual: one real LLM flow (intake -> needs -> team). Skips cleanly when LLM_API_KEY is not set."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import wasl.config  # noqa: F401  pins caches/temp to D:

import os
import time

from wasl.agents import LLM
from wasl.orchestrator import Orchestrator

if not os.getenv("LLM_API_KEY"):
    print("LLM_API_KEY not set -> skipping live smoke test")
    sys.exit(0)

llm = LLM()
print(f"model={llm.model} fast={llm.fast_model} base={llm.base_url}")
o = Orchestrator(llm)
t = time.time()
st = o.start("أبغى أسوي فيلم وثائقي قصير عن الحرف اليدوية في الأحساء، ميزانيتي حوالي 120 ألف ريال",
             "إضاءة طبيعية وإيقاع هادئ")
while st.status == "clarifying":
    print(f"Q: {st.question}  {st.quick_replies}")
    ans = "ما أدري" if "ما أدري" in st.quick_replies else st.quick_replies[0]
    print(f"A: {ans}")
    st = o.message(st, ans)
print("card:", {k: v for k, v in st.card.model_dump(mode="json", exclude={"needs"}).items()})
for n in st.card.needs:
    print(f"  need {n.id}: {n.role} [{n.phase} {n.phase_window[0]}..{n.phase_window[1]}] mentioned={n.mentioned}")
st = o.build_team(st)
v = o.view(st)
print("status:", v["status"], "| check:", v.get("check"))
if v["status"] == "built":
    for m in v["team"]:
        print(f"  {m['role']}: {m['practitioner']['name']} ~{m['estimated_cost']} | {m['explanation']}")
    print(v["brief"])
else:
    print("blocking:", v["blocking"], "\nconcessions:", [c["label"] for c in v["concessions"]])
print(f"done in {time.time() - t:.1f}s")
