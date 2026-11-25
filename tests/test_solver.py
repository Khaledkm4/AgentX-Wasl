from datetime import date

import pytest

from wasl.schemas import Candidate, Need, PastWork, Practitioner, ScoreBreakdown
from wasl.solver import _avail, _overlap, solve

D = date.fromisoformat
ALL = [(D("2027-01-01"), D("2027-12-31"))]
CITY = "الرياض"
SB = ScoreBreakdown(specialty=0, past_work_similarity=0, location=0, budget=0, availability=0)


def P(id, city=CITY, remote=False, avail=ALL, rising=False, collab=()):
    return Practitioner(id=id, name=id, type="individual", specialties=["x"], sectors=["film"], city=city,
                        remote_ok=remote, price_min=1, price_max=1, availability=avail,
                        past_works=[PastWork(title="w", year=2024, role="r", description="d",
                                             collaborator_ids=list(collab))],
                        verified_license=True, is_rising_talent=rising)


def N(id, s="2027-02-01", e="2027-02-10", remote=False):
    return Need(id=id, role=id, sector="film", phase_window=(D(s), D(e)), remote_ok=remote)


def C(nid, pid, cost, score):
    return Candidate(practitioner_id=pid, need_id=nid, estimated_cost=cost, score=score, score_breakdown=SB,
                     is_available=True, location_match=True)


def run(needs, cands, budget, prs, **prefs):
    by = {n.id: [c for c in cands if c.need_id == n.id] for n in needs}
    return solve(needs, by, budget, prefs={"city": CITY, "rising_talent": "off", **prefs},
                 practitioners={p.id: p for p in prs})


def test_within_budget_picks_best_affordable():
    # (a,c) best but costs 1200; affordable: (a,d)=1.5 vs (b,c)=1.6 -> (b,c)
    needs = [N("n1"), N("n2", "2027-03-01", "2027-03-05")]
    prs = [P(i) for i in "abcd"]
    cands = [C("n1", "a", 600, 0.9), C("n1", "b", 300, 0.7), C("n2", "c", 600, 0.9), C("n2", "d", 300, 0.6)]
    r = run(needs, cands, 1000, prs)
    assert r.feasible and r.team.total_cost <= 1000
    assert r.team.assignments == {"n1": "b", "n2": "c"} and r.team.total_cost == 900


def test_max_one_role_per_practitioner_even_across_disjoint_phases():
    prs = [P("a"), P("b"), P("c")]
    cands = lambda: [C("n1", "a", 10, 0.9), C("n1", "b", 10, 0.5), C("n2", "a", 10, 0.9), C("n2", "c", 10, 0.5)]
    for n2 in (N("n2", "2027-02-05", "2027-02-20"), N("n2", "2027-03-01", "2027-03-10")):
        r = run([N("n1"), n2], cands(), 100, prs)
        assert r.feasible and len(set(r.team.assignments.values())) == 2
    # a is the only candidate for both roles -> infeasible, not double-hired
    r = run([N("n1"), N("n2", "2027-03-01", "2027-03-10")], [C("n1", "a", 10, 0.9), C("n2", "a", 10, 0.9)], 100,
            [P("a")])
    assert not r.feasible and any("double-booking" in b for b in r.blocking_constraints)


def test_backups_distinct_across_roles_and_never_team_members():
    needs = [N("n1"), N("n2", "2027-03-01", "2027-03-05")]
    prs = [P(i) for i in "abxy"]
    cands = [C("n1", "a", 10, 0.9), C("n1", "x", 10, 0.8), C("n1", "y", 10, 0.7), C("n1", "b", 10, 0.1),
             C("n2", "b", 10, 0.9), C("n2", "x", 10, 0.85), C("n2", "y", 10, 0.5), C("n2", "a", 10, 0.1)]
    t = run(needs, cands, 100, prs).team
    assert t.assignments == {"n1": "a", "n2": "b"}
    assert set(t.backups.values()).isdisjoint(t.assignments.values())
    assert t.backups == {"n1": "x", "n2": "y"}  # x already backs n1 -> n2 prefers a distinct backup


def test_backups_are_valid():
    needs = [N("n1"), N("n2", "2027-02-05", "2027-02-20")]
    busy = [(D("2027-03-01"), D("2027-03-31"))]
    prs = [P("a"), P("b"), P("c", avail=busy), P("d", city="جدة"), P("e"), P("f")]
    cands = [C("n1", "a", 50, 0.9), C("n1", "c", 10, 0.99), C("n1", "d", 10, 0.98), C("n1", "f", 80, 0.97),
             C("n1", "b", 40, 0.6), C("n2", "e", 40, 0.9), C("n2", "a", 10, 0.95)]
    r = run(needs, cands, 100, prs)
    t, by = r.team, {p.id: p for p in prs}
    assert r.feasible and t.total_cost <= 100
    for nid, pid in t.backups.items():
        need = next(n for n in needs if n.id == nid)
        assert pid != t.assignments[nid] and _avail(by[pid], need.phase_window) and by[pid].city == CITY
        assert t.total_cost - next(c.estimated_cost for c in cands if c.need_id == nid and c.practitioner_id == t.assignments[nid]) \
            + next(c.estimated_cost for c in cands if c.need_id == nid and c.practitioner_id == pid) <= 100
        others = [m for m in needs if m.id != nid and _overlap(m.phase_window, need.phase_window)]
        assert all(t.assignments[m.id] != pid for m in others)
    # primary f+a (score 1.92, cost 90); n1 backup: c unavailable, d wrong city, a busy on overlapping n2 -> b
    assert t.assignments == {"n1": "f", "n2": "a"} and t.backups["n1"] == "b"
    assert "n2" not in t.backups  # e (40) exceeds remaining room (20)


