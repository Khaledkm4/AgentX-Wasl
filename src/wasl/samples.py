"""Three hand-written ProjectCards (stand-ins for Clarifier/Requirements agent output)."""
from datetime import date

from wasl.schemas import Need, ProjectCard, TrackedField as TF

D = date.fromisoformat


def _card(sector, stage, budget, city, start, deadline, needs):
    return ProjectCard(sector=TF(value=sector, status="known"), stage=TF(value=stage, status="known"),
                       budget=TF(value=budget, status="known"), city=TF(value=city, status="known"),
                       start_date=TF(value=D(start), status="known"),
                       deadline=TF(value=D(deadline), status="assumed"), needs=needs)


def N(id, role, sector, reason, phase, s, e, importance=0.8, remote_ok=False, mentioned=True):
    return Need(id=id, role=role, sector=sector, reason=reason, phase=phase, phase_window=(D(s), D(e)),
                importance=importance, confidence=0.9 if mentioned else 0.7, remote_ok=remote_ok,
                mentioned=mentioned, consequence_if_ignored="" if mentioned else "قد يتأثر المشروع جودةً أو جدولاً")


FILM = _card("film", "pre_production", 120000, "الأحساء", "2027-01-10", "2027-03-20", [
    N("film_dir", "مخرج أفلام وثائقية", "film", "إخراج فيلم وثائقي قصير عن الحرف اليدوية في الأحساء",
      "pre_production", "2027-01-10", "2027-02-12", 1.0, remote_ok=True),
    N("film_dp", "مدير تصوير سينمائي", "film", "تصوير الحرفيين في ورشهم بإضاءة طبيعية",
      "production", "2027-01-25", "2027-02-10", 0.9, remote_ok=True),
    N("film_sound", "مهندس صوت ميداني", "film", "تسجيل المقابلات وأصوات الحرف في المواقع",
      "production", "2027-01-25", "2027-02-10", 0.7, mentioned=False),
    N("film_edit", "مونتير أفلام وثائقية", "film", "مونتاج الفيلم وتجهيزه للمهرجانات",
      "post_production", "2027-02-15", "2027-03-20", 0.9, remote_ok=True),
])

FASHION = _card("fashion", "design", 150000, "الرياض", "2027-02-01", "2027-04-20", [
    N("fa_designer", "مصمم أزياء", "fashion", "تصميم مجموعة أزياء مستوحاة من التراث السعودي",
      "design", "2027-02-01", "2027-03-31", 1.0, remote_ok=True),
    N("fa_show", "منسق عروض أزياء", "fashion", "تنسيق عرض الأزياء والعارضات في الرياض",
      "show", "2027-04-01", "2027-04-20", 0.8),
    N("fa_light", "مصمم إضاءة مسرحية", "fashion", "إضاءة منصة العرض بما يبرز ألوان الأقمشة",
      "show", "2027-04-05", "2027-04-20", 0.6, remote_ok=True, mentioned=False),
    N("fa_heritage", "خبير أزياء تراثية", "fashion", "مراجعة دقة الرموز والنقوش التراثية في التصاميم",
      "design", "2027-02-01", "2027-03-15", 0.6, remote_ok=True, mentioned=False),
])

HERITAGE = _card("heritage", "design", 100000, "العلا", "2027-02-15", "2027-04-25", [
    N("he_design", "مصمم معارض", "heritage", "تصميم جناح معرض تراثي في العلا",
      "design", "2027-03-01", "2027-03-31", 1.0, remote_ok=True),
    N("he_research", "باحث تراث وأمين متحف", "heritage", "إعداد المحتوى التاريخي والبطاقات التعريفية للقطع",
      "research", "2027-02-15", "2027-03-20", 0.8, remote_ok=True, mentioned=False),
    N("he_build", "منفذ ديكور وتجهيزات معارض", "heritage", "تنفيذ وتركيب الجناح في موقع العلا",
      "build", "2027-04-01", "2027-04-25", 0.9),
    N("he_graphic", "مصمم جرافيك ولوحات تعريفية", "heritage", "تصميم لوحات تعريفية ثنائية اللغة",
      "design", "2027-03-10", "2027-04-05", 0.5, remote_ok=True, mentioned=False),
])

CASES = {"film": FILM, "fashion": FASHION, "heritage": HERITAGE}
TIGHT_BUDGET = 40000  # deliberately infeasible budget for the heritage case
