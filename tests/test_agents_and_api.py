"""Agents + orchestrator + API with a mocked LLM (zero API cost). Retrieval/solver/DB are real."""
import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from wasl import agents
from wasl.agents import (ClarifierOut, ExplainOut, LLM, LLMError, NeedDraft, RequirementsOut, check_team,
                         heuristic_extract)
from wasl.orchestrator import FlowError, Orchestrator, SessionState
from wasl.samples import CASES, TIGHT_BUDGET

TODAY = date(2026, 12, 1)
OUTSIDER = "طلال الحربي"  # h01: heritage practitioner, never on a film team


class FakeLLM:
    enabled = True

    def __init__(self, bad_explain: int = 0):
        self.calls, self.bad_explain = [], bad_explain

    def structured(self, system, user, schema, fast=False):
        self.calls.append(schema.__name__)
        d = json.loads(user)
        if schema is ClarifierOut:
            return ClarifierOut(extracted=heuristic_extract(d["latest_message"]), ask_field=d["ask_field"],
                                question="سؤال؟", quick_replies=["أ", "ب", "ما أدري"])
        if schema is RequirementsOut:
            return RequirementsOut(needs=[NeedDraft(
                role=n.role, reason=n.reason, consequence_if_ignored=n.consequence_if_ignored,
                importance=n.importance, confidence=n.confidence, phase=n.phase, start=n.phase_window[0],
                end=n.phase_window[1], remote_ok=n.remote_ok, mentioned=n.mentioned)
                for n in CASES[d["card"]["sector"]["value"]].needs])
        if schema is ExplainOut:
            bad = self.bad_explain > 0
            self.bad_explain -= bad
            ex = {m["need_id"]: f"{m['name']} مناسب لدور {m['role']} بعد «{m['past_works'][0]['title']}»."
                  for m in d["members"]}
            if bad and ex:
                k = next(iter(ex))
                ex[k] += f" وسبق له العمل مع {OUTSIDER} في «فيلم مخترع»."
            return ExplainOut(explanations=ex, brief_intro="فيلم وثائقي قصير عن الحرف اليدوية." if d["need_brief_intro"] else "")
        raise AssertionError(schema)


class DownLLM:
    enabled = False

    def structured(self, *a, **kw):
        raise LLMError("offline")


class Counter:
    def __init__(self):
        from wasl import retrieval
        self.fn, self.n = retrieval.search_all, 0

    def __call__(self, needs, card):
        self.n += 1
        return self.fn(needs, card)


def orch(llm=None, search=None):
    return Orchestrator(llm or FakeLLM(), search=search, today=TODAY)


def staged(case: str, budget: int | None = None) -> SessionState:
    card = CASES[case].model_copy(deep=True)
    if budget is not None:
        card.budget.value = budget
    return SessionState(id="t", idea="مشروع تجريبي", card=card, status="needs_review")


# ---------------------------------------------------------------- unit: LLM wrapper + clarifier
def test_llm_structured_strips_fences_and_retries_invalid_json():
    class Stub(LLM):
        def __init__(self):
            super().__init__(api_key="x")
            self.replies = ['{"needs": "oops"}', '```json\n{"needs": []}\n```']

        def _call(self, msgs, model):
            return self.replies.pop(0)

    assert Stub().structured("s", "u", RequirementsOut).needs == []


def test_heuristic_extract():
    ex = heuristic_extract("معرض تراثي في العلا بميزانية ١٢٠ ألف ريال من 2027-02-15 إلى 2027-04-25")
    assert (ex.sector, ex.city, ex.budget) == ("heritage", "العلا", 120000)
    assert (ex.start_date, ex.deadline) == (date(2027, 2, 15), date(2027, 4, 25))


def test_clarifier_unsure_assumed_and_turn_cap():
    o = orch()
    st = o.start("مشروع")  # nothing extractable
    assert st.status == "clarifying" and st.pending_field == "sector" and 2 <= len(st.quick_replies) <= 4
    st = o.message(st, "ما أدري")
    assert st.card.sector.status == "assumed" and st.pending_field == "budget"
    for _ in range(3):
        st = o.message(st, "همم")
    assert st.turns == 5 and st.status == "clarifying"  # practical questions capped at 5 turns ...
    assert st.pending_field == "style" and agents.SUGGEST_STYLE in st.quick_replies  # ... then the final style step
    st = o.message(st, agents.NO_STYLE)
    assert st.status == "needs_review" and st.card.style.value == agents.NO_STYLE_VALUE
    assert all(getattr(st.card, f).value is not None for f in agents.CORE)
    assert {getattr(st.card, f).status for f in ("budget", "city", "deadline")} == {"assumed"}


