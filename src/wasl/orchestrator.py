"""Explicit state machine: clarifying -> needs_review -> (built | infeasible). All state lives in SessionState."""
import uuid
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel

from wasl import agents, db, deadlines, solver
from wasl.agents import ConcessionOption
from wasl.schemas import Candidate, Need, Practitioner, ProjectCard, ScoreBreakdown, SolveResult, TrackedField

MAX_COORDINATOR_RETRIES = 2
MAX_FINAL_RETRIES = 1


class Overrides(BaseModel):
    budget: int | None = None
    shift_days: int = 0
    remote_needs: list[str] = []


class Pin(BaseModel):
    """User-suggested member: a DB practitioner (practitioner_id) or an external person (name + optional fee)."""
    need_id: str
    practitioner_id: str | None = None
    name: str | None = None
    estimated_cost: int | None = None

    @property
    def pid(self) -> str:
        return self.practitioner_id or f"ext_{self.need_id}"


class TimelineItem(BaseModel):
    phase: str
    phase_ar: str
    start: date
    end: date
    roles: list[str]
    members: list[str]


class SessionState(BaseModel):
    id: str
    idea: str
    style_notes: str = ""
    style_rationale: str = ""  # the Clarifier's tailored style proposal ("اقترح لي طابع مناسب")
    status: Literal["clarifying", "needs_review", "built", "infeasible"] = "clarifying"
    card: ProjectCard = ProjectCard()
    history: list[dict] = []
    turns: int = 0
    pending_field: str | None = None
    question: str | None = None
    quick_replies: list[str] = []
    candidates_pool: dict[str, list[Candidate]] = {}
    result: SolveResult | None = None
    explanations: dict[str, str] = {}
    explain_cache: dict[str, str] = {}  # "need_id|practitioner_id" -> text
    brief_intro: str = ""
    timeline: list[TimelineItem] = []
    brief: str = ""
    blocking: list[str] = []
    concessions: list[ConcessionOption] = []
    overrides: Overrides = Overrides()
    rejected: list[str] = []
    pins: list[Pin] = []
    custom_prs: dict[str, Practitioner] = {}  # external (non-DB) pinned people, keyed ext_<need_id>
    injected: list[tuple[str, str]] = []      # (need_id, pid) candidates added to the pool for pins
    retries: dict[str, int] = {"coordinator": 0, "final": 0}
    check: dict = {}
    events: list[str] = []
    consultation: list[dict] = []           # post-build Advisor chat: {"role": "user"|"assistant", "text": ...}
    advisor_quick_replies: list[str] = []


class FlowError(ValueError):
    pass


def _ek(t, nid: str) -> str:
    """explain-cache key: the text depends on who fills the role and whether they carry an out-of-scope fee."""
    return f"{nid}|{t.assignments[nid]}" + ("|oos" if nid in t.out_of_scope else "")


def _weights() -> dict[str, float]:
    from wasl.retrieval import WEIGHTS
    return WEIGHTS