def test_rising_talent_slot():
    needs = [N("n1"), N("n2", "2027-03-01", "2027-03-05")]
    prs = [P("a"), P("b"), P("r", rising=True)]
    cands = [C("n1", "a", 10, 0.9), C("n1", "r", 10, 0.5), C("n2", "b", 10, 0.9)]
    assert run(needs, cands, 100, prs).team.assignments["n1"] == "a"
    hard = run(needs, cands, 100, prs, rising_talent="hard")
    assert hard.team.assignments["n1"] == "r" and "rising talent" in " ".join(hard.team.notes)
    soft = run(needs, cands, 100, prs, rising_talent="soft", rising_bonus=60)
    assert soft.team.assignments["n1"] == "a"  # 400-point gap > soft bonus


def test_collaboration_bonus_flips_close_tie():
    needs = [N("n1"), N("n2", "2027-03-01", "2027-03-05")]
    prs = [P("a", collab=["c"]), P("b"), P("c")]
    cands = [C("n1", "a", 10, 0.80), C("n2", "b", 10, 0.80), C("n2", "c", 10, 0.79)]
    assert run(needs, cands, 100, prs, collab_bonus=0).team.assignments["n2"] == "b"
    r = run(needs, cands, 100, prs)
    assert r.team.assignments["n2"] == "c" and any("worked together" in n for n in r.team.notes)


def test_infeasible_budget_returns_exact_extra():
    needs = [N("n1"), N("n2", "2027-03-01", "2027-03-05")]
    prs = [P("a"), P("b"), P("c")]
    cands = [C("n1", "a", 500, 0.9), C("n1", "b", 400, 0.5), C("n2", "c", 300, 0.9)]
    r = run(needs, cands, 600, prs)
    assert not r.feasible and r.team is None
    assert any(b.startswith("budget") for b in r.blocking_constraints)
    extra = [c for c in r.min_concessions if c.kind == "extra_budget_sar"]
    assert extra and extra[0].value == 100


def test_infeasible_availability_returns_min_shift():
    prs = [P("a", avail=[(D("2027-02-15"), D("2027-03-31"))]), P("b", avail=[(D("2027-02-20"), D("2027-03-31"))])]
    cands = [C("n1", "a", 10, 0.9), C("n1", "b", 10, 0.9)]
    r = run([N("n1")], cands, 100, prs)
    assert not r.feasible and "no candidate available" in r.blocking_constraints[0]
    shift = [c for c in r.min_concessions if c.kind == "shift_days"]
    assert shift and shift[0].value == 14  # 2027-02-01 -> 2027-02-15


def test_infeasible_location_returns_remote_concession():
    prs = [P("a", city="جدة", remote=True), P("b", city=CITY)]
    cands = [C("n1", "a", 10, 0.9), C("n2", "b", 10, 0.9)]
    r = run([N("n1"), N("n2", "2027-03-01", "2027-03-05")], cands, 100, prs)
    assert not r.feasible
    rem = [c for c in r.min_concessions if c.kind == "allow_remote_needs"]
    assert rem and rem[0].value == ["n1"]


# ---------- end-to-end: retrieval -> solver on the seeded DB ----------
@pytest.mark.e2e
@pytest.mark.parametrize("case", ["film", "fashion", "heritage"])
def test_e2e_search_then_solve(case):
    from wasl import retrieval
    from wasl.samples import CASES
    card = CASES[case]
    prs = retrieval.practitioners()
    cands = retrieval.search_all(card.needs, card)
    for n in card.needs:
        assert cands[n.id] and all(c.practitioner_id in prs and n.sector in prs[c.practitioner_id].sectors
                                   for c in cands[n.id])
    r = solve(card.needs, cands, card.budget.value, prefs={"city": card.city.value}, practitioners=prs)
    assert r.feasible and r.team.total_cost <= card.budget.value
    assert set(r.team.assignments) == {n.id for n in card.needs}
    for n in card.needs:
        p = prs[r.team.assignments[n.id]]
        assert _avail(p, n.phase_window) and (p.city == card.city.value or (p.remote_ok and n.remote_ok))


@pytest.mark.e2e
def test_e2e_tight_budget_concession():
    from wasl import retrieval
    from wasl.samples import CASES, TIGHT_BUDGET
    card = CASES["heritage"]
    cands = retrieval.search_all(card.needs, card)
    r = solve(card.needs, cands, TIGHT_BUDGET, prefs={"city": card.city.value}, practitioners=retrieval.practitioners())
    assert not r.feasible
    extra = next(c for c in r.min_concessions if c.kind == "extra_budget_sar")
    assert extra.value > 0
    r2 = solve(card.needs, cands, TIGHT_BUDGET + extra.value, prefs={"city": card.city.value},
               practitioners=retrieval.practitioners())
    assert r2.feasible  # concession is exactly sufficient
    r3 = solve(card.needs, cands, TIGHT_BUDGET + extra.value - 1, prefs={"city": card.city.value},
               practitioners=retrieval.practitioners())
    assert not r3.feasible  # ...and minimal
