"""Seed SQLite with ~35 synthetic (is_demo=True) Arabic practitioner profiles + precomputed embeddings.
All names and works are invented."""
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import wasl.config  # noqa: F401  pins caches/temp to D: before anything heavy loads
from wasl import db
from wasl.schemas import Practitioner

D = date.fromisoformat
ALL = [(D("2026-12-01"), D("2027-12-31"))]


def w(title, year, role, desc, collab=()):
    return dict(title=title, year=year, role=role, description=desc, collaborator_ids=list(collab))


# id, name, type, specialties, sectors, city, remote_ok, price_min, price_max, availability, works, verified, rising
RAW = [
    # ---- Case 1: documentary film on Al-Ahsa handicrafts ----
    ("f01", "فيصل العتيبي", "individual", ["مخرج أفلام وثائقية", "إخراج"], ["film"], "الرياض", True, 30000, 45000, ALL,
     [w("أيادي النخيل", 2023, "مخرج", "فيلم وثائقي عن صناعة الخوص في القرى الزراعية.", ["f09"]),
      w("ذاكرة الطين", 2021, "مخرج", "وثائقي عن البيوت الطينية وحرفيي البناء التقليدي.", ["f05"])], True, False),
    ("f02", "نوف الملحم", "individual", ["مخرجة أفلام وثائقية", "إخراج", "سرد قصصي"], ["film"], "الأحساء", False, 18000, 26000,
     [(D("2027-01-01"), D("2027-04-30"))],
     [w("نول جدتي", 2025, "مخرجة", "فيلم قصير عن نساء ينسجن البشوت في الأحساء.", ["f07"]),
      w("سوق القيصرية", 2024, "مخرجة", "وثائقي قصير عن حرفيي سوق القيصرية التاريخي.")], False, True),
    ("f03", "ماجد الدوسري", "individual", ["مخرج", "مونتير", "مونتاج أفلام وثائقية"], ["film"], "الدمام", True, 20000, 30000,
     [(D("2027-01-01"), D("2027-05-31"))],
     [w("بحارة الخليج", 2022, "مخرج ومونتير", "وثائقي عن صيادي اللؤلؤ وحكاياتهم.", ["f08"]),
      w("مواسم", 2024, "مونتير", "سلسلة قصيرة عن المهرجانات الشعبية في المنطقة الشرقية.")], True, False),
    ("f04", "سلطان الغامدي", "individual", ["مدير تصوير سينمائي", "تصوير سينمائي"], ["film"], "جدة", True, 28000, 40000,
     [(D("2027-03-01"), D("2027-06-30"))],
     [w("ظلال البلد", 2024, "مدير تصوير", "فيلم وثائقي حائز على جائزة عن جدة التاريخية.", ["f01"]),
      w("الحرفي الأخير", 2022, "مدير تصوير", "تصوير سينمائي لحرفيي النحاس في الأسواق القديمة.")], True, False),
    ("f05", "حسن البوعلي", "individual", ["مدير تصوير", "تصوير سينمائي", "تصوير وثائقي"], ["film"], "الأحساء", False, 15000, 22000,
     [(D("2027-01-01"), D("2027-03-31"))],
     [w("ذاكرة الطين", 2021, "مدير تصوير", "تصوير البيوت الطينية والحرفيين في ضوء طبيعي.", ["f01", "f07"]),
      w("عيون الأحساء", 2023, "مصور", "تصوير وثائقي للعيون والمزارع في الواحة.")], True, False),
    ("f06", "راكان الشمري", "individual", ["مخرج", "مدير تصوير", "تصوير سينمائي"], ["film"], "الرياض", True, 22000, 32000,
     [(D("2027-01-01"), D("2027-03-31"))],
     [w("رمال", 2023, "مخرج ومصور", "فيلم قصير تجريبي عن الصحراء والرعاة.", ["f09"]),
      w("صنعة", 2024, "مدير تصوير", "إعلان وثائقي عن الحرف السعودية.")], False, False),
    ("f07", "علي الخليفة", "individual", ["مهندس صوت ميداني", "تسجيل صوت"], ["film"], "الأحساء", False, 8000, 12000,
     [(D("2027-01-15"), D("2027-02-28"))],
     [w("نول جدتي", 2025, "مهندس صوت", "تسجيل أصوات الأنوال والحرفيات في بيئة حقيقية.", ["f02"]),
      w("ذاكرة الطين", 2021, "مهندس صوت", "تسجيل ميداني للمقابلات في مواقع مفتوحة.", ["f05"])], False, False),
    ("f08", "تركي القحطاني", "individual", ["مهندس صوت", "مكساج صوتي", "تصميم صوتي"], ["film"], "الرياض", True, 12000, 18000, ALL,
     [w("بحارة الخليج", 2022, "مصمم صوت", "مكساج وتصميم صوتي لفيلم وثائقي بحري.", ["f03"]),
      w("الليل الطويل", 2024, "مهندس صوت", "تسجيل ومكساج لفيلم روائي قصير.")], True, False),
    ("f09", "خالد المطيري", "individual", ["مونتير أفلام وثائقية", "مونتاج"], ["film"], "الرياض", True, 18000, 25000,
     [(D("2027-02-01"), D("2027-05-31"))],
     [w("أيادي النخيل", 2023, "مونتير", "مونتاج وثائقي عن الخوص بإيقاع هادئ.", ["f01"]),
      w("رمال", 2023, "مونتير", "مونتاج فيلم قصير تجريبي.", ["f06"])], True, False),
    ("f10", "ريم الزهراني", "individual", ["مونتيرة", "تصحيح ألوان", "مونتاج"], ["film"], "جدة", True, 12000, 16000,
     [(D("2027-01-01"), D("2027-06-30"))],
     [w("حكايات البحر", 2025, "مونتيرة", "مونتاج سلسلة قصيرة على المنصات الرقمية."),
      w("مشروع التخرج: ورق", 2024, "مونتيرة وملونة", "فيلم قصير عن صناعة الورق اليدوي.")], False, True),
    ("f11", "عبدالله الصالح", "individual", ["مدير تصوير سينمائي", "تصوير وثائقي"], ["film"], "الأحساء", True, 14000, 20000, ALL,
     [w("نخلة وحرفة", 2024, "مدير تصوير", "تصوير وثائقي لحرفيي السعف في ورشهم بإضاءة طبيعية."),
      w("مواسم", 2024, "مصور", "تصوير سلسلة قصيرة عن المهرجانات الشعبية.", ["f03"])], True, False),
    ("f12", "زينب الحسن", "individual", ["مهندسة صوت ميداني", "تسجيل صوت", "تسجيل مقابلات"], ["film"], "الأحساء", False, 7000, 11000, ALL,
     [w("أصوات السوق", 2025, "مهندسة صوت", "تسجيل ميداني لأصوات الحرفيين في سوق شعبي."),
      w("حكايا الجدات", 2024, "مسجلة صوت", "تسجيل مقابلات صوتية لتوثيق الذاكرة الشفهية.")], False, True),
    # ---- Case 2: heritage-themed fashion show in Riyadh ----
    ("s01", "لمى السبيعي", "individual", ["مصممة أزياء", "أزياء معاصرة مستوحاة من التراث"], ["fashion"], "الرياض", True, 40000, 60000, ALL,
     [w("سدو", 2024, "مصممة", "مجموعة أزياء مستوحاة من نقوش السدو.", ["s04", "s08"]),
      w("نجد", 2023, "مصممة", "عرض أزياء يمزج القصات النجدية بالخامات الحديثة.", ["s04"])], True, False),
    ("s02", "عمر باعشن", "individual", ["مصمم أزياء", "خياطة راقية"], ["fashion"], "جدة", True, 30000, 45000,
     [(D("2027-01-01"), D("2027-02-20"))],
     [w("البحر الأحمر", 2024, "مصمم", "مجموعة صيفية بألوان الساحل الغربي."),
      w("رواشين", 2022, "مصمم", "أزياء مستوحاة من رواشين جدة التاريخية.")], True, False),
    ("s03", "دار ورد للأزياء", "company", ["دار أزياء", "تصميم أزياء", "تنفيذ مجموعات"], ["fashion"], "الرياض", False, 50000, 80000, ALL,
     [w("أسبوع الرياض للأزياء", 2024, "دار أزياء", "تنفيذ مجموعة كاملة من ثلاثين قطعة.", ["s05"]),
      w("عباءات", 2023, "دار أزياء", "مجموعة عباءات بتطريز يدوي.")], True, False),
    ("s04", "سعد الحمدان", "individual", ["منسق عروض أزياء", "إدارة فعاليات"], ["fashion"], "الرياض", False, 20000, 30000, ALL,
     [w("سدو", 2024, "منسق العرض", "إدارة عرض أزياء لأربعين عارضة.", ["s01"]),
      w("ليالي الدرعية", 2023, "منسق فعالية", "تنسيق فعالية ثقافية في الدرعية.", ["x04"])], True, False),
    ("s05", "جود العنزي", "individual", ["منسقة عروض أزياء", "تنسيق مسرح"], ["fashion"], "الرياض", False, 15000, 22000, ALL,
     [w("أسبوع الرياض للأزياء", 2024, "مساعدة منسق", "تنسيق الكواليس وترتيب دخول العارضات.", ["s03"]),
      w("عرض التخرج", 2025, "منسقة", "تنسيق عرض أزياء لطالبات التصميم.")], False, True),
    ("s06", "بدر الرشيد", "individual", ["مصمم إضاءة مسرحية", "إضاءة عروض"], ["fashion"], "الرياض", False, 10000, 16000,
     [(D("2027-03-01"), D("2027-04-10"))],
     [w("نجد", 2023, "مصمم إضاءة", "إضاءة منصة عرض أزياء بألوان دافئة.", ["s01"]),
      w("مسرحية الحارة", 2022, "مصمم إضاءة", "إضاءة مسرحية شعبية.")], True, False),
    ("s07", "هيا الدوسري", "individual", ["مصممة إضاءة", "إضاءة مسرحية", "إضاءة فعاليات"], ["fashion"], "الدمام", True, 12000, 18000, ALL,
     [w("ليالي الشرقية", 2024, "مصممة إضاءة", "إضاءة فعالية ثقافية على الواجهة البحرية."),
      w("عرض الربيع", 2023, "مصممة إضاءة", "إضاءة عرض أزياء في الخبر.")], False, False),
    ("s08", "منيرة الأسمري", "individual", ["باحثة في الأزياء التراثية", "خبيرة أزياء تراثية"], ["fashion"], "أبها", True, 8000, 14000, ALL,
     [w("سدو", 2024, "مستشارة تراثية", "مراجعة دقة النقوش والرموز التراثية.", ["s01"]),
      w("أزياء عسير", 2022, "باحثة", "توثيق أزياء النساء في منطقة عسير.")], True, False),
    ("s09", "عبدالرحمن الفايز", "individual", ["خبير أزياء تراثية", "نسيج تقليدي"], ["fashion"], "الرياض", False, 15000, 20000, ALL,
     [w("البشت", 2023, "خبير", "دراسة عن تاريخ صناعة البشت."),
      w("معرض النسيج", 2021, "مستشار", "تقديم استشارات لمعرض أقمشة تقليدية.")], False, False),
    # ---- Case 3: heritage exhibition booth in AlUla ----
    ("h01", "طلال الحربي", "individual", ["مصمم معارض", "تصميم متاحف"], ["heritage"], "الرياض", True, 25000, 40000, ALL,
     [w("طريق البخور", 2024, "مصمم المعرض", "تصميم معرض متنقل عن طرق التجارة القديمة.", ["h05", "h08"]),
      w("قاعة النقوش", 2022, "مصمم", "تصميم قاعة عرض للنقوش الصخرية.", ["h05"])], True, False),
    ("h02", "استوديو مدار", "company", ["استوديو تصميم معارض", "تصميم أجنحة"], ["heritage"], "جدة", True, 35000, 55000, ALL,
     [w("جناح المملكة", 2023, "مصمم الجناح", "تصميم جناح ثقافي في معرض دولي."),
      w("بيت نصيف", 2022, "تصميم", "إعادة تصميم مسار الزوار في بيت تاريخي.")], True, False),
    ("h03", "شهد العنزي", "individual", ["مصممة معارض", "تصميم أجنحة صغيرة"], ["heritage"], "العلا", False, 12000, 18000, ALL,
     [w("ركن الحجر", 2025, "مصممة", "تصميم ركن صغير عن صناعة الحجر في العلا.", ["h06"]),
      w("مشروع تخرج: دادان", 2024, "مصممة", "نموذج معرض عن مملكة دادان.")], False, True),
    ("h04", "سليمان العنزي", "individual", ["باحث تراث", "أمين متحف"], ["heritage"], "العلا", False, 10000, 15000,
     [(D("2027-01-01"), D("2027-03-01"))],
     [w("كتالوج الحجر", 2023, "باحث", "توثيق القطع الأثرية لمعرض محلي.", ["h06"]),
      w("حكايات الواحة", 2021, "أمين معرض", "إعداد محتوى معرض عن تاريخ الواحة.")], True, False),
    ("h05", "دانة القرشي", "individual", ["باحثة آثار", "باحثة تراث", "نقوش قديمة"], ["heritage"], "الرياض", True, 12000, 18000, ALL,
     [w("طريق البخور", 2024, "باحثة المحتوى", "إعداد النصوص التاريخية للمعرض.", ["h01"]),
      w("قاعة النقوش", 2022, "باحثة", "قراءة وتوثيق النقوش الصخرية.", ["h01"])], True, False),
    ("h06", "مؤسسة الواحة للتجهيزات", "company", ["تجهيزات معارض", "تنفيذ ديكور"], ["heritage"], "العلا", False, 25000, 35000, ALL,
     [w("ركن الحجر", 2025, "منفذ", "تنفيذ ركن عرض بخامات محلية.", ["h03"]),
      w("كتالوج الحجر", 2023, "منفذ", "تجهيز فتارين عرض القطع.", ["h04"])], True, False),
    ("h07", "ياسر الجهني", "individual", ["منفذ ديكور", "نجارة معارض"], ["heritage"], "المدينة المنورة", True, 15000, 22000, ALL,
     [w("معرض السيرة", 2023, "منفذ ديكور", "تنفيذ جدران عرض خشبية متنقلة."),
      w("سوق المناخة", 2022, "نجار", "تنفيذ أكشاك بطابع تراثي.")], False, False),
    ("h08", "نواف السهلي", "individual", ["مصمم جرافيك", "لوحات تعريفية ثنائية اللغة"], ["heritage"], "الرياض", True, 8000, 12000, ALL,
     [w("طريق البخور", 2024, "مصمم جرافيك", "تصميم اللوحات التعريفية بالعربية والإنجليزية.", ["h01"]),
      w("دليل المتحف", 2023, "مصمم", "تصميم دليل مطبوع لزوار متحف.")], True, False),
    ("h09", "رهف البلوي", "individual", ["مصممة جرافيك", "خط عربي"], ["heritage"], "العلا", False, 6000, 10000, ALL,
     [w("خطوط دادان", 2025, "مصممة", "سلسلة ملصقات بخط مستوحى من النقوش القديمة."),
      w("هوية مهرجان محلي", 2024, "مصممة", "تصميم هوية بصرية لمهرجان صغير.")], False, True),
    ("h10", "أمل العطوي", "individual", ["باحثة تراث", "أمينة متحف", "توثيق مقتنيات"], ["heritage"], "العلا", True, 9000, 14000, ALL,
     [w("مقتنيات الواحة", 2024, "أمينة متحف", "إعداد البطاقات التعريفية لقطع أثرية في معرض محلي.", ["h06"]),
      w("سجل العلا", 2023, "باحثة", "بحث تاريخي عن طرق القوافل في العلا.")], True, False),
    # ---- Cross-sector ----
    ("x01", "أروى الشهري", "individual", ["مصورة سينمائية", "تصوير أزياء", "تصوير سينمائي"], ["film", "fashion"], "الرياض", True, 15000, 25000, ALL,
     [w("نجد", 2023, "مصورة العرض", "تصوير عرض أزياء بأسلوب سينمائي.", ["s01"]),
      w("حرفة", 2024, "مديرة تصوير", "فيلم قصير عن صناعة الفخار.", ["f09"])], True, False),
    ("x02", "إبراهيم النعيم", "individual", ["باحث تاريخ ثقافي", "باحث تراث", "باحث محتوى أفلام"], ["film", "heritage"], "الأحساء", True, 8000, 12000, ALL,
     [w("ذاكرة الطين", 2021, "باحث المحتوى", "بحث تاريخي عن العمارة الطينية.", ["f01"]),
      w("حكايات الواحة", 2021, "باحث", "جمع الروايات الشفهية لمعرض تراثي.", ["h04"])], True, False),
    ("x03", "مازن حلواني", "individual", ["مصمم جرافيك", "هوية بصرية"], ["film", "fashion", "heritage"], "جدة", True, 10000, 15000, ALL,
     [w("ملصق مهرجان الفيلم", 2024, "مصمم", "تصميم ملصقات وهوية لمهرجان أفلام قصيرة."),
      w("رواشين", 2022, "مصمم هوية", "هوية بصرية لمجموعة أزياء.", ["s02"])], False, False),
    ("x04", "سارة الخثلان", "individual", ["مصممة إضاءة", "سينوغرافيا", "إضاءة معارض"], ["fashion", "heritage"], "الرياض", True, 14000, 20000, ALL,
     [w("ليالي الدرعية", 2023, "سينوغرافيا", "تصميم الإضاءة والفضاء لفعالية تراثية.", ["s04"]),
      w("طريق البخور", 2024, "إضاءة المعرض", "إضاءة القطع الأثرية في معرض متنقل.", ["h01"])], True, False),
]