class Orchestrator:
    def __init__(self, llm, search=None, practitioners: dict[str, Practitioner] | None = None, today: date | None = None):
        self.llm = llm
        self._search = search
        self._prs = practitioners
        self.today = today

    @property
    def prs(self) -> dict[str, Practitioner]:
        if self._prs is None:
            self._prs = db.load_practitioners(db.connect())
        return self._prs

    def search(self, needs, card):
        if self._search is None:
            from wasl import retrieval
            self._search = retrieval.search_all
        return self._search(needs, card)

    def _today(self) -> date:
        return self.today or date.today()

    # ---------- intake ----------
    def start(self, idea: str, style_notes: str = "") -> SessionState:
        st = SessionState(id=uuid.uuid4().hex[:12], idea=idea, style_notes=style_notes)
        if style_notes.strip():  # style already given up-front: the final style question is skipped
            st.card.style = TrackedField(value=style_notes.strip()[:120], status="known")
        self._clarify(st, idea)
        return st

    def message(self, st: SessionState, text: str) -> SessionState:
        if st.status in ("built", "infeasible"):  # the chat never locks: keep consulting on the built project
            return self.consult(st, text)
        if st.status != "clarifying":
            raise FlowError("intake already finished; review the needs and call build-team")
        self._clarify(st, text)
        return st

    # ---------- post-build consultation ----------
    def consult(self, st: SessionState, text: str) -> SessionState:
        out = agents.consult(self.llm, self.advisor_context(st), st.consultation, text)
        st.consultation += [{"role": "user", "text": text}, {"role": "assistant", "text": out.answer}]
        st.advisor_quick_replies = out.quick_replies
        return st

    def advisor_context(self, st: SessionState) -> dict:
        """Everything the Advisor may ground its answers on (built card, team, budget, timeline, playbook)."""
        c, budget = st.card, self.budget(st)
        pb = agents.load_playbook(c.sector.value)
        ctx = {"idea": st.idea, "style_notes": st.style_notes, "status": st.status,
               "card": c.model_dump(mode="json", exclude={"needs"}),
               "needs": [{"role": n.role, "phase": n.phase, "reason": n.reason, "remote_ok": n.remote_ok,
                          "window": [str(n.phase_window[0]), str(n.phase_window[1])]} for n in self.needs(st)],
               "overrides": st.overrides.model_dump(),
               "critical_deadlines": [a["ar"] for a in self.deadlines(st)],
               "playbook": {k: pb.get(k) for k in ("phases", "typical_roles", "permits", "commonly_forgotten_needs")}}
        if st.status == "built" and st.result and st.result.team:
            t, prs = st.result.team, self._p(st)
            cost = {(x.need_id, x.practitioner_id): x.estimated_cost for cs in st.candidates_pool.values() for x in cs}
            team = []
            for n in st.card.needs:
                pid, bk = t.assignments[n.id], t.backups.get(n.id)
                o = t.out_of_scope.get(n.id)
                team.append({"role": n.role, "phase": n.phase, "member": prs[pid].name, "city": prs[pid].city,
                             "cost": t.cost_of(n.id, cost[n.id, pid]),
                             "out_of_scope": o.note_ar if o else None,
                             "pinned_by_user": n.id in self._pin_map(st),
                             "why": st.explanations.get(n.id, ""),
                             "backup": prs[bk].name if bk else None})
            ctx.update(team=team, timeline=[x.model_dump(mode="json") for x in st.timeline],
                       budget_breakdown={"budget": budget, "team_cost": t.total_cost,
                                         "remaining": (budget or 0) - t.total_cost,
                                         "per_role": {m["role"]: m["cost"] for m in team}})
        else:
            ctx.update(blocking=st.blocking, concessions=[x.label for x in st.concessions], budget=budget)
        return ctx

    def _clarify(self, st, text):
        if agents.clarify(self.llm, st, text, self._today()):
            st.card.needs = agents.requirements(self.llm, st)
            st.status = "needs_review"
            st.events.append("requirements ready for review")

    # ---------- team ----------
    def build_team(self, st: SessionState, needs: list[Need] | None = None, drop: list[str] = (),
                   pins: list[Pin] | None = None) -> SessionState:
        if st.status == "clarifying":
            raise FlowError("finish the intake first")
        if needs is not None:
            st.card.needs = needs
        st.card.needs = [n for n in st.card.needs if n.id not in set(drop)]
        if not st.card.needs:
            raise FlowError("no needs to staff")
        st.overrides, st.rejected, st.explain_cache = Overrides(), [], {}
        st.retries = {"coordinator": 0, "final": 0}
        st.candidates_pool = self.search(st.card.needs, st.card)
        st.injected = []
        self.set_pins(st, st.pins if pins is None else pins)
        self._solve_and_explain(st)
        return st

    def what_if(self, st: SessionState, budget: int | None = None, deadline_shift_days: int | None = None,
                allow_remote: bool | None = None, pins: list[Pin] | None = None) -> SessionState:
        self._need_pool(st)
        if pins is not None:
            self.set_pins(st, pins)
        if budget is not None:
            st.overrides.budget = budget
        if deadline_shift_days is not None:
            st.overrides.shift_days = deadline_shift_days
        if allow_remote is not None:
            st.overrides.remote_needs = [n.id for n in st.card.needs] if allow_remote else []
        self._solve_and_explain(st)
        return st

    def apply_concession(self, st: SessionState, concession_id: str) -> SessionState:
        self._need_pool(st)
        c = next((c for c in st.concessions if c.id == concession_id), None)
        if c is None:
            raise FlowError(f"unknown concession {concession_id}")
        if st.retries["coordinator"] >= MAX_COORDINATOR_RETRIES:
            raise FlowError("too many concessions applied; adjust budget/dates via what-if or rebuild")
        st.retries["coordinator"] += 1
        o = st.overrides
        if c.kind == "extra_budget_sar":
            o.budget = self.budget(st) + c.value
        elif c.kind == "shift_days":
            o.shift_days += c.value
        else:
            o.remote_needs = sorted(set(o.remote_needs) | set(c.value))
        st.events.append(f"concession applied: {c.label}")
        self._solve_and_explain(st)
        return st

    def reject(self, st: SessionState, need_id: str) -> SessionState:
        if st.status != "built" or st.result is None or st.result.team is None:
            raise FlowError("no team to modify")
        t = st.result.team
        if need_id not in t.assignments:
            raise FlowError(f"unknown need {need_id}")
        old, bk = t.assignments[need_id], t.backups.get(need_id)
        prs = self._p(st)
        st.events.append(f"{prs[old].name} declined {need_id}")
        if any(p.need_id == need_id for p in st.pins):  # a pinned member declined -> unpin, re-optimise
            self.set_pins(st, [p for p in st.pins if p.need_id != need_id])
            if not old.startswith("ext_"):
                st.rejected.append(old)
            self._solve_and_explain(st)
            return st
        st.rejected.append(old)
        if bk is None or bk in st.rejected:
            self._solve_and_explain(st)  # no backup -> re-solve without the decliner
            return st
        t.assignments[need_id] = bk
        t.out_of_scope.pop(need_id, None)  # backups are always in scope
        pool, needs = self.pool(st), self.needs(st)
        cost = {(c.need_id, c.practitioner_id): c.estimated_cost for cs in pool.values() for c in cs}
        t.total_cost = sum(t.cost_of(n, cost[n, p]) for n, p in t.assignments.items())
        ctx = solver._Ctx(needs, pool, self.budget(st), None, prs, {"city": st.card.city.value}, self._pin_map(st))
        t.backups = solver._backups(ctx, t.assignments, t.total_cost,
                                    {n: o.surcharge for n, o in t.out_of_scope.items()})
        t.notes = [n for n in t.notes if old not in n] + [f"{need_id}: swapped {old} -> {bk} (declined)"]
        self._explain_and_check(st)
        return st

    # ---------- project-card edits (start date / official show date / delivery deadline) ----------
    def update_card(self, st: SessionState, start_date: date | None = None, show_date: date | None = None,
                    deadline: date | None = None) -> SessionState:
        """Editing the start moves the whole schedule (deadline + every role window) by the same delta; editing the
        deadline rescales the role windows into the new span; the show date is a fixed external commitment.
        A built/infeasible team is re-solved on the new windows (availability is re-checked, no retrieval rerun)."""
        c, changed = st.card, []
        if start_date is not None and start_date != c.start_date.value:
            old = c.start_date.value
            if old is not None:
                d = start_date - old
                c.needs = [n.model_copy(update={"phase_window": (n.phase_window[0] + d, n.phase_window[1] + d)})
                           for n in c.needs]
                if c.deadline.value:
                    c.deadline = TrackedField(value=c.deadline.value + d, status=c.deadline.status)
                if c.show_date.value and c.show_date.status == "assumed":
                    c.show_date = TrackedField(value=c.show_date.value + d, status="assumed")
            c.start_date = TrackedField(value=start_date, status="known")
            if c.deadline.value and c.deadline.value <= start_date:
                c.deadline = TrackedField(value=start_date + timedelta(90), status="assumed")
            changed.append(f"start_date={start_date}")
        if deadline is not None and deadline != c.deadline.value:
            s, old = c.start_date.value, c.deadline.value
            if s is not None and deadline <= s:
                raise FlowError("deadline must be after the start date")
            if s is not None and old is not None and c.needs:
                k = (deadline - s).days / max((old - s).days, 1)

                def f(x: date) -> date:
                    return s + timedelta(round((x - s).days * k))
                c.needs = [n.model_copy(update={"phase_window": (f(n.phase_window[0]),
                                                                 max(f(n.phase_window[0]), f(n.phase_window[1])))})
                           for n in c.needs]
            if c.show_date.value and c.show_date.status == "assumed" and c.show_date.value == old:
                c.show_date = TrackedField(value=deadline, status="assumed")
            c.deadline = TrackedField(value=deadline, status="known")
            changed.append(f"deadline={deadline}")
        if show_date is not None and show_date != c.show_date.value:
            if c.start_date.value and show_date < c.start_date.value:
                raise FlowError("the official show date cannot be before the start date")
            c.show_date = TrackedField(value=show_date, status="known")
            changed.append(f"show_date={show_date}")
        if not changed:
            return st
        st.events.append("card edited: " + ", ".join(changed))
        if st.status in ("built", "infeasible") and st.candidates_pool:
            st.retries["final"] = 0
            self._solve_and_explain(st)
        return st

    # ---------- critical deadlines & constraints ----------
    def deadlines(self, st: SessionState) -> list[dict]:
        c = st.card
        if not c.sector.value:
            return []
        members = None
        if st.status == "built" and st.result and st.result.team:
            t, prs, eff = st.result.team, self._p(st), {n.id: n for n in self.needs(st)}
            members = [(n.role, prs[t.assignments[n.id]], eff[n.id]) for n in c.needs if n.id in t.assignments]
        return deadlines.compute(c, self.needs(st), agents.load_playbook(c.sector.value), self._today(),
                                 st.overrides.shift_days, members)

    # ---------- pins (suggested members) ----------
    def _p(self, st) -> dict[str, Practitioner]:
        return {**self.prs, **st.custom_prs} if st.custom_prs else self.prs

    def _pin_map(self, st) -> dict[str, str]:
        return {p.need_id: p.pid for p in st.pins}

    def set_pins(self, st: SessionState, pins: list[Pin]):
        """Validate pins; make sure each pinned person is a candidate for their role (synthesised if needed).
        The solver then treats them as hard constraints and optimises the rest of the team around them."""
        nids = {n.id for n in st.card.needs}
        clean, roles, people = [], set(), set()
        for p in pins:
            if p.need_id not in nids:
                continue  # pin on a dropped role
            if p.practitioner_id is None and not (p.name or "").strip():
                raise FlowError(f"pin for {p.need_id}: choose a practitioner or type a name")
            if p.practitioner_id is not None and p.practitioner_id not in self.prs:
                raise FlowError(f"unknown practitioner {p.practitioner_id}")
            if p.need_id in roles or (p.practitioner_id and p.practitioner_id in people):
                raise FlowError("each role and each practitioner can be pinned only once")
            if p.estimated_cost is not None and p.estimated_cost < 0:
                raise FlowError("estimated cost must be >= 0")
            roles.add(p.need_id)
            people.add(p.practitioner_id)
            clean.append(p)
        for nid, pid in st.injected:  # drop candidates synthesised for previous pins
            st.candidates_pool[nid] = [c for c in st.candidates_pool.get(nid, []) if c.practitioner_id != pid]
        st.injected, st.custom_prs, st.pins = [], {}, clean
        st.rejected = [r for r in st.rejected if r not in {p.pid for p in clean}]
        needs = {n.id: n for n in self.needs(st)}
        for p in clean:
            n, pid = needs[p.need_id], p.pid
            pool = st.candidates_pool.setdefault(p.need_id, [])
            if p.practitioner_id is None:
                fee = p.estimated_cost or 0
                st.custom_prs[pid] = Practitioner(
                    id=pid, name=p.name.strip(), type="individual", specialties=[n.role], sectors=[n.sector],
                    city=st.card.city.value or "", remote_ok=True, price_min=max(fee, 1), price_max=max(fee, 1),
                    availability=[(date(2000, 1, 1), date(2100, 12, 31))], past_works=[], verified_license=False,
                    is_rising_talent=False, is_demo=False)
                cost, sb = fee, ScoreBreakdown(specialty=1, past_work_similarity=0, location=1, budget=1, availability=1)
            else:
                c = next((c for c in pool if c.practitioner_id == pid), None)
                if c is not None and (p.estimated_cost is None or p.estimated_cost == c.estimated_cost):
                    continue  # already a retrieved candidate: keep its real score
                if c is not None:
                    pool.remove(c)  # user-agreed fee overrides the estimate
                cost, sb = self._pin_candidate(self.prs[pid], n, st, c)
                cost = p.estimated_cost if p.estimated_cost is not None else cost
            score = sum(w * getattr(sb, f) for f, w in _weights().items())
            pool.append(Candidate(practitioner_id=pid, need_id=p.need_id, estimated_cost=cost, score=round(score, 4),
                                  score_breakdown=sb, is_available=True, location_match=True))
            st.injected.append((p.need_id, pid))
        if clean:
            prs = self._p(st)
            st.events.append("pinned: " + ", ".join(f"{prs[p.pid].name} -> {needs[p.need_id].role}" for p in clean))

    def _pin_candidate(self, pr: Practitioner, n: Need, st, c: Candidate | None):
        from wasl.retrieval import coverage, est_cost
        if c is not None:
            return c.estimated_cost, c.score_breakdown
        city = st.card.city.value
        return est_cost(pr), ScoreBreakdown(
            specialty=1.0 if n.sector in pr.sectors else 0.5, past_work_similarity=0.0, budget=1.0,
            location=1.0 if city is None or pr.city == city else (0.6 if pr.remote_ok else 0.0),
            availability=round(coverage(pr, n.phase_window), 4))

    # ---------- effective inputs ----------
    def budget(self, st) -> int | None:
        return st.overrides.budget if st.overrides.budget is not None else st.card.budget.value

    def needs(self, st) -> list[Need]:
        d, rem = timedelta(st.overrides.shift_days), set(st.overrides.remote_needs)
        return [n.model_copy(update={"phase_window": (n.phase_window[0] + d, n.phase_window[1] + d),
                                     "remote_ok": n.remote_ok or n.id in rem}) for n in st.card.needs]

    def pool(self, st) -> dict[str, list[Candidate]]:
        bad = set(st.rejected)
        return {k: [c for c in v if c.practitioner_id not in bad] for k, v in st.candidates_pool.items()}

    def _need_pool(self, st):
        if not st.candidates_pool:
            raise FlowError("build the team first")

    # ---------- pipeline: solve -> coordinate -> explain -> final check ----------
    def _solve(self, st) -> SolveResult:
        return solver.solve(self.needs(st), self.pool(st), self.budget(st), prefs={"city": st.card.city.value},
                            practitioners=self._p(st), pins=self._pin_map(st))

    def _solve_and_explain(self, st):
        res = self._solve(st)
        st.result = res
        if not res.feasible:  # Coordinator: translate diagnosis into user-facing choices
            nd = {n.id: n for n in st.card.needs}
            st.status = "infeasible"
            st.blocking = agents.explain_blocking(res, nd, st.card.city.value)
            st.concessions = agents.concession_options(res, nd)
            st.explanations, st.timeline, st.brief = {}, [], ""
            st.check = {"ok": False, "issues": ["infeasible"]}
            return
        st.status, st.blocking, st.concessions = "built", [], []
        self._explain_and_check(st)

    def _members(self, st) -> list[dict]:
        t, needs = st.result.team, {n.id: n for n in st.card.needs}
        team_ids = set(t.assignments.values())
        cand = {(c.need_id, c.practitioner_id): c for cs in st.candidates_pool.values() for c in cs}
        prs = self._p(st)
        return [agents.member_facts(nid, needs[nid], prs[pid], cand.get((nid, pid)), team_ids, prs,
                                    t.out_of_scope.get(nid))
                for nid, pid in t.assignments.items()]

    def _explain_and_check(self, st):
        needs, budget, city = self.needs(st), self.budget(st), st.card.city.value
        prs, pinned = self._p(st), set(self._pin_map(st))
        issues = agents.check_team(st.result, needs, budget, city, st.candidates_pool, prs, pinned)
        if issues and st.retries["final"] < MAX_FINAL_RETRIES:  # one solver retry
            st.retries["final"] += 1
            st.events.append(f"final check failed ({issues}); re-solving")
            res = self._solve(st)
            if not res.feasible:
                return self._solve_and_explain(st)
            st.result = res
            issues = agents.check_team(res, needs, budget, city, st.candidates_pool, prs, pinned)
        t = st.result.team
        members = self._members(st)
        project = {"idea": st.idea, "style_notes": st.style_notes, "sector": st.card.sector.value,
                   "city": city, "budget": budget}
        text_issues = []
        for attempt in range(MAX_FINAL_RETRIES + 2):  # LLM, one LLM retry, then grounded templates
            todo = [m for m in members if _ek(t, m["need_id"]) not in st.explain_cache]
            if todo or not st.brief_intro:
                if attempt <= MAX_FINAL_RETRIES:
                    out = agents.explain(self.llm, todo, project, need_intro=not st.brief_intro)
                else:
                    out = agents.ExplainOut(explanations={m["need_id"]: agents.template_explanation(m) for m in todo},
                                            brief_intro=st.brief_intro or self._default_intro(st))
                for m in todo:
                    st.explain_cache[_ek(t, m["need_id"])] = out.explanations[m["need_id"]]
                st.brief_intro = st.brief_intro or out.brief_intro or self._default_intro(st)
            st.explanations = {nid: st.explain_cache[_ek(t, nid)] for nid in t.assignments}
            text_issues = agents.check_texts({**st.explanations, "brief": st.brief_intro}, t.assignments, prs,
                                             t.backups)
            if not text_issues:
                break
            st.events.append(f"final check: grounding issues {text_issues}; regenerating")
            bad = {i.split(":")[0] for i in text_issues}
            if "brief" in bad:
                st.brief_intro = ""
            for nid in bad - {"brief"}:
                st.explain_cache.pop(_ek(t, nid), None)
        st.timeline = self._timeline(st)
        st.brief = self._brief(st)
        st.check = {"ok": not issues and not text_issues, "issues": issues + text_issues}

    def _default_intro(self, st) -> str:
        return f"مشروع {agents.SECTORS.get(st.card.sector.value, '')} في {st.card.city.value}: {st.idea[:200]}"

    def _timeline(self, st) -> list[TimelineItem]:
        t, groups, prs = st.result.team, {}, self._p(st)
        for n in self.needs(st):
            groups.setdefault(n.phase, []).append(n)
        out = [TimelineItem(phase=ph, phase_ar=agents.PHASES_AR.get(ph, ph), start=min(n.phase_window[0] for n in ns),
                            end=max(n.phase_window[1] for n in ns), roles=[n.role for n in ns],
                            members=[prs[t.assignments[n.id]].name for n in ns]) for ph, ns in groups.items()]
        return sorted(out, key=lambda x: x.start)

    def _brief(self, st) -> str:
        t, c, prs, pins = st.result.team, st.card, self._p(st), self._pin_map(st)
        cost = {(x.need_id, x.practitioner_id): x.estimated_cost for cs in st.candidates_pool.values() for x in cs}
        d = timedelta(st.overrides.shift_days)
        budget = self.budget(st)
        lines = [f"موجز المشروع — {agents.SECTORS.get(c.sector.value, c.sector.value)}", "", st.brief_intro, "",
                 f"المدينة: {c.city.value} | الفترة: {c.start_date.value + d} ← {c.deadline.value + d}"
                 + (f" | يوم العرض الرسمي: {c.show_date.value}" if c.show_date.value else ""),
                 f"الميزانية: {budget:,} ريال | التكلفة التقديرية للفريق: {t.total_cost:,} ريال"]
        if c.style.value:
            lines.append(f"طابع العمل: {c.style.value}")
        lines += ["", "الفريق:"]
        for n in st.card.needs:
            pid = t.assignments[n.id]
            bk = t.backups.get(n.id)
            oos = t.out_of_scope.get(n.id)
            fee = t.cost_of(n.id, cost[n.id, pid])
            share = f" — {fee / budget:.1%} من الميزانية" if budget else ""
            lines.append(f"- {n.role}: {prs[pid].name} (~{fee:,} ريال{share})"
                         + (" [مقترح من صاحب المشروع]" if n.id in pins else "")
                         + (f" [تشمل +{oos.surcharge:,} ريال: {agents.OOS_MARK}]" if oos else "")
                         + (f" — البديل: {prs[bk].name}" if bk else ""))
        lines += ["", "الجدول الزمني:"]
        lines += [f"- {x.phase_ar}: {x.start} ← {x.end} ({'، '.join(x.roles)})" for x in st.timeline]
        permits = agents.load_playbook(c.sector.value).get("permits", [])
        if permits:
            lines += ["", "التصاريح المطلوبة:"] + [f"- {p}" for p in permits]
        crit = [a["ar"] for a in self.deadlines(st) if a["severity"] != "info"]
        if crit:
            lines += ["", "المواعيد الحرجة والالتزامات:"] + [f"- {x}" for x in crit]
        return "\n".join(lines)

    # ---------- per-member facts for the team cards ----------
    @staticmethod
    def _availability(p: Practitioner, win, span) -> dict:
        """full=True when one availability block covers the whole project (start -> max(deadline, show))."""
        s, e = span
        full = bool(s and e) and any(a <= s and e <= b for a, b in p.availability)
        iv = next(((a, b) for a, b in p.availability if a <= win[0] and win[1] <= b), None)
        if iv is None and p.availability:  # pinned member outside their availability: closest block by overlap
            iv = max(p.availability, key=lambda ab: (min(ab[1], win[1]) - max(ab[0], win[0])).days)
        return {"full": full, "covers_role": any(a <= win[0] and win[1] <= b for a, b in p.availability),
                "from": str(iv[0]) if iv else None, "to": str(iv[1]) if iv else None,
                "role_from": str(win[0]), "role_to": str(win[1])}

    @staticmethod
    def _location(p: Practitioner, city: str | None, oos: bool) -> dict:
        if oos:
            return {"kind": "out_of_scope", "city": p.city, "surcharge_pct": round(solver.DEFAULTS["oos_rate"] * 100)}
        if city is None or p.city == city:
            return {"kind": "local", "city": p.city}
        return {"kind": "remote", "city": p.city}

    # ---------- view ----------
    def view(self, st: SessionState) -> dict:
        out = {"session_id": st.id, "status": st.status,
               "card": st.card.model_dump(mode="json", exclude={"needs"}),
               "question": st.question, "quick_replies": st.quick_replies,
               "needs": [n.model_dump(mode="json") for n in st.card.needs], "events": st.events[-10:],
               "pins": [p.model_dump() for p in st.pins],
               "consultation": st.consultation[-20:], "consultation_count": len(st.consultation),
               "advisor_quick_replies": st.advisor_quick_replies,
               "style_rationale": st.style_rationale, "deadlines": self.deadlines(st)}
        if st.status in ("built", "infeasible"):
            out.update(budget=self.budget(st), overrides=st.overrides.model_dump(), check=st.check,
                       blocking=st.blocking, concessions=[c.model_dump() for c in st.concessions])
        if st.status == "built":
            t, prs, pins = st.result.team, self._p(st), self._pin_map(st)
            cand = {(c.need_id, c.practitioner_id): c for cs in st.candidates_pool.values() for c in cs}
            budget, eff = self.budget(st), {n.id: n for n in self.needs(st)}
            ps, pe, show = deadlines.project_span(st.card, st.overrides.shift_days)
            span = (ps, max(x for x in (pe, show) if x) if (pe or show) else None)
            team = []
            for n in st.card.needs:
                pid, bk = t.assignments[n.id], t.backups.get(n.id)
                c, p = cand[n.id, pid], prs[pid]
                fee = t.cost_of(n.id, c.estimated_cost)
                team.append({"need_id": n.id, "role": n.role, "phase": n.phase, "pinned": n.id in pins,
                             "external": pid in st.custom_prs,
                             "practitioner": {"id": p.id, "name": p.name, "city": p.city, "type": p.type,
                                              "gender": p.gender, "specialties": p.specialties,
                                              "sectors": p.sectors, "remote_ok": p.remote_ok,
                                              "works_count": len(p.past_works),
                                              "since": min((w.year for w in p.past_works), default=None),
                                              "past_works": [w.model_dump() for w in p.past_works],
                                              "is_rising_talent": p.is_rising_talent,
                                              "verified_license": p.verified_license,
                                              "contact": p.contact()},
                             "budget_share": round(fee / budget, 4) if budget else None,
                             "availability": self._availability(p, eff[n.id].phase_window, span),
                             "location": self._location(p, st.card.city.value, n.id in t.out_of_scope),
                             "estimated_cost": fee, "base_cost": c.estimated_cost,
                             "out_of_scope": t.out_of_scope[n.id].model_dump() if n.id in t.out_of_scope else None,
                             "score": c.score,
                             "score_breakdown": c.score_breakdown.model_dump(),
                             "explanation": st.explanations.get(n.id, ""),
                             "backup": {"id": bk, "name": prs[bk].name,
                                        "estimated_cost": cand[n.id, bk].estimated_cost} if bk else None})
            out.update(team=team, total_cost=t.total_cost, notes=t.notes, idea=st.idea, style_notes=st.style_notes,
                       project_span={"start": str(ps) if ps else None, "end": str(pe) if pe else None,
                                     "show": str(show) if show else None},
                       permits=agents.load_playbook(st.card.sector.value).get("permits", []),
                       timeline=[x.model_dump(mode="json") for x in st.timeline], brief=st.brief)
        return out
