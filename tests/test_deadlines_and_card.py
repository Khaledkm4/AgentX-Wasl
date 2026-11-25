"""Critical deadlines, editable start / official show dates, member-card facts, gender + DB migration."""
import sqlite3
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from tests.test_agents_and_api import DownLLM, TODAY, _stub_search, orch, staged
from tests.test_solver import N, P
from wasl import agents, db, deadlines
from wasl.orchestrator import FlowError

D = date.fromisoformat


# ---------------------------------------------------------------- pure deadline rules
def test_availability_alert_says_how_far_the_project_can_slip():
    busy = P("busy", avail=[(D("2027-01-01"), D("2027-02-20"))])  # role window ends 2027-02-10 -> 10 days slack
    free = P("free")                                               # whole year: nothing to report
    out = deadlines.availability_alerts([("مخرج", busy, N("n1")), ("مونتير", free, N("n2"))], show=None)
    assert len(out) == 1 and out[0]["kind"] == "availability" and out[0]["days"] == 10
    assert out[0]["severity"] == "high" and "لا يمكن تمديد المشروع أكثر من 10 أيام" in out[0]["ar"]
    assert "2027-02-20" in out[0]["ar"] and "10 days" in out[0]["en"]
    gone = P("gone", avail=[(D("2027-01-01"), D("2027-02-05"))])  # not available for the whole role window
    assert deadlines.availability_alerts([("مخرج", gone, N("n1"))], None)[0]["severity"] == "high"


def test_permit_and_show_alerts_follow_start_and_show_dates():
    st = staged("fashion")  # start 2027-02-01, deadline 2027-04-20, playbook permits anchored on the show
    st.card.show_date.value, st.card.show_date.status = D("2027-05-01"), "known"
    out = deadlines.compute(st.card, st.card.needs, agents.load_playbook("fashion"), TODAY)
    permits = [a for a in out if a["kind"] == "permit"]
    assert {a["date"] for a in permits} == {"2027-04-10", "2027-03-17"}  # show - 21 days, show - 45 days
    assert all("يجب إنجازه قبل" in a["ar"] for a in permits)
    show = next(a for a in out if a["kind"] == "show")
    assert show["severity"] == "info" and show["days"] == 11
    st.card.show_date.value = D("2027-04-15")  # show before the work ends -> critical
    show = next(a for a in deadlines.show_alerts(st.card) if a["kind"] == "show")
    assert show["severity"] == "high" and show["days"] == -5


# ---------------------------------------------------------------- orchestrator: card edits re-plan everything
def test_start_date_edit_shifts_schedule_resolves_and_recomputes():
    o = orch(DownLLM(), search=_stub_search)
    st = o.build_team(staged("film"))
    assert st.status == "built"
    before = {n.id: n.phase_window for n in st.card.needs}
    dl0, start0 = st.card.deadline.value, st.card.start_date.value
    st = o.update_card(st, start_date=start0 + timedelta(7))
    assert st.card.start_date.value == start0 + timedelta(7) and st.card.start_date.status == "known"
    assert st.card.deadline.value == dl0 + timedelta(7)
    assert all(n.phase_window == (before[n.id][0] + timedelta(7), before[n.id][1] + timedelta(7)) for n in st.card.needs)
    assert st.status in ("built", "infeasible") and any("card edited" in e for e in st.events)

    st = o.update_card(st, show_date=dl0 + timedelta(20))
    v = o.view(st)
    assert v["card"]["show_date"] == {"value": str(dl0 + timedelta(20)), "status": "known"}
    kinds = {a["kind"] for a in v["deadlines"]}
    assert {"permit", "show"} <= kinds
    if v["status"] == "built":
        assert "يوم العرض الرسمي" in v["brief"] and v["project_span"]["show"] == str(dl0 + timedelta(20))
    with pytest.raises(FlowError):
        o.update_card(st, show_date=start0 - timedelta(30))


def test_deadline_edit_rescales_role_windows():
    o = orch(DownLLM(), search=_stub_search)
    st = staged("heritage")
    s, old = st.card.start_date.value, st.card.deadline.value
    st = o.update_card(st, deadline=s + timedelta((old - s).days * 2))
    assert st.card.deadline.status == "known"
    assert all(s <= n.phase_window[0] <= n.phase_window[1] <= st.card.deadline.value for n in st.card.needs)
    assert max(n.phase_window[1] for n in st.card.needs) > old
    with pytest.raises(FlowError):
        o.update_card(st, deadline=s)


def test_built_view_has_actionable_member_facts():
    o = orch(DownLLM(), search=_stub_search)
    v = o.view(o.build_team(staged("film")))
    assert v["status"] == "built"
    for m in v["team"]:
        assert 0 < m["budget_share"] < 1 and abs(m["budget_share"] - m["estimated_cost"] / v["budget"]) < 1e-3
        assert m["location"]["kind"] in ("local", "remote", "out_of_scope")
        a = m["availability"]
        assert isinstance(a["full"], bool) and a["role_from"] <= a["role_to"]
        assert m["practitioner"]["gender"] in ("male", "female", None)
    assert any("من الميزانية" in line for line in v["brief"].splitlines())


# ---------------------------------------------------------------- data: gender + automatic migration
def test_seeded_gender_and_migration_of_old_db(tmp_path):
    prs = db.load_practitioners(db.connect())
    assert prs["f02"].gender == "female" and prs["f01"].gender == "male" and prs["s03"].gender is None
    assert any(p.availability[-1][1] < D("2027-06-01") for p in prs.values())  # some get busy early
    assert any(p.availability == [(D("2026-12-01"), D("2027-12-31"))] for p in prs.values())  # some fully free

    path = tmp_path / "old.db"
    con = sqlite3.connect(path)  # schema from before the gender column existed
    con.execute("CREATE TABLE practitioners (id TEXT PRIMARY KEY, data TEXT NOT NULL, is_demo INTEGER NOT NULL DEFAULT 1)")
    old = prs["f02"].model_copy(update={"gender": None})
    con.execute("INSERT INTO practitioners (id, data) VALUES (?, ?)", (old.id, old.model_dump_json()))
    con.commit()
    con.close()
    con = db.connect(path)
    assert "gender" in {r[1] for r in con.execute("PRAGMA table_info(practitioners)")}
    con.execute("UPDATE practitioners SET gender = 'female' WHERE id = 'f02'")
    assert db.load_practitioners(con)["f02"].gender == "female"


def test_api_card_edit_endpoint(monkeypatch):
    from wasl import api
    monkeypatch.setenv("WASL_PRELOAD", "0")
    api.app.state.orch = orch(DownLLM(), search=_stub_search)
    try:
        with TestClient(api.app) as c:
            api.SESSIONS["dl"] = staged("fashion")
            r = c.post("/api/sessions/dl/build-team", json={}).json()
            assert r["status"] == "built" and "deadlines" in r
            r = c.post("/api/sessions/dl/card", json={"start_date": "2027-02-08", "show_date": "2027-05-05"}).json()
            assert r["card"]["start_date"] == {"value": "2027-02-08", "status": "known"}
            assert r["card"]["show_date"]["value"] == "2027-05-05" and r["deadlines"]
            assert c.post("/api/sessions/dl/card", json={"show_date": "2026-01-01"}).status_code == 409
            p = next(x for x in c.get("/api/practitioners").json() if x["id"] == "s01")
            assert p["gender"] == "female" and p["availability"]
    finally:
        api.SESSIONS.pop("dl", None)
        api.app.state.orch = None