def test_quick_reply_parsed_without_llm():
    llm = FakeLLM()
    o = orch(llm)
    st = o.start("فيلم وثائقي في الأحساء")
    assert st.pending_field == "budget"
    n = len(llm.calls)
    st = o.message(st, "حوالي 100 ألف")
    assert st.card.budget.value == 100000 and st.card.budget.status == "known" and len(llm.calls) == n


# ---------------------------------------------------------------- unit: requirements
def test_requirements_fields_and_window_clamp():
    o = orch()
    st = o.start("فيلم وثائقي في الأحساء بميزانية 120 ألف ريال من 2027-01-20 إلى 2027-03-01")
    assert st.status == "clarifying" and st.pending_field == "style"  # all facts given: only the style step left
    st = o.message(st, "عصري بلمسة تراثية")
    assert st.card.style.value == "عصري بلمسة تراثية" and st.style_notes == "عصري بلمسة تراثية"
    assert st.status == "needs_review" and len(st.card.needs) == 4
    for n in st.card.needs:
        assert date(2027, 1, 20) <= n.phase_window[0] <= n.phase_window[1] <= date(2027, 3, 1)
        assert n.reason and (n.mentioned or n.consequence_if_ignored)
    assert any(not n.mentioned for n in st.card.needs)


def test_requirements_playbook_fallback_when_llm_down():
    o = orch(DownLLM())
    st = o.start("معرض تراثي في العلا بميزانية 100 ألف ريال من 2027-02-15 إلى 2027-04-25")
    st = o.message(st, agents.SUGGEST_STYLE)  # LLM down -> grounded per-sector creative direction
    assert st.card.style.status == "assumed" and st.card.style.value and st.card.style.value in st.style_rationale
    assert st.status == "needs_review" and st.card.needs
    assert all(n.sector == "heritage" and n.phase for n in st.card.needs)


# ---------------------------------------------------------------- e2e (real retrieval + solver)
@pytest.mark.e2e
def test_tight_budget_concession_and_coordinator_guard():
    o = orch()
    st = o.build_team(staged("heritage", TIGHT_BUDGET))
    assert st.status == "infeasible" and st.blocking and "ريال" in " ".join(st.blocking)
    c = next(c for c in st.concessions if c.kind == "extra_budget_sar")
    assert "زيادة الميزانية" in c.label
    st = o.apply_concession(st, c.id)
    assert st.status == "built" and st.check["ok"] and st.result.team.total_cost <= o.budget(st)
    for _ in range(2):  # guard: at most 2 concessions per build
        st = o.what_if(st, budget=TIGHT_BUDGET)
        assert st.status == "infeasible"
        if st.retries["coordinator"] < 2:
            st = o.apply_concession(st, st.concessions[0].id)
    with pytest.raises(FlowError):
        o.apply_concession(st, st.concessions[0].id)


@pytest.mark.e2e
def test_final_check_guard_regenerates_then_falls_back_to_templates():
    llm = FakeLLM(bad_explain=1)
    st = orch(llm).build_team(staged("film"))
    assert st.check["ok"] and llm.calls.count("ExplainOut") == 2  # 1 retry fixed it
    assert not any(OUTSIDER in t for t in st.explanations.values())

    llm = FakeLLM(bad_explain=5)
    o = orch(llm)
    st = o.build_team(staged("film"))
    assert st.check["ok"] and llm.calls.count("ExplainOut") == 2  # max 1 retry, then grounded templates
    assert not any(OUTSIDER in t or "فيلم مخترع" in t for t in st.explanations.values())
    assert any("grounding issues" in e for e in st.events)

    bad = st.result.model_copy(deep=True)
    bad.team.total_cost = 10 ** 7
    assert any("budget" in i for i in check_team(bad, o.needs(st), o.budget(st), "الأحساء", st.candidates_pool, o.prs))
    bad.team.assignments["n1" if "n1" in bad.team.assignments else next(iter(bad.team.assignments))] = "ghost"
    assert any("not in DB" in i for i in check_team(bad, o.needs(st), o.budget(st), "الأحساء", st.candidates_pool, o.prs))


@pytest.mark.e2e
def test_whole_flow_runs_with_llm_down():
    o = orch(DownLLM())
    st = o.start("فيلم وثائقي عن الحرف في الأحساء بميزانية 150 ألف ريال من 2027-01-10 إلى 2027-03-25")
    st = o.message(st, "ما أدري")  # style: unsure -> a suggested style is assumed
    assert st.status == "needs_review" and st.card.style.status == "assumed"
    st = o.build_team(st)
    assert st.status in ("built", "infeasible")
    if st.status == "built":
        assert st.check["ok"] and all(st.explanations.values()) and st.brief


