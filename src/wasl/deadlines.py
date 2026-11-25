"""Critical deadlines & constraints (المواعيد الحرجة والالتزامات): pure, deterministic, recomputed on every view.

Sources:
  a) each assigned member's real availability vs. their (shifted) role window -> how far the project can slip;
  b) the sector playbook's permit_rules, anchored on a phase start or the official show date;
  c) the official show / launch date vs. the end of the work schedule.
Every alert carries both Arabic and English text so the UI can switch language without a round trip."""
from datetime import date, timedelta

from wasl.schemas import Need, Practitioner, ProjectCard

WATCH_DAYS = 60   # only surface members whose slack is within this horizon
HIGH_DAYS = 15    # <= this slack / lead time is critical
_RANK = {"high": 0, "medium": 1, "info": 2}


def _days_ar(n: int) -> str:
    n = abs(n)
    return "يوم واحد" if n == 1 else "يومين" if n == 2 else f"{n} أيام" if 3 <= n <= 10 else f"{n} يوماً"


def _days_en(n: int) -> str:
    n = abs(n)
    return f"{n} day" + ("" if n == 1 else "s")


def _alert(kind, severity, when: date | None, ar: str, en: str, days: int | None = None, **extra) -> dict:
    return {"kind": kind, "severity": severity, "date": str(when) if when else None, "days": days,
            "ar": ar, "en": en, **extra}


def project_span(card: ProjectCard, shift_days: int = 0) -> tuple[date | None, date | None, date | None]:
    """(effective start, effective end of work, official show date). Shift moves the work, not the show."""
    d = timedelta(shift_days)
    s = card.start_date.value + d if card.start_date.value else None
    e = card.deadline.value + d if card.deadline.value else None
    show = card.show_date.value or e
    return s, e, show


