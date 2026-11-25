"""Latency config, contacts, hybrid clarifier, soft out-of-scope solver, post-build Advisor."""
import os
from datetime import date

from fastapi.testclient import TestClient

from tests.test_agents_and_api import DownLLM, FakeLLM, _stub_search, orch, staged
from tests.test_solver import C, N, P, run
from wasl import agents, config
from wasl.agents import AdvisorOut, LLM, check_team, heuristic_extract


# ---------------------------------------------------------------- 1. latency
def test_hf_strictly_offline_and_gemini_thinking_disabled(monkeypatch):
    assert not config.ALLOW_DOWNLOAD and os.environ["HF_HUB_OFFLINE"] == "1"
    assert os.environ["TRANSFORMERS_OFFLINE"] == "1"
    monkeypatch.delenv("LLM_REASONING_EFFORT", raising=False)
    llm = LLM(api_key="x", model="gpt-4o-mini", fast_model="gemini-2.5-flash")
    assert llm.effort_for("gemini-2.5-flash") == "none" and llm.effort_for("gpt-4o-mini") is None
    monkeypatch.setenv("LLM_REASONING_EFFORT", "low")
    assert LLM(api_key="x").effort_for("gemini-2.5-flash") == "low"


def test_llm_drops_reasoning_effort_if_provider_rejects_it():
    class Resp:
        choices = [type("c", (), {"message": type("m", (), {"content": '{"needs": []}'})()})()]

    class Client:
        def __init__(self):
            self.kw = []
            self.chat = type("x", (), {"completions": self})()

        def create(self, **kw):
            self.kw.append(kw)
            if "reasoning_effort" in kw:
                raise ValueError("Unknown parameter: reasoning_effort")
            return Resp()

    llm = LLM(api_key="x", model="gemini-2.5-flash")
    llm._client = Client()
    assert llm.structured("s", "u", agents.RequirementsOut).needs == []
    assert llm._effort is None and len(llm._client.kw) == 2  # one rejected call, then no more reasoning param
    assert "reasoning_effort" not in llm._client.kw[-1]


# ---------------------------------------------------------------- 3. hybrid clarifier
def test_hybrid_sector_detected_and_never_asked():
    ex = heuristic_extract("أبغى أسوي عرض أزياء تراثي في الرياض")
    assert ex.sector == "fashion" and ex.secondary_sectors == ["heritage"]
    for llm in (FakeLLM(), DownLLM()):
        st = orch(llm).start("أبغى أسوي عرض أزياء تراثي")
        assert st.card.sector.value == "fashion" and st.card.sector.status == "known"
        assert st.card.secondary_sectors == ["heritage"]
        assert st.pending_field != "sector"


def test_requirements_can_staff_secondary_sector_role():
    from wasl.agents import NeedDraft, RequirementsOut

    class HybridLLM(FakeLLM):
        def structured(self, system, user, schema, fast=False):
            if schema is RequirementsOut:
                return RequirementsOut(needs=[
                    NeedDraft(role="مصمم أزياء", reason="r", phase="design"),
                    NeedDraft(role="باحث تراث وأمين متحف", reason="r", phase="research", sector="heritage")])
            return super().structured(system, user, schema, fast)

    o = orch(HybridLLM())
    st = o.message(o.start("عرض أزياء تراثي في الرياض بميزانية 150 ألف ريال من 2027-02-01 إلى 2027-04-20"),
                   agents.NO_STYLE)
    assert st.status == "needs_review"
    by = {n.role: n for n in st.card.needs}
    assert by["مصمم أزياء"].sector == "fashion"
    h = by["باحث تراث وأمين متحف"]
    assert h.sector == "heritage" and h.phase in agents.load_playbook("fashion")["phases"]