# project title -> local photo in src/wasl/static/portfolio/ (fetched once by scripts/fetch_portfolio_images.py).
# Keyed by title so a project shared by several collaborators shows the same photo on each of their portfolios.
IMAGES = {
    "أيادي النخيل": "palm-frond-weaving", "ذاكرة الطين": "mud-brick-village", "نول جدتي": "loom-weaving",
    "سوق القيصرية": "qaisariya-souq", "بحارة الخليج": "pearling-dhow", "مواسم": "folk-festival",
    "ظلال البلد": "jeddah-al-balad", "الحرفي الأخير": "coppersmith", "عيون الأحساء": "al-ahsa-oasis",
    "رمال": "desert-dunes-herder", "صنعة": "saudi-crafts", "الليل الطويل": "film-set-sound",
    "حكايات البحر": "red-sea-boats", "مشروع التخرج: ورق": "handmade-paper", "نخلة وحرفة": "palm-basket-craft",
    "أصوات السوق": "souq-field-recording", "حكايا الجدات": "oral-history-recording",
    "سدو": "sadu-weaving", "نجد": "runway-najd", "البحر الأحمر": "runway-summer", "رواشين": "jeddah-roshan",
    "أسبوع الرياض للأزياء": "fashion-week", "عباءات": "abaya-embroidery", "ليالي الدرعية": "diriyah-night",
    "عرض التخرج": "graduation-show", "مسرحية الحارة": "theatre-lighting", "ليالي الشرقية": "corniche-night-lights",
    "عرض الربيع": "runway-lighting", "أزياء عسير": "asir-dress", "البشت": "bisht", "معرض النسيج": "textile-exhibition",
    "طريق البخور": "incense-route-exhibit", "قاعة النقوش": "rock-inscriptions", "جناح المملكة": "saudi-pavilion",
    "بيت نصيف": "nasseef-house", "ركن الحجر": "alula-sandstone", "مشروع تخرج: دادان": "dadan",
    "كتالوج الحجر": "artifact-catalogue", "حكايات الواحة": "alula-oasis", "معرض السيرة": "exhibition-build",
    "سوق المناخة": "heritage-market-stalls", "دليل المتحف": "national-museum", "خطوط دادان": "ancient-script",
    "هوية مهرجان محلي": "festival-identity", "مقتنيات الواحة": "museum-vitrine", "سجل العلا": "camel-caravan",
    "حرفة": "pottery-wheel", "ملصق مهرجان الفيلم": "film-festival",
}


