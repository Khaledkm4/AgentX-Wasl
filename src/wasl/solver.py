"""Team solver: pure CP-SAT, no LLM.

Location/work-mode is a SOFT constraint: the solver first looks for a team where everyone works in their usual
scope (project city, or remote only where the need allows it). Only if that is impossible does it allow members
outside their usual scope, each with a small symbolic surcharge on their fee (+5%, min 500 SAR) and a structured
OutOfScope flag on the assignment, using as few of them as possible. Availability and budget stay hard."""
import math
from datetime import date, timedelta

from ortools.sat.python import cp_model

from wasl.schemas import Candidate, Concession, Need, OutOfScope, Practitioner, SolveResult, Team

Window = tuple[date, date]
DEFAULTS = dict(city=None, rising_talent="soft", rising_bonus=60, collab_bonus=40, time_limit=5.0,
                out_of_scope="soft", oos_rate=0.05, oos_min_fee=500, oos_penalty=1000)
OOS_NOTE_AR = "إضافة بسيطة على الأتعاب لكونه خارج نطاق عمله المعتاد"
OOS_NOTE_EN = "A small extra fee is added because this is outside their usual work scope"


def surcharge(cost: int, prefs: dict | None = None) -> int:
    p = {**DEFAULTS, **(prefs or {})}
    return max(int(p["oos_min_fee"]), math.ceil(cost * p["oos_rate"]))


def out_of_scope_flag(p: Practitioner, n: Need, city, base_cost: int, prefs: dict | None = None) -> OutOfScope:
    remote = p.remote_ok and not n.remote_ok  # prefers remote work but this role is on-site
    why_ar = (f"يفضّل العمل عن بُعد من {p.city} والدور يتطلب حضوراً في {city}" if remote
              else f"مقرّه {p.city} والمشروع في {city}")
    why_en = (f"prefers remote work from {p.city} while this role is on-site in {city}" if remote
              else f"based in {p.city} while the project is in {city}")
    s = surcharge(base_cost, prefs)
    return OutOfScope(reason="remote_preference" if remote else "outside_city", member_city=p.city,
                      project_city=city, base_cost=base_cost, surcharge=s,
                      note_ar=f"{OOS_NOTE_AR} ({why_ar}): +{s:,} ريال.",
                      note_en=f"{OOS_NOTE_EN} ({why_en}): +{s:,} SAR.")


def _avail(p: Practitioner, w: Window) -> bool:
    return any(a <= w[0] and w[1] <= b for a, b in p.availability)


def _loc(p: Practitioner, n: Need, city, remote_extra=frozenset()) -> bool:
    return city is None or p.city == city or (p.remote_ok and (n.remote_ok or n.id in remote_extra))


def _overlap(a: Window, b: Window) -> bool:
    return a[0] <= b[1] and b[0] <= a[1]


def _together(p: Practitioner, q: Practitioner) -> bool:
    return p.id in q.collaborators or q.id in p.collaborators