def _anchor(rule: dict, needs: list[Need], phases: list[str], start, end, show) -> date | None:
    a = rule.get("anchor", "show")
    if a == "show":
        return show
    ws = [n.phase_window[0] for n in needs if n.phase == a]
    if ws:
        return min(ws)
    if start and end and a in phases:  # no staffed role in that phase: place it proportionally
        return start + timedelta((end - start).days * phases.index(a) // max(len(phases), 1))
    return None


def permit_alerts(card: ProjectCard, needs: list[Need], playbook: dict, today: date, shift_days: int = 0) -> list[dict]:
    start, end, show = project_span(card, shift_days)
    if not (start or show):
        return []
    out = []
    for r in playbook.get("permit_rules", []):
        anchor = _anchor(r, needs, playbook.get("phases") or [], start, end, show)
        if anchor is None:
            continue
        due = anchor - timedelta(int(r.get("lead_days", 14)))
        left = (due - today).days
        sev = "high" if left < HIGH_DAYS else "medium" if left < 45 else "info"
        name_ar, name_en = r["permit"], r.get("en", r["permit"])
        ar = f"«{name_ar}» يجب إنجازه قبل {due} {r.get('purpose_ar', '')}".strip()
        en = f"“{name_en}” must be secured before {due} {r.get('purpose_en', '')}".strip()
        if left < 0:
            ar += f" — الموعد فات قبل {_days_ar(left)}، ابدأ الإجراءات فوراً."
            en += f" — overdue by {_days_en(left)}; start the process now."
        else:
            ar += f" (متبقٍ {_days_ar(left)})."
            en += f" ({_days_en(left)} left)."
        if start and due < start:
            ar += " يلزم إنجازه قبل بدء المشروع."
            en += " It must be done before the project starts."
        out.append(_alert("permit", sev, due, ar, en, left, permit=name_ar))
    return out


def availability_alerts(members: list[tuple[str, Practitioner, Need]], show: date | None) -> list[dict]:
    """members: (role, practitioner, effective need). External (pinned outside the DB) members are skipped."""
    out = []
    for role, p, n in members:
        if not p.is_demo and p.id.startswith("ext_"):
            continue
        w0, w1 = n.phase_window
        iv = next(((a, b) for a, b in p.availability if a <= w0 and w1 <= b), None)
        if iv is None:
            ar = f"{p.name} ({role}) غير متاح بالكامل خلال فترة دوره ({w0} ← {w1}) — نسّق معه أو عدّل الجدول."
            en = f"{p.name} ({role}) is not fully available during their role window ({w0} → {w1}) — confirm or adjust the schedule."
            out.append(_alert("availability", "high", w0, ar, en, 0, member=p.name, role=role))
            continue
        slack = (iv[1] - w1).days
        if slack > WATCH_DAYS:
            continue
        sev = "high" if slack <= HIGH_DAYS else "medium" if slack <= 30 else "info"
        ar = (f"لا يمكن تمديد المشروع أكثر من {_days_ar(slack)} لأن {p.name} ({role}) "
              f"سيصبح مشغولاً بعد {iv[1]}.") if slack else \
             f"لا يوجد أي هامش للتأخير: {p.name} ({role}) يصبح مشغولاً مباشرة بعد {iv[1]}."
        en = (f"The project can't slip more than {_days_en(slack)}: {p.name} ({role}) becomes busy after {iv[1]}."
              if slack else f"Zero slack: {p.name} ({role}) becomes busy right after {iv[1]}.")
        if show and n.phase in ("show", "operation") and iv[1] < show:
            ar += f" وهو غير متاح يوم العرض الرسمي ({show})."
            en += f" They are not available on the official show date ({show})."
            sev = "high"
        out.append(_alert("availability", sev, iv[1], ar, en, slack, member=p.name, role=role))
    return out


def show_alerts(card: ProjectCard, shift_days: int = 0) -> list[dict]:
    start, end, show = project_span(card, shift_days)
    if not (card.show_date.value and end):
        return []
    gap = (show - end).days
    if start and show < start:
        return [_alert("show", "high", show, f"يوم العرض الرسمي ({show}) قبل تاريخ البدء ({start}) — راجع التواريخ.",
                       f"The official show date ({show}) is before the start date ({start}) — check the dates.", gap)]
    if gap < 0:
        return [_alert("show", "high", show,
                       f"يوم العرض الرسمي ({show}) يسبق نهاية جدول العمل ({end}) بـ{_days_ar(gap)} — قدّم الجدول أو أجّل العرض.",
                       f"The official show date ({show}) falls {_days_en(gap)} before the work schedule ends ({end}) — "
                       f"pull the schedule forward or move the show.", gap)]
    if gap == 0:
        return [_alert("show", "medium", show,
                       f"يوم العرض الرسمي ({show}) هو نفس يوم نهاية العمل — لا يوجد أي هامش، وأي تأخير يمس العرض.",
                       f"The official show date ({show}) is the same day the work ends — no buffer at all; any slip hits the show.",
                       gap)]
    if gap <= 7:
        return [_alert("show", "medium", show,
                       f"هامش {_days_ar(gap)} فقط بين نهاية العمل ({end}) ويوم العرض الرسمي ({show}) — أي تأخير يمس العرض.",
                       f"Only {_days_en(gap)} between the end of work ({end}) and the official show ({show}) — any slip hits the show.",
                       gap)]
    return [_alert("show", "info", show,
                   f"يوم العرض الرسمي {show}: هامش {_days_ar(gap)} بعد نهاية جدول العمل ({end}).",
                   f"Official show date {show}: {_days_en(gap)} of buffer after the work schedule ends ({end}).", gap)]


def compute(card: ProjectCard, needs: list[Need], playbook: dict, today: date, shift_days: int = 0,
            members: list[tuple[str, Practitioner, Need]] | None = None) -> list[dict]:
    _, _, show = project_span(card, shift_days)
    out = show_alerts(card, shift_days) + availability_alerts(members or [], show) + \
        permit_alerts(card, needs, playbook, today, shift_days)
    return sorted(out, key=lambda a: (_RANK[a["severity"]], a["date"] or "9999"))