def image_url(title: str) -> str:
    return f"/static/portfolio/{IMAGES[title]}.jpg"


KEYS = ["id", "name", "type", "specialties", "sectors", "city", "remote_ok", "price_min", "price_max",
        "availability", "past_works", "verified_license", "is_rising_talent"]

# gender drives the heritage emblem on member cards (companies have none)
FEMALE = {"f02", "f10", "f12", "s01", "s05", "s07", "s08", "h03", "h05", "h09", "h10", "x01", "x04"}


def gender(pid: str, ptype: str) -> str | None:
    return None if ptype == "company" else "female" if pid in FEMALE else "male"


# Realistic calendars: some in-demand practitioners are only free for a block and get booked 15-30 days after the
# demo projects end (film ~Mar 20, fashion ~Apr 20, heritage ~Apr 25), so the Critical Deadlines panel shows real
# "can't slip more than N days" constraints; others keep the whole season open.
BUSY_AFTER = {
    "f01": [(D("2026-12-01"), D("2027-04-12"))],                                 # director: booked mid-April
    "f08": [(D("2026-12-01"), D("2027-04-20"))],                                 # sound: next film from late April
    "f11": [(D("2026-12-01"), D("2027-04-05")), (D("2027-06-01"), D("2027-12-31"))],
    "f12": [(D("2026-12-15"), D("2027-04-18"))],
    "s01": [(D("2026-12-01"), D("2027-05-12"))],                                 # designer: Paris week in May
    "s04": [(D("2027-01-10"), D("2027-05-08"))],
    "s07": [(D("2026-12-01"), D("2027-05-15"))],
    "h01": [(D("2026-12-01"), D("2027-05-20"))],
    "h06": [(D("2027-01-01"), D("2027-05-12"))],                                 # fit-out crew: Expo build
    "h10": [(D("2026-12-01"), D("2027-05-25"))],
    "x01": [(D("2026-12-01"), D("2027-04-15")), (D("2027-06-15"), D("2027-12-31"))],
    "x04": [(D("2026-12-01"), D("2027-05-14"))],
}