class _Ctx:
    def __init__(self, needs, cands, budget, windows, prs, prefs, pins=None):
        self.needs, self.cands, self.budget, self.prs = needs, cands, budget, prs
        self.pins = {k: v for k, v in (pins or {}).items() if k in {n.id for n in needs}}  # need_id -> pid
        self.windows = {n.id: (windows or {}).get(n.id, n.phase_window) for n in needs}
        self.p = {**DEFAULTS, **(prefs or {})}

    def valid(self, n: Need, wins=None, remote_extra=frozenset(), check_avail=True, check_loc=True):
        w = (wins or self.windows)[n.id]
        return [c for c in self.cands.get(n.id, [])
                if (not check_avail or _avail(self.prs[c.practitioner_id], w))
                and (not check_loc or _loc(self.prs[c.practitioner_id], n, self.p["city"], remote_extra))]

    def pinned(self, n: Need) -> list[Candidate]:
        """User-pinned role: the pinned candidate is the only option (hard constraint, no avail/loc filter)."""
        return [c for c in self.cands.get(n.id, []) if c.practitioner_id == self.pins[n.id]]

    @property
    def soft(self) -> bool:
        return self.p["out_of_scope"] == "soft"

    def run(self, objective="score", budget=True, wins=None, rising_hard=False, remote_gated=False,
            check_avail=True, soft_loc=False):
        """Build & solve. remote_gated: allow remote on any need behind a per-need bool r_n (minimized).
        soft_loc: out-of-scope candidates allowed, at cost + surcharge and a large per-member score penalty."""
        wins = wins or self.windows
        m = cp_model.CpModel()
        x, r, oos = {}, {}, set()
        for n in self.needs:
            if n.id in self.pins:
                pool = self.pinned(n)
            else:
                pool = self.valid(n, wins, check_avail=check_avail, check_loc=not (remote_gated or soft_loc))
            if remote_gated and n.id not in self.pins:
                pool = [c for c in pool if _loc(self.prs[c.practitioner_id], n, self.p["city"], {n.id})]
                r[n.id] = m.NewBoolVar(f"r_{n.id}")
            if not pool:
                return None
            for c in pool:
                v = x[n.id, c.practitioner_id] = m.NewBoolVar(f"x_{n.id}_{c.practitioner_id}")
                in_scope = _loc(self.prs[c.practitioner_id], n, self.p["city"])
                if remote_gated and n.id not in self.pins and not in_scope:
                    m.Add(v <= r[n.id])
                if soft_loc and n.id not in self.pins and not in_scope:
                    oos.add((n.id, c.practitioner_id))
            m.AddExactlyOne(x[n.id, c.practitioner_id] for c in pool)
        cand = {(c.need_id, c.practitioner_id): c for cs in self.cands.values() for c in cs}
        cost = {k: cand[k].estimated_cost + (surcharge(cand[k].estimated_cost, self.p) if k in oos else 0)
                for k in x}
        if budget and self.budget is not None:
            m.Add(sum(cost[k] * v for k, v in x.items()) <= self.budget)
        # one role per practitioner per project (also rules out double-booking across phases)
        keys, by_p = list(x), {}
        for (n, p), v in x.items():
            by_p.setdefault(p, []).append(v)
        for vs in by_p.values():
            if len(vs) > 1:
                m.AddAtMostOne(vs)
        terms, pairs = [], []
        if objective == "score":
            terms += [(int(round(cand[k].score * 1000)) - (self.p["oos_penalty"] if k in oos else 0)) * v
                      for k, v in x.items()]
            for i, (n1, p1) in enumerate(keys):  # collaboration bonus: y <= x1, y <= x2
                for n2, p2 in keys[i + 1:]:
                    if n1 != n2 and p1 != p2 and _together(self.prs[p1], self.prs[p2]):
                        y = m.NewBoolVar(f"y_{n1}_{p1}_{n2}_{p2}")
                        m.Add(y <= x[n1, p1])
                        m.Add(y <= x[n2, p2])
                        terms.append(self.p["collab_bonus"] * y)
                        pairs.append((y, p1, p2))
            rising = [v for (n, p), v in x.items() if self.prs[p].is_rising_talent]
            if rising and rising_hard:
                m.Add(sum(rising) >= 1)
            elif rising and self.p["rising_talent"] != "off":
                z = m.NewBoolVar("rising")
                m.Add(z <= sum(rising))
                terms.append(self.p["rising_bonus"] * z)
            m.Maximize(sum(terms))
        elif objective == "cost":
            m.Minimize(sum(cost[k] * v for k, v in x.items()))
        elif objective == "remote":
            m.Minimize(sum(r.values()))
        s = cp_model.CpSolver()
        s.parameters.max_time_in_seconds = self.p["time_limit"]
        s.parameters.num_workers = 1
        if s.Solve(m) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return None
        assign = {n: p for (n, p), v in x.items() if s.Value(v)}
        return dict(assign=assign, cost=sum(cost[k] for k in assign.items()),
                    pairs=[(a, b) for y, a, b in pairs if s.Value(y)],
                    remote=[n for n, v in r.items() if s.Value(v)],
                    oos=[n for n, p in assign.items() if (n, p) in oos])


def solve(needs: list[Need], candidates_by_need: dict[str, list[Candidate]], budget: int | None,
          phase_windows: dict[str, Window] | None = None, prefs: dict | None = None,
          practitioners: dict[str, Practitioner] | None = None, pins: dict[str, str] | None = None) -> SolveResult:
    """pins: need_id -> practitioner_id forced into that role; the rest of the team is optimised around them
    (remaining budget, availability, one-role-per-person and the collaboration bonus all still apply)."""
    if practitioners is None:
        from wasl import db
        practitioners = db.load_practitioners(db.connect())
    ctx = _Ctx(needs, candidates_by_need, budget, phase_windows, practitioners, prefs, pins)
    notes = [f"pinned: {p} -> {n}" for n, p in ctx.pins.items()]
    hard = ctx.p["rising_talent"] == "hard"
    res = ctx.run(rising_hard=hard)
    if res is None and hard:
        res = ctx.run()
        if res:
            notes.append("rising-talent hard slot relaxed to soft: no feasible team includes a rising talent")
    if res is None and ctx.soft:  # nobody in scope fits -> allow out-of-scope members with a small surcharge
        res = ctx.run(rising_hard=hard, soft_loc=True) or (ctx.run(soft_loc=True) if hard else None)
    if res is None:
        return _diagnose(ctx)
    a = res["assign"]
    base = {(c.need_id, c.practitioner_id): c.estimated_cost for cs in candidates_by_need.values() for c in cs}
    nd = {n.id: n for n in needs}
    oos = {nid: out_of_scope_flag(practitioners[a[nid]], nd[nid], ctx.p["city"], base[nid, a[nid]], ctx.p)
           for nid in res.get("oos", [])}
    if any(practitioners[p].is_rising_talent for p in a.values()):
        notes.append("team includes a rising talent")
    notes += [f"collaboration bonus: {p} & {q} worked together before" for p, q in res["pairs"]]
    notes += [f"out of usual scope: {a[n]} -> {n} (+{o.surcharge} SAR surcharge, {o.reason})" for n, o in oos.items()]
    team = Team(assignments=a, backups=_backups(ctx, a, res["cost"], {n: o.surcharge for n, o in oos.items()}),
                total_cost=res["cost"], notes=notes, out_of_scope=oos)
    missing = [n.id for n in needs if n.id not in team.backups]
    if missing:
        team.notes.append(f"no valid backup for: {', '.join(missing)}")
    return SolveResult(feasible=True, team=team)