@pytest.fixture(scope="module")
def client():
    from wasl import api
    counter = Counter()
    api.app.state.orch = orch(FakeLLM(), search=counter)
    with TestClient(api.app) as c:
        c.counter = counter
        yield c
    api.app.state.orch = None


@pytest.mark.e2e
def test_api_full_flow(client):
    assert client.get("/api/health").json()["models_loaded"] is True

    # intake -> clarify ("ما أدري" -> assumed) -> requirements
    r = client.post("/api/sessions", json={"idea": "أبغى أسوي فيلم وثائقي قصير عن الحرف اليدوية في الأحساء "
                                                    "والميزانية 120 ألف ريال", "style_notes": "إضاءة طبيعية"}).json()
    sid = r["session_id"]
    assert r["status"] == "clarifying" and r["question"] and 2 <= len(r["quick_replies"]) <= 4
    assert r["card"]["sector"] == {"value": "film", "status": "known"}
    assert r["card"]["budget"] == {"value": 120000, "status": "known"}
    r = client.post(f"/api/sessions/{sid}/message", json={"text": "ما أدري"}).json()
    assert r["status"] == "needs_review" and r["card"]["deadline"]["status"] == "assumed"
    assert len(r["needs"]) == 4 and all("consequence_if_ignored" in n for n in r["needs"])
    assert client.post(f"/api/sessions/{sid}/message", json={"text": "x"}).status_code == 409

    # build team
    r = client.post(f"/api/sessions/{sid}/build-team", json={}).json()
    assert r["status"] == "built" and r["check"]["ok"], r.get("check")
    assert len(r["team"]) == 4 and r["total_cost"] <= r["budget"]
    assert all(m["explanation"] and m["backup"] for m in r["team"])  # every role has a backup (incl. dp/sound)
    assert r["timeline"] and "الفريق:" in r["brief"] and client.counter.n == 1

    # what-if: solver only, no retrieval rerun
    r = client.post(f"/api/sessions/{sid}/what-if", json={"budget": 200000}).json()
    assert r["status"] == "built" and r["budget"] == 200000 and client.counter.n == 1

    # simulate a member declining -> backup swaps in
    before = {m["need_id"]: m for m in r["team"]}
    r = client.post(f"/api/sessions/{sid}/reject/n2").json()
    after = {m["need_id"]: m for m in r["team"]}
    assert after["n2"]["practitioner"]["id"] == before["n2"]["backup"]["id"]
    assert after["n2"]["practitioner"]["name"] in after["n2"]["explanation"]
    assert r["total_cost"] == sum(m["estimated_cost"] for m in r["team"]) and r["check"]["ok"]
    assert before["n2"]["practitioner"]["id"] not in {m["practitioner"]["id"] for m in r["team"]}

    # tight budget -> infeasible -> concession -> feasible
    r = client.post(f"/api/sessions/{sid}/what-if", json={"budget": 30000}).json()
    assert r["status"] == "infeasible" and r["blocking"] and r["concessions"]
    c = next(c for c in r["concessions"] if c["kind"] == "extra_budget_sar")
    r = client.post(f"/api/sessions/{sid}/apply-concession", json={"concession_id": c["id"]}).json()
    assert r["status"] == "built" and r["budget"] == 30000 + c["value"] and r["total_cost"] <= r["budget"]
    assert r["check"]["ok"] and client.counter.n == 1

    assert client.post("/api/sessions/nope/build-team", json={}).status_code == 404


def test_ui_served(monkeypatch):
    from wasl import api
    monkeypatch.setenv("WASL_PRELOAD", "0")  # skip model loading: fast test
    api.app.state.orch = orch(DownLLM())
    with TestClient(api.app) as c:
        r = c.get("/")
        assert r.status_code == 200 and "وصل" in r.text and "/static/app.js" in r.text
        js = c.get("/static/app.js")
        assert js.status_code == 200 and "/api/sessions" in js.text
        import re
        for path in sorted(set(re.findall(r'/static/assets/[\w./-]+', r.text))):  # logo, flag, icons, fonts
            a = c.get(path)
            assert a.status_code == 200 and len(a.content) > 500, path
    api.app.state.orch = None


def test_requirement_roles_restricted_to_playbook():
    typical = [r["role"] for r in agents.load_playbook("film")["typical_roles"]]
    assert agents._canon_role("مدير تصوير سينمائي", typical) == "مدير تصوير"
    assert agents._canon_role("مخرج أفلام وثائقية", typical) == "مخرج"
    assert agents._canon_role("مترجم ومعد ترجمة", typical) is None