# ---- contact details (all invented; domains use the reserved .example TLD, numbers are demo placeholders) ----
# company key -> (name, phone, domain)
COMPANIES = {
    "nakhla": ("استوديو نخلة للإنتاج", "+966 13 581 2040", "nakhla-films.example"),
    "sarab": ("سراب ميديا", "+966 11 460 7310", "sarab-media.example"),
    "ofoq": ("أفق للإنتاج المرئي", "+966 12 655 1180", "ofoq-productions.example"),
    "ward": ("دار ورد للأزياء", "+966 11 470 2255", "ward-fashion.example"),
    "minassa": ("منصة للعروض والفعاليات", "+966 11 482 9060", "minassa-events.example"),
    "madar": ("استوديو مدار", "+966 12 667 4410", "madar-studio.example"),
    "alwaha": ("مؤسسة الواحة للتجهيزات", "+966 14 884 3020", "alwaha-fitout.example"),
    "irth": ("إرث للاستشارات الثقافية", "+966 11 455 6090", "irth-heritage.example"),
}
# practitioner id -> (latin handle for email, affiliated company key)
AFFILIATION = {
    "f01": ("faisal.otaibi", "sarab"), "f02": ("nouf.almulhim", "nakhla"), "f03": ("majed.dosari", "nakhla"),
    "f04": ("sultan.ghamdi", "ofoq"), "f05": ("hassan.bualy", "nakhla"), "f06": ("rakan.shammari", "sarab"),
    "f07": ("ali.khalifa", "nakhla"), "f08": ("turki.qahtani", "sarab"), "f09": ("khalid.mutairi", "sarab"),
    "f10": ("reem.zahrani", "ofoq"), "f11": ("abdullah.saleh", "nakhla"), "f12": ("zainab.hassan", "nakhla"),
    "s01": ("lama.subaie", "ward"), "s02": ("omar.baeshen", "ofoq"), "s03": ("info", "ward"),
    "s04": ("saad.hamdan", "minassa"), "s05": ("jood.anazi", "minassa"), "s06": ("bader.rasheed", "minassa"),
    "s07": ("haya.dosari", "minassa"), "s08": ("munira.asmari", "irth"), "s09": ("abdulrahman.fayez", "ward"),
    "h01": ("talal.harbi", "madar"), "h02": ("hello", "madar"), "h03": ("shahad.anazi", "alwaha"),
    "h04": ("sulaiman.anazi", "irth"), "h05": ("dana.qurashi", "irth"), "h06": ("info", "alwaha"),
    "h07": ("yasser.juhani", "alwaha"), "h08": ("nawaf.sahli", "madar"), "h09": ("rahaf.balawi", "alwaha"),
    "h10": ("amal.atawi", "irth"), "x01": ("arwa.shehri", "ofoq"), "x02": ("ibrahim.nuaim", "irth"),
    "x03": ("mazen.halawani", "ofoq"), "x04": ("sara.khathlan", "minassa"),
}