def _backups(ctx: _Ctx, assign: dict[str, str], total: int, surcharges: dict[str, int] | None = None) -> dict[str, str]:
    """In-scope backups only. surcharges: need_id -> out-of-scope surcharge included in the primary's cost."""
    cost = {(c.need_id, c.practitioner_id): c.estimated_cost for cs in ctx.cands.values() for c in cs}
    sc = surcharges or {}
    out, team = {}, set(assign.values())
    for n in ctx.needs:
        room = None if ctx.budget is None else ctx.budget - (total - cost[n.id, assign[n.id]] - sc.get(n.id, 0))
        ok = [c for c in ctx.valid(n) if c.practitioner_id not in team and (room is None or c.estimated_cost <= room)]
        fresh = [c for c in ok if c.practitioner_id not in out.values()]  # prefer a distinct backup per role
        if fresh or ok:
            out[n.id] = max(fresh or ok, key=lambda c: c.score).practitioner_id
    return out


def _diagnose(ctx: _Ctx) -> SolveResult:
    blocking, conc = [], []
    city = ctx.p["city"]
    for n in ctx.needs:
        w = ctx.windows[n.id]
        if n.id in ctx.pins:
            if not ctx.pinned(n):
                blocking.append(f"{n.id}: pinned practitioner {ctx.pins[n.id]} is not a candidate")
            elif any(ctx.pins[n.id] == q for k, q in ctx.pins.items() if k != n.id):
                blocking.append(f"{n.id}: pinned practitioner {ctx.pins[n.id]} pinned to more than one role")
            continue
        if not ctx.cands.get(n.id):
            blocking.append(f"{n.id}: no candidates retrieved")
        elif not ctx.valid(n, check_loc=False):
            blocking.append(f"{n.id}: no candidate available for {w[0]}..{w[1]}")
        elif not ctx.valid(n) and not ctx.soft:  # soft mode: location never blocks (surcharge instead)
            blocking.append(f"{n.id}: no available candidate located in {city} (remote not allowed)")
    if not blocking:
        if ctx.run(objective="cost", budget=False, soft_loc=ctx.soft) is None:
            blocking.append("double-booking: the same practitioner is needed for more than one role")
        else:
            blocking.append("budget")

    free = ctx.run(objective="cost", budget=False, soft_loc=ctx.soft)
    if free and ctx.budget is not None and free["cost"] > ctx.budget:
        conc.append(Concession(kind="extra_budget_sar", value=free["cost"] - ctx.budget,
                               detail=f"cheapest valid team costs {free['cost']} SAR vs budget {ctx.budget}"))
        blocking = [b if b != "budget" else f"budget: cheapest valid team {free['cost']} > {ctx.budget} SAR"
                    for b in blocking]
    d = _min_shift(ctx)
    if d:
        conc.append(Concession(kind="shift_days", value=d, detail=f"shift all phase windows by +{d} days"))
    rem = ctx.run(objective="remote", remote_gated=True)
    if rem and rem["remote"]:
        conc.append(Concession(kind="allow_remote_needs", value=sorted(rem["remote"]),
                               detail="allow remote/out-of-city practitioners for these needs"))
    return SolveResult(feasible=False, blocking_constraints=blocking, min_concessions=conc)


def _min_shift(ctx: _Ctx, max_days: int = 365) -> int | None:
    """Exact min shift: feasibility in d only changes at availability-start offsets a - s."""
    ds = set()
    for n in ctx.needs:
        s = ctx.windows[n.id][0]
        for c in ctx.cands.get(n.id, []):
            ds.update((a - s).days for a, _ in ctx.prs[c.practitioner_id].availability)
    for d in sorted(x for x in ds | {1} if 0 < x <= max_days):
        wins = {k: (a + timedelta(d), b + timedelta(d)) for k, (a, b) in ctx.windows.items()}
        if ctx.run(objective="cost", wins=wins, soft_loc=ctx.soft) is not None:
            return d
    return None