# ---------------------------------------------------------------- pins (suggested members) + practitioners API
def _stub_search(needs, card):
    """Fast, model-free stand-in for retrieval: every same-sector practitioner, uniform score."""
    from wasl.schemas import Candidate, ScoreBreakdown
    from wasl.retrieval import est_cost
    from wasl import db
    prs = db.load_practitioners(db.connect())
    sb = ScoreBreakdown(specialty=0.5, past_work_similarity=0.5, location=1, budget=1, availability=1)
    return {n.id: [Candidate(practitioner_id=p.id, need_id=n.id, estimated_cost=est_cost(p), score=0.5,
                             score_breakdown=sb, is_available=True, location_match=True)
                   for p in prs.values() if n.sector in p.sectors] for n in needs}


def test_solver_pin_is_hard_and_team_is_built_around_it():
    from tests.test_solver import C, N, P, run
    needs = [N("n1"), N("n2", "2027-03-01", "2027-03-05")]
    prs = [P("a"), P("b", collab=["d"]), P("c"), P("d")]
    cands = [C("n1", "a", 50, 0.9), C("n1", "b", 70, 0.5), C("n2", "c", 20, 0.6), C("n2", "d", 30, 0.58)]
    free = run(needs, cands, 100, prs)
    assert free.team.assignments == {"n1": "a", "n2": "c"}
    from wasl.solver import solve
    by = {n.id: [c for c in cands if c.need_id == n.id] for n in needs}
    r = solve(needs, by, 100, prefs={"city": "الرياض", "rising_talent": "off"},
              practitioners={p.id: p for p in prs}, pins={"n1": "b"})
    assert r.feasible and r.team.assignments == {"n1": "b", "n2": "d"}  # pinned b, collaborator d via synergy
    assert r.team.total_cost == 100 and any("collaboration bonus" in x for x in r.team.notes)
    r = solve(needs, by, 90, prefs={"city": "الرياض", "rising_talent": "off"},
              practitioners={p.id: p for p in prs}, pins={"n1": "b"})
    assert r.feasible and r.team.assignments == {"n1": "b", "n2": "c"}  # remaining budget 20 -> only c fits


def test_api_practitioners_and_build_team_with_pins(monkeypatch):
    from wasl import api
    from wasl.orchestrator import Pin
    monkeypatch.setenv("WASL_PRELOAD", "0")
    api.app.state.orch = orch(DownLLM(), search=_stub_search)
    with TestClient(api.app) as c:
        prs = c.get("/api/practitioners").json()
        assert len(prs) >= 30
        f01 = next(p for p in prs if p["id"] == "f01")
        assert {"id", "name", "specialty", "city", "typical_fee_min", "typical_fee_max", "is_rising_talent",
                "past_works"} <= set(f01) and f01["past_works"][0]["title"]
        assert f01["typical_fee_min"] <= f01["typical_fee_max"]

        api.SESSIONS["pin"] = staged("film")
        pins = [{"need_id": "film_dir", "practitioner_id": "f01"},
                {"need_id": "film_sound", "name": "سارة المستقلة", "estimated_cost": 9000}]
        r = c.post("/api/sessions/pin/build-team", json={"pins": pins}).json()
        assert r["status"] == "built" and r["check"]["ok"], r.get("check")
        team = {m["need_id"]: m for m in r["team"]}
        assert team["film_dir"]["practitioner"]["id"] == "f01" and team["film_dir"]["pinned"]
        ext = team["film_sound"]
        assert ext["external"] and ext["practitioner"]["name"] == "سارة المستقلة" and ext["estimated_cost"] == 9000
        assert r["total_cost"] == sum(m["estimated_cost"] for m in r["team"]) <= r["budget"]
        assert {p["need_id"] for p in r["pins"]} == {"film_dir", "film_sound"}
        assert "سارة المستقلة" in r["brief"]

        # what-if: change pins (unpin the external person) -> solver re-staffs that role from the DB
        r = c.post("/api/sessions/pin/what-if", json={"pins": pins[:1]}).json()
        team = {m["need_id"]: m for m in r["team"]}
        assert r["status"] == "built" and not team["film_sound"]["external"]
        assert team["film_dir"]["practitioner"]["id"] == "f01"
        assert c.post("/api/sessions/pin/what-if", json={"pins": [{"need_id": "film_dir"}]}).status_code == 409
    api.SESSIONS.pop("pin", None)
    api.app.state.orch = None