# ---------------------------------------------------------------- 4. soft out-of-scope
def test_out_of_scope_is_soft_with_surcharge_not_infeasible():
    prs = [P("a", city="جدة", remote=True), P("b"), P("c", city="جدة")]
    cands = [C("n1", "a", 20000, 0.9), C("n2", "b", 10000, 0.9)]
    needs = [N("n1"), N("n2", "2027-03-01", "2027-03-05")]
    r = run(needs, cands, 40000, prs)
    assert r.feasible and r.team.assignments == {"n1": "a", "n2": "b"}
    o = r.team.out_of_scope["n1"]
    assert o.reason == "remote_preference" and o.surcharge == 1000 and o.base_cost == 20000  # +5%
    assert "خارج نطاق عمله المعتاد" in o.note_ar and "outside their usual" in o.note_en
    assert r.team.total_cost == 31000 and "n2" not in r.team.out_of_scope
    # on-site person from another city -> outside_city; minimum symbolic fee applies
    r = run([N("n1")], [C("n1", "c", 6000, 0.9)], 10000, prs)
    assert r.feasible and r.team.out_of_scope["n1"].reason == "outside_city"
    assert r.team.out_of_scope["n1"].surcharge == 500 and r.team.total_cost == 6500
    # an in-scope option is always preferred over a better-scoring out-of-scope one
    r = run(needs, cands + [C("n1", "c", 1000, 0.1), C("n1", "b2", 1000, 0.2)], 40000, prs + [P("b2")])
    assert r.team.assignments["n1"] == "b2" and not r.team.out_of_scope
    # the surcharge counts against the budget; hard mode keeps the old behaviour
    assert not run(needs, cands, 30500, prs).feasible
    assert not run(needs, cands, 40000, prs, out_of_scope="hard").feasible


def test_out_of_scope_passes_final_check_and_explainer_mentions_fee():
    from wasl.solver import solve
    prs = {p.id: p for p in [P("a", city="جدة", remote=True), P("b")]}
    needs = [N("n1"), N("n2", "2027-03-01", "2027-03-05")]
    cands = {"n1": [C("n1", "a", 20000, 0.9)], "n2": [C("n2", "b", 10000, 0.9)]}
    r = solve(needs, cands, 40000, prefs={"city": "الرياض"}, practitioners=prs)
    assert check_team(r, needs, 40000, "الرياض", cands, prs) == []
    f = agents.member_facts("n1", needs[0], prs["a"], cands["n1"][0], {"a", "b"}, prs, r.team.out_of_scope["n1"])
    assert agents.OOS_MARK in agents.template_explanation(f)
    assert agents.OOS_MARK in agents.explain(DownLLM(), [f], {}, False).explanations["n1"]


# ---------------------------------------------------------------- 2 + 5. contacts API, post-build Advisor
class AdvisorLLM(FakeLLM):
    def structured(self, system, user, schema, fast=False):
        if schema is AdvisorOut:
            self.calls.append("AdvisorOut")
            import json
            d = json.loads(user)
            assert d["project"]["team"] and d["project"]["budget_breakdown"] and d["project"]["playbook"]["phases"]
            return AdvisorOut(answer=f"ابدأ بـ{d['project']['team'][0]['member']}", quick_replies=["وبعدها؟"])
        return super().structured(system, user, schema, fast)


def test_contacts_exposed_and_chat_continues_after_build(monkeypatch):
    from wasl import api
    monkeypatch.setenv("WASL_PRELOAD", "0")
    llm = AdvisorLLM()
    api.app.state.orch = orch(llm, search=_stub_search)
    try:
        with TestClient(api.app) as c:
            prs = {p["id"]: p for p in c.get("/api/practitioners").json()}
            f01 = prs["f01"]["contact"]
            assert f01["phone"].startswith("+966") and "@" in f01["email"]
            assert f01["company"]["name"] and f01["company"]["website"].startswith("https://")
            assert all(p["contact"]["company"] for p in prs.values())

            api.SESSIONS["adv"] = staged("film")
            assert c.post("/api/sessions/adv/message", json={"text": "سؤال"}).status_code == 409  # needs_review
            r = c.post("/api/sessions/adv/build-team", json={}).json()
            assert r["status"] == "built"
            assert all(m["practitioner"]["contact"]["company"] for m in r["team"])
            r = c.post("/api/sessions/adv/message", json={"text": "وش أول خطوة؟"}).json()
            assert r["status"] == "built" and r["team"]  # not locked, team intact
            assert r["consultation"][-1]["role"] == "assistant" and r["consultation"][-1]["text"].startswith("ابدأ بـ")
            assert r["advisor_quick_replies"] == ["وبعدها؟"] and r["consultation_count"] == 2
            r = c.post("/api/sessions/adv/message", json={"text": "وبعدها؟"}).json()
            assert r["consultation_count"] == 4 and llm.calls.count("AdvisorOut") == 2
    finally:
        api.SESSIONS.pop("adv", None)
        api.app.state.orch = None


def test_advisor_fallback_is_grounded_when_llm_down():
    o = orch(DownLLM(), search=_stub_search)
    st = o.build_team(staged("film"))
    st = o.message(st, "كيف أوزع الميزانية؟")
    ans = st.consultation[-1]["text"]
    assert st.status == "built" and "ريال" in ans
    names = {o.prs[p].name for p in st.result.team.assignments.values() if p in o.prs}
    assert any(n in ans for n in names)