def contact(pid: str, i: int, ptype: str) -> dict:
    handle, ck = AFFILIATION[pid]
    cname, cphone, dom = COMPANIES[ck]
    own = {"phone": cphone, "email": f"{handle}@{dom}"} if ptype == "company" else \
          {"phone": f"+966 5{i % 6} {100 + i * 7:03d} {2000 + i * 37:04d}", "email": f"{handle}@{dom}"}
    return {**own, "company_name": cname, "company_phone": cphone, "company_email": f"contact@{dom}",
            "company_website": f"https://{dom}"}


def build() -> list[Practitioner]:
    out = []
    for i, r in enumerate(RAW):
        d = dict(zip(KEYS, r))
        d["availability"] = BUSY_AFTER.get(r[0], d["availability"])
        d["past_works"] = [{**w, "image_url": image_url(w["title"])} for w in d["past_works"]]
        out.append(Practitioner(**d, **contact(r[0], i, r[2]), gender=gender(r[0], r[2])))
    return out


def main():
    items = build()
    ids = {p.id for p in items}
    dangling = {c for p in items for c in p.collaborators} - ids
    assert not dangling, f"unknown collaborator ids: {dangling}"
    assert all(p.phone and p.email and p.company_name for p in items), "every profile needs contact details"
    static = Path(__file__).resolve().parents[1] / "src" / "wasl" / "static"
    for p in items:
        urls = [w.image_url for w in p.past_works]
        assert len(set(urls)) == len(urls), f"{p.id}: duplicate portfolio photo"
        for u in urls:
            f = static / u.removeprefix("/static/")
            assert f.is_file() and f.stat().st_size > 20_000 and f.read_bytes()[:3] == b"\xff\xd8\xff", \
                f"{p.id}: missing/invalid photo {u} (run scripts/fetch_portfolio_images.py)"
    path = db.DB_PATH
    path.unlink(missing_ok=True)
    con = db.connect(path)
    db.upsert_practitioners(con, items)
    n = len(items)
    print(f"seeded {n} profiles -> {path}")
    print(f"  rising_talent: {sum(p.is_rising_talent for p in items)/n:.0%}  "
          f"verified: {sum(p.verified_license for p in items)/n:.0%}  "
          f"remote_ok: {sum(p.remote_ok for p in items)/n:.0%}")
    print("  sectors:", dict(Counter(s for p in items for s in p.sectors)))
    print("  cities:", dict(Counter(p.city for p in items)))
    print("  gender:", dict(Counter(p.gender or "company" for p in items)),
          f" full-season availability: {sum(p.availability == ALL for p in items)}/{n}")
    if "--no-embed" not in sys.argv:
        from wasl import retrieval
        retrieval.index_all(con, list(items))
        print(f"  embeddings stored with model: {retrieval.active_models()}")


if __name__ == "__main__":
    main()
