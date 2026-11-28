// وصل — vanilla JS client for the FastAPI backend (/api/*)
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pct = (x) => Math.round((x || 0) * 100);

// ================================================================ i18n
// Static markup carries Arabic as its default text; elements tagged data-i18n / data-i18n-ph get their English
// from I18N.en (the Arabic is captured from the DOM on first switch). Dynamic UI strings live in both dictionaries.
const I18N = {
  ar: {
    title: "وصل — الصندوق الثقافي", langBtn: "English", arrow: "←", sarUnit: "ريال",
    welcome: "أهلاً بك في وصل! 👋 وش المشروع الثقافي اللي تبي تسويه؟ اشرح لي فكرتك بكلامك العادي، وأنا أساعدك نكمّل التفاصيل ونبني لك الفريق المناسب.",
    starters: ["فيلم وثائقي قصير", "عرض أزياء تراثي", "معرض أو جناح تراثي"],
    intakeDone: "تمام! جمعت الصورة الكاملة 👌 راجع شجرة الاحتياجات تحت، وعدّل أو استبعد اللي ما تحتاجه، واقترح عضو لو تبي، ثم اضغط «ابنِ الفريق الآن».",
    intakeOver: "راجع شجرة الاحتياجات واضغط «ابنِ الفريق الآن» — بعدها تقدر تكمل المحادثة معي كمستشار لمشروعك.",
    adv: { ready: "فريقك جاهز 🎉 المحادثة ما تقفل: اسألني عن تسلسل العمل بين الفريق، توزيع الميزانية، التصاريح، أو أي تعديل تفكر فيه.",
           readyInf: "ما اكتمل الفريق بالشروط الحالية، بس المحادثة مفتوحة: اسألني وش أفضل تنازل أو كيف نعدّل الخطة.",
           ld: "أراجع مشروعك وأجهّز لك الرد…",
           starters: ["وش تسلسل العمل بين الفريق؟", "كيف أوزع الميزانية المتبقية؟", "وش التصاريح المطلوبة؟"] },
    ct: { kicker: "بيانات التواصل", person: "التواصل المباشر", company: "الجهة / الشركة", phone: "الجوال", tel: "الهاتف", email: "البريد",
          web: "الموقع", call: "اتصال", mail: "مراسلة", visit: "زيارة", portfolio: "عرض ملف الأعمال ←", open: "📇 بيانات التواصل",
          none: "لا تتوفر بيانات تواصل لهذا العضو لأنه مقترح من خارج قاعدة وصل.", self: "هذه جهة (شركة) — بياناتها أدناه.",
          noCompany: "لا توجد جهة مرتبطة.", demo: "بيانات تجريبية لأغراض العرض فقط." },
    noServer: "تعذر الاتصال بالخادم. تأكد أنه شغال.", errCode: "خطأ {n}",
    ld: { start: "أقرأ فكرتك وأحلل المشروع…", msg: "أفهم ردّك…", build: "أبحث في قاعدة الممارسين وأبني أفضل فريق… (قد يأخذ لحظات)",
          wi: "أعيد الحساب…", conc: "أطبّق التنازل وأعيد البناء…", reject: "العضو اعتذر… أبدّله بالبديل",
          card: "أحدّث التواريخ وأعيد حساب الجدول والفريق والمواعيد الحرجة…" },
    health: { ok: "● النظام جاهز", cold: "● النماذج غير محمّلة", nollm: " · بدون LLM", down: "● الخادم غير متصل", checking: "… جارِ الفحص" },
    FIELDS: { sector: "المجال", stage: "المرحلة", budget: "الميزانية", city: "المدينة", start_date: "تاريخ البدء", deadline: "التسليم",
              show_date: "تاريخ يوم العرض الرسمي", style: "طابع العمل" },
    dl: { empty: "تظهر هنا تلقائياً المواعيد الحرجة (التصاريح، توفر الفريق، يوم العرض) بمجرد تحديد التواريخ والفريق.", n: "{n} حرجة",
          kind: { availability: "توفر الفريق", permit: "تصريح", show: "يوم العرض" } },
    mx: { budget: "الميزانية", loc: "الموقع", avail: "التوفر", exp: "التخصص والخبرة", ofBudget: "من الميزانية",
          local: "مناسب — {city}", remote: "عن بُعد", remoteFrom: "عن بُعد · {city}", oos: "خارج النطاق (+{p}%)",
          full: "متوفر خلال فترة المشروع كاملة", win: "متوفر من {a} إلى {b}", role: "فترة دوره: {a} ← {b}",
          notCover: "⚠ لا يغطي فترة دوره بالكامل", works: "{n} أعمال موثقة", since: "خبرة منذ {y}", match: "من نفس المجال" },
    emblem: { male: "العقال المقصب", female: "الهامة التراثية الذهبية" },
    editHint: "✎ قابل للتعديل",
    SECTORS: { film: "إنتاج أفلام", fashion: "أزياء", heritage: "تراث ومعارض" },
    STAGES: { planning: "تخطيط", pre_production: "ما قبل الإنتاج", design: "التصميم" },
    PHASES: { pre_production: "ما قبل الإنتاج", production: "الإنتاج", post_production: "ما بعد الإنتاج", distribution: "التوزيع",
      design: "التصميم", show: "العرض", marketing: "التسويق", research: "البحث", build: "التنفيذ", operation: "التشغيل" },
    STATUS: { clarifying: "محادثة", needs_review: "مراجعة الاحتياجات", built: "الفريق جاهز", infeasible: "غير ممكن حالياً" },
    SCORE: { specialty: "التخصص", past_work_similarity: "تشابه الأعمال", location: "الموقع", budget: "الميزانية", availability: "التوفر" },
    PILL: { known: "✓ معروف", assumed: "~ مفترض", missing: "؟ ناقص" },
    TYPE: { individual: "فرد", company: "شركة" },
    none: "لا يوجد", noEvents: "لا يوجد بعد",
    build: "ابنِ الفريق الآن ←", rebuild: "↻ أعد بناء الفريق",
    tree: { root: "المشروع", core: "أدوار أساسية", important: "أدوار مهمة", optional: "أدوار مكملة",
            coreEn: "Core / Mandatory", importantEn: "Important", optionalEn: "Optional",
            mentioned: "ذكرته", inferred: "مستنتج", remote: "عن بُعد", conf: "الثقة", imp: "الأهمية", drop: "استبعد",
            risk: "⚠️ لو تجاهلته:", pinned: "📌 مثبّت:" },
    card: { fit: "ملاءمة", rising: "🌟 موهبة صاعدة", collab: "🤝 عمل مشترك", licensed: "✓ مرخص", backup: "البديل:",
            reject: "محاكاة رفض العضو", pinned: "📌 مقترح منك", external: "من خارج القاعدة",
            oos: "↔ خارج نطاقه المعتاد", oosBase: "الأتعاب الأساسية", oosFee: "إضافة",
            extNote: "عضو اقترحته من خارج قاعدة الممارسين: ثبّتناه في الدور وخصمنا أتعابه من الميزانية، وبنينا بقية الفريق حوله." },
    sum: { cost: "التكلفة:", budget: "الميزانية:", left: "المتبقي:", ok: "✓ اجتاز الفحص النهائي", warn: "⚠️ ملاحظات بالفحص" },
    inf: { head: "⛔ ما قدرنا نكوّن فريق بالشروط الحالية", conc: "أقل تنازل يحل المشكلة (اختر واحد):", tryWi: "جرّب تعديل الميزانية أو الجدول من شريط «ماذا لو؟»." },
    copy: "📋 نسخ", copied: "✓ تم النسخ", copyFail: "تعذّر النسخ، انسخ النص يدوياً.", micFail: "ما قدرت أسمعك، جرّب مرة ثانية أو اكتب.",
    pin: { title: "اقترح عضواً ونبني الفريق حوله", sub: "اختياري — يُثبَّت العضو في دوره كشرط إلزامي، ويُحسب الباقي حول ميزانيته وتوفره وشبكة تعاوناته.",
           db: "من قاعدة الممارسين", custom: "اسم من خارجها", role: "الدور", search: "ابحث بالاسم أو التخصص أو المدينة…",
           name: "اسم الشخص", cost: "الأتعاب التقديرية (اختياري)", add: "ثبّت", empty: "لا يوجد أعضاء مقترحون بعد.",
           noRes: "لا نتائج", needSel: "اختر ممارساً من القائمة أولاً.", needName: "اكتب اسم الشخص.", ext: "خارجي" },
    rp: { service: "خدمة تشكيل الفرق الثقافية — الصندوق الثقافي", kicker: "تقرير تنفيذي", title: "التقرير النهائي للمشروع",
          generated: "تاريخ الإصدار", ref: "المرجع", card: "بطاقة المشروع", budget: "تفصيل الميزانية", total: "الميزانية الكلية",
          teamCost: "تكلفة الفريق", left: "المتبقي", share: "من الميزانية", perRole: "التكلفة حسب الدور", team: "الفريق والبدلاء",
          role: "الدور", member: "العضو", cost: "التكلفة", fit: "الملاءمة", backup: "البديل", why: "مبررات الاختيار",
          timeline: "الجدول الزمني المرحلي", phase: "المرحلة", period: "الفترة", permits: "التصاريح المطلوبة", brief: "موجز المشروع",
          noPermits: "لا توجد تصاريح مسجلة لهذا القطاع.", checkOk: "اجتاز الفريق الفحص النهائي الآلي (الميزانية، التوفر، الموقع، صحة البيانات).",
          checkWarn: "ملاحظات الفحص النهائي:", foot: "أُعدّ هذا التقرير آلياً بواسطة وصل من بيانات تجريبية؛ التكاليف تقديرية وتخضع للتفاوض.",
          style: "طابع العمل", idea: "الفكرة", deadlines: "المواعيد الحرجة والالتزامات", noDeadlines: "لا توجد مواعيد حرجة حالياً." },
    pf: { kicker: "ملف الممارس", fee: "نطاق الأتعاب", collab: "تعاونات سابقة", works: "معرض الأعمال", remote: "يعمل عن بُعد",
          verified: "✓ ترخيص موثّق", rising: "🌟 موهبة صاعدة", inTeam: "في فريقك: ", noWorks: "لا توجد أعمال مسجلة في قاعدة وصل لهذا العضو.",
          extNote: "هذا العضو مقترح من خارج قاعدة الممارسين، لذلك لا يتوفر له ملف أعمال موثّق.", with: "بالتعاون مع", unknownFee: "غير محدد", zoom: "عرض الصورة بالحجم الكامل" },
  },
  en: {
    title: "Wasl — Cultural Development Fund", langBtn: "العربية", arrow: "→", sarUnit: "SAR",
    welcome: "Welcome to Wasl! 👋 What cultural project do you have in mind? Describe it in your own words and I'll fill in the details and build the right team. (Tip: the assistant understands Arabic best.)",
    starters: [["Short documentary", "فيلم وثائقي قصير"], ["Heritage fashion show", "عرض أزياء تراثي"], ["Heritage pavilion", "معرض أو جناح تراثي"]],
    intakeDone: "Great — I have the full picture 👌 Review the needs tree below, drop what you don't need, optionally suggest a member, then press “Build the team”.",
    intakeOver: "Review the needs tree and press “Build the team” — after that you can keep chatting with me as your project advisor.",
    adv: { ready: "Your team is ready 🎉 The chat stays open: ask me about the workflow between members, how to use the remaining budget, permits, or any change you're considering.",
           readyInf: "No team fits the current constraints yet, but the chat stays open: ask me which concession makes most sense or how to adjust the plan.",
           ld: "Reviewing your project…",
           starters: [["Workflow between members?", "وش تسلسل العمل بين الفريق؟"], ["How to use the remaining budget?", "كيف أوزع الميزانية المتبقية؟"], ["Which permits do I need?", "وش التصاريح المطلوبة؟"]] },
    ct: { kicker: "CONTACT DETAILS", person: "Direct contact", company: "Company / affiliation", phone: "Mobile", tel: "Phone", email: "Email",
          web: "Website", call: "Call", mail: "Email", visit: "Visit", portfolio: "View portfolio →", open: "📇 Contact details",
          none: "No contact details: this member was suggested from outside the Wasl database.", self: "This is a company — its details are below.",
          noCompany: "No affiliated company.", demo: "Demo data for illustration only." },
    noServer: "Can't reach the server. Make sure it is running.", errCode: "Error {n}",
    ld: { start: "Reading your idea and analysing the project…", msg: "Understanding your reply…", build: "Searching practitioners and building the best team… (may take a moment)",
          wi: "Recalculating…", conc: "Applying the concession and rebuilding…", reject: "Member declined… swapping in the backup",
          card: "Updating dates and recalculating schedule, team and critical deadlines…" },
    health: { ok: "● System ready", cold: "● Models not loaded", nollm: " · no LLM", down: "● Server offline", checking: "… checking" },
    FIELDS: { sector: "Sector", stage: "Stage", budget: "Budget", city: "City", start_date: "Start date", deadline: "Deadline",
              show_date: "Official show / launch date", style: "Work style" },
    dl: { empty: "Critical deadlines (permits, team availability, show day) appear here automatically once dates and the team are set.", n: "{n} critical",
          kind: { availability: "Team availability", permit: "Permit", show: "Show day" } },
    mx: { budget: "Budget", loc: "Location", avail: "Availability", exp: "Specialty & experience", ofBudget: "of budget",
          local: "Good fit — {city}", remote: "Remote", remoteFrom: "Remote · {city}", oos: "Out of scope (+{p}%)",
          full: "Available for the whole project period", win: "Available {a} – {b}", role: "Role window: {a} → {b}",
          notCover: "⚠ Doesn't fully cover the role window", works: "{n} documented works", since: "Since {y}", match: "Same sector" },
    emblem: { male: "Iqal Muqassab (gold-threaded iqal)", female: "Golden heritage Hama (headpiece)" },
    editHint: "✎ Editable",
    SECTORS: { film: "Film production", fashion: "Fashion", heritage: "Heritage & exhibitions" },
    STAGES: { planning: "Planning", pre_production: "Pre-production", design: "Design" },
    PHASES: { pre_production: "Pre-production", production: "Production", post_production: "Post-production", distribution: "Distribution",
      design: "Design", show: "Show", marketing: "Marketing", research: "Research", build: "Build", operation: "Operation" },
    STATUS: { clarifying: "Chat", needs_review: "Needs review", built: "Team ready", infeasible: "Not feasible yet" },
    SCORE: { specialty: "Specialty", past_work_similarity: "Past-work fit", location: "Location", budget: "Budget", availability: "Availability" },
    PILL: { known: "✓ Known", assumed: "~ Assumed", missing: "? Missing" },
    TYPE: { individual: "Individual", company: "Company" },
    none: "None", noEvents: "Nothing yet",
    build: "Build the team →", rebuild: "↻ Rebuild the team",
    tree: { root: "PROJECT", core: "Core roles", important: "Important roles", optional: "Optional roles",
            coreEn: "أدوار أساسية", importantEn: "أدوار مهمة", optionalEn: "أدوار مكملة",
            mentioned: "You mentioned", inferred: "Inferred", remote: "Remote", conf: "Confidence", imp: "Importance", drop: "Drop",
            risk: "⚠️ If ignored:", pinned: "📌 Pinned:" },
    card: { fit: "Fit", rising: "🌟 Rising talent", collab: "🤝 Worked together", licensed: "✓ Licensed", backup: "Backup:",
            reject: "Simulate decline", pinned: "📌 Your pick", external: "External",
            oos: "↔ Outside usual scope", oosBase: "Base fee", oosFee: "Extra",
            extNote: "A person you suggested from outside the practitioner database: locked into this role, fee deducted from the budget, the rest of the team built around them." },
    sum: { cost: "Cost:", budget: "Budget:", left: "Remaining:", ok: "✓ Passed final check", warn: "⚠️ Check notes" },
    inf: { head: "⛔ We couldn't form a team under the current constraints", conc: "Smallest concession that fixes it (pick one):", tryWi: "Try adjusting budget or schedule in the What-If bar." },
    copy: "📋 Copy", copied: "✓ Copied", copyFail: "Couldn't copy — please copy manually.", micFail: "Couldn't hear you — try again or type.",
    pin: { title: "Suggest a member to build the team around", sub: "Optional — the member is locked into their role as a hard constraint; the rest is optimised around their fee, availability and collaborator network.",
           db: "From practitioners", custom: "External name", role: "Role", search: "Search by name, specialty or city…",
           name: "Person's name", cost: "Estimated fee (optional)", add: "Pin", empty: "No suggested members yet.",
           noRes: "No results", needSel: "Pick a practitioner from the list first.", needName: "Type the person's name.", ext: "external" },
    rp: { service: "Cultural team-building service — Cultural Development Fund", kicker: "EXECUTIVE REPORT", title: "Final Project Report",
          generated: "Issued", ref: "Reference", card: "Project card", budget: "Budget breakdown", total: "Total budget",
          teamCost: "Team cost", left: "Remaining", share: "of budget", perRole: "Cost by role", team: "Team & backups",
          role: "Role", member: "Member", cost: "Cost", fit: "Fit", backup: "Backup", why: "Justification",
          timeline: "Phased timeline", phase: "Phase", period: "Period", permits: "Required permits", brief: "Project brief",
          noPermits: "No permits recorded for this sector.", checkOk: "The team passed the automated final check (budget, availability, location, data integrity).",
          checkWarn: "Final-check notes:", foot: "Generated automatically by Wasl from demo data; costs are estimates and subject to negotiation.",
          style: "Work style", idea: "Idea", deadlines: "Critical deadlines & constraints", noDeadlines: "No critical deadlines right now." },
    pf: { kicker: "PRACTITIONER PROFILE", fee: "Fee range", collab: "Past collaborators", works: "Portfolio", remote: "Works remotely",
          verified: "✓ Verified license", rising: "🌟 Rising talent", inTeam: "In your team: ", noWorks: "No works recorded in the Wasl database for this member.",
          extNote: "This member was suggested from outside the practitioner database, so no verified portfolio is available.", with: "With", unknownFee: "Not set", zoom: "View full-size photo" },
    // static markup
    "stamp.official": "An official website of the Government of Saudi Arabia", "stamp.how": "How to verify",
    "stamp.t1": 'Official Saudi websites end with <span class="text-ok" dir="ltr">gov.sa</span>',
    "stamp.d1": 'All official government websites in Saudi Arabia end with <span dir="ltr">gov.sa</span>',
    "stamp.t2": 'Government websites use the <span class="text-ok" dir="ltr">HTTPS</span> protocol',
    "stamp.d2": 'Secure websites in Saudi Arabia use <span dir="ltr">HTTPS</span> encryption.',
    "nav.funding": "Cultural Funding", "nav.invest": "Investment", "nav.namaa": "Namaa Enablement Services", "nav.accel": "Accelerators",
    "nav.incent": "Incentives", "nav.vouchers": "Vouchers", "nav.consult": "Consulting → Wasl", "nav.more": "More", "nav.about": "About the Fund",
    "nav.contact": "Contact us", "nav.stories": "Success stories", "nav.news": "News", "nav.login": "Log in", "nav.new": "+ New project",
    "bc.home": "Home", "bc.consult": "Consulting", "bc.wasl": "Wasl",
    "hero.kicker": "Ask for advice..", "hero.title": "Wasl — your smart advisor for building cultural teams",
    "hero.sub": "Describe your project in plain words; Wasl identifies its needs and assembles the best-fit team within your budget and timeline.",
    "demo.film": "Documentary in Al-Ahsa", "demo.fashion": "Fashion show in Riyadh", "demo.heritage": "Heritage pavilion in AlUla", "demo.tight": "Tight-budget scenario",
    "s1.step": "STEP 1", "s1.title": "Describe the project", "btn.send": "Send",
    "ph.input": "Type your idea or answer here… (Arabic works best)",
    "s2.step": "STEP 2", "s2.title": "Review the needs", "s2.sub": "Needs tree by importance",
    "wi.title": "What if?", "wi.budget": "Budget", "wi.sar": "SAR", "wi.shift": "Shift schedule", "wi.days": "days", "wi.remote": "Remote work",
    "wi.apply": "Apply", "wi.pin": "📌 Suggest a member", "rp.open": "View & export final report", "rp.bar": "Final report", "rp.print": "Print / Save PDF",
    "tab.timeline": "Timeline", "tab.brief": "Project brief", "card.title": "Project card",
    "st.known": "✓ Known", "st.assumed": "~ Assumed", "st.missing": "? Missing", "dl.title": "Critical Deadlines",
    "ft.about": "The Cultural Development Fund was founded in 2021 to empower the cultural sector and strengthen its sustainability, in support of Saudi Vision 2030.",
    "ft.who": "Who we are", "ft.services": "Our services", "ft.wasl": "↳ Wasl", "ft.support": "Support", "ft.faq": "FAQ", "ft.privacy": "Privacy policy",
    "ft.note": "Wasl — illustrative prototype of a cultural team-building service (demo data)",
  },
};
let LANG = (() => { try { return localStorage.getItem("wasl.lang") === "en" ? "en" : "ar"; } catch { return "ar"; } })();
const T = (path, vars) => {
  const get = (d) => path.split(".").reduce((o, k) => (o == null ? o : o[k]), d);
  let s = get(I18N[LANG]); if (s === undefined) s = get(I18N.ar); if (s === undefined) s = path;
  if (vars && typeof s === "string") for (const [k, v] of Object.entries(vars)) s = s.replaceAll(`{${k}}`, v);
  return s;
};
const tm = (map, v) => (v == null ? v : T(map)?.[v] ?? v);
const sar = (n) => (n == null ? "—" : LANG === "ar" ? Number(n).toLocaleString("ar-SA") + " ريال" : "SAR " + Number(n).toLocaleString("en-US"));
const num = (n) => Number(n).toLocaleString(LANG === "ar" ? "ar-SA" : "en-US");
// share of budget, 1 decimal (e.g. 18.5% / ١٨٫٥٪)
const share = (x) => (x == null || !isFinite(x) ? "—" : new Intl.NumberFormat(LANG === "ar" ? "ar-SA" : "en-US", { style: "percent", minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(x));
// Gregorian dates in both languages (ar-SA defaults to the Hijri calendar, so pin gregory)
const fmtDate = (d) => { if (!d) return "—"; const x = new Date(d + "T00:00:00");
  return isNaN(x) ? d : x.toLocaleDateString(LANG === "ar" ? "ar-SA-u-ca-gregory" : "en-GB", { day: "numeric", month: "short", year: "numeric" }); };
const bdi = (s) => `<bdi>${esc(s)}</bdi>`;

// ---------------------------------------------------------------- heritage emblems (inline SVG, CDF palette)
// Male: العقال المقصب — double black cord wrapped in gold thread (qasab), front knot, hanging tassels.
// Female: الهامة التراثية الذهبية — arched golden headpiece of linked discs, central ruby medallion, coin fringe.
const GOLD = "#C8A27A", GOLD_D = "#8C6239", GOLD_L = "#E9D9C6", INK = "#0D121C";
function emblem(gender, cls = "") {
  const title = esc(T("emblem." + gender));
  if (gender === "male") {
    const ring = (cy) => `
      <ellipse cx="32" cy="${cy}" rx="21" ry="7.2" fill="none" stroke="${INK}" stroke-width="5"/>
      <ellipse cx="32" cy="${cy}" rx="21" ry="7.2" fill="none" stroke="${GOLD}" stroke-width="3.2" stroke-dasharray="2.6 1.6"/>
      <ellipse cx="32" cy="${cy}" rx="21" ry="7.2" fill="none" stroke="${GOLD_L}" stroke-width=".7" stroke-dasharray="1 3.2" stroke-dashoffset="1"/>`;
    const tassel = (x, y, len) => `
      <path d="M${x} ${y} q 1.2 ${len * .5} 0 ${len}" stroke="${INK}" stroke-width="1.6" fill="none"/>
      <path d="M${x - 2.4} ${y + len} h4.8 l-.9 7.5 h-3 z" fill="${GOLD}" stroke="${INK}" stroke-width=".8"/>
      <path d="M${x - 1.6} ${y + len + 7.5} v3 M${x} ${y + len + 7.5} v3.6 M${x + 1.6} ${y + len + 7.5} v3" stroke="${INK}" stroke-width=".9"/>`;
    return `<svg class="emblem ${cls}" viewBox="0 0 64 64" role="img" aria-label="${title}"><title>${title}</title>
      <rect width="64" height="64" fill="#F6EFE7"/>
      <path d="M0 56h64v8H0z" fill="${INK}"/>
      <path d="M2 60l3-3 3 3 3-3 3 3 3-3 3 3 3-3 3 3 3-3 3 3 3-3 3 3 3-3 3 3 3-3 3 3 3-3 3 3 3-3 3 3 3-3" stroke="${GOLD}" stroke-width="1" fill="none"/>
      ${tassel(46.5, 30, 10)}${tassel(50.5, 29, 13)}
      ${ring(22)}${ring(31)}
      <rect x="29" y="34.2" width="6" height="6" transform="rotate(45 32 37.2)" fill="${GOLD}" stroke="${INK}" stroke-width="1"/>
      <circle cx="32" cy="37.2" r="1.1" fill="${INK}"/></svg>`;
  }
  if (gender === "female") {
    const pts = [...Array(9)].map((_, i) => { const t = i / 8, x = 9 + 46 * t, y = 35 - 13 * Math.sin(Math.PI * t); return [x, y]; });
    const fringe = pts.filter((_, i) => i !== 4).map(([x, y]) => `
      <path d="M${x.toFixed(1)} ${(y + 3).toFixed(1)} v6" stroke="${GOLD_D}" stroke-width=".8"/>
      <circle cx="${x.toFixed(1)}" cy="${(y + 10.5).toFixed(1)}" r="1.8" fill="${GOLD}" stroke="${GOLD_D}" stroke-width=".6"/>`).join("");
    const discs = pts.map(([x, y], i) => i === 4 ? "" : `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="3.1" fill="${GOLD}" stroke="${INK}" stroke-width=".9"/><circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="1" fill="${GOLD_L}"/>`).join("");
    const chain = `M${pts.map(([x, y]) => `${x.toFixed(1)} ${y.toFixed(1)}`).join(" L")}`;
    return `<svg class="emblem ${cls}" viewBox="0 0 64 64" role="img" aria-label="${title}"><title>${title}</title>
      <rect width="64" height="64" fill="#F6EFE7"/>
      <path d="M0 56h64v8H0z" fill="${INK}"/>
      <path d="M2 60l3-3 3 3 3-3 3 3 3-3 3 3 3-3 3 3 3-3 3 3 3-3 3 3 3-3 3 3 3-3 3 3 3-3 3 3 3-3 3 3 3-3" stroke="${GOLD}" stroke-width="1" fill="none"/>
      <path d="M27 12 l5 -5 l5 5 l-5 4z" fill="${GOLD}" stroke="${INK}" stroke-width=".9"/>
      <path d="${chain}" fill="none" stroke="${INK}" stroke-width="2.2"/>
      <path d="${chain}" fill="none" stroke="${GOLD}" stroke-width="1" stroke-dasharray="1.4 1.2"/>
      ${fringe}${discs}
      <path d="M32 31.5 v4" stroke="${GOLD_D}" stroke-width=".9"/>
      <path d="M32 35 l3 4.5 l-3 3.5 l-3 -3.5z" fill="${GOLD}" stroke="${INK}" stroke-width=".8"/>
      <circle cx="32" cy="23.5" r="7.6" fill="${GOLD}" stroke="${INK}" stroke-width="1.1"/>
      <circle cx="32" cy="23.5" r="5.4" fill="none" stroke="${GOLD_D}" stroke-width=".7" stroke-dasharray=".9 1.1"/>
      <circle cx="32" cy="23.5" r="3.1" fill="#B42318" stroke="${INK}" stroke-width=".7"/>
      <circle cx="31" cy="22.5" r=".9" fill="#fff" fill-opacity=".8"/></svg>`;
  }
  return "";
}
// emblem for a person, initials tile for companies / unknown
const avatar = (p, cls = "") => (p?.gender ? emblem(p.gender, cls) : `<div class="emblem-co ${cls === "lg" ? "!w-[72px] !h-[72px] text-2xl" : ""}">${esc(initials(p?.name))}</div>`);

function applyStatic() {
  const html = document.documentElement;
  html.lang = LANG; html.dir = LANG === "ar" ? "rtl" : "ltr";
  document.title = T("title");
  $$("[data-i18n]").forEach((el) => {
    if (el.dataset.ar === undefined) el.dataset.ar = el.innerHTML;
    el.innerHTML = LANG === "ar" ? el.dataset.ar : I18N.en[el.dataset.i18n] ?? el.dataset.ar;
  });
  $$("[data-i18n-ph]").forEach((el) => {
    if (el.dataset.arPh === undefined) el.dataset.arPh = el.placeholder;
    el.placeholder = LANG === "ar" ? el.dataset.arPh : I18N.en[el.dataset.i18nPh] ?? el.dataset.arPh;
  });
  const lt = $("#langToggle");
  lt.textContent = T("langBtn"); lt.lang = LANG === "ar" ? "en" : "ar"; lt.dir = LANG === "ar" ? "ltr" : "rtl";
  $("#copy").textContent = T("copy");
}
function setLang(l) {
  LANG = l; try { localStorage.setItem("wasl.lang", l); } catch {}
  applyStatic(); renderHealth();
  if (S) renderView(S); else reset();
  renderPinHosts();
  if (!$("#reportModal").hidden) renderReport();
  if (!$("#pfModal").hidden && PF_OPEN) openPortfolio(PF_OPEN);
  if (!$("#ctModal").hidden && CT_OPEN) openContact(...CT_OPEN);
}

// ================================================================ state
const DEMOS = {
  // the work style is no longer typed in a notes box: the Clarifier asks for it as the final intake step
  film: "أبغى أسوي فيلم وثائقي قصير عن الحرف اليدوية في الأحساء والميزانية 120 ألف ريال",
  fashion: "عرض أزياء في الرياض لمجموعة مستوحاة من التراث السعودي، الميزانية 150 ألف ريال من 2027-02-01 إلى 2027-04-20",
  heritage: "جناح معرض تراثي في العلا يعرض قطع أثرية بلوحات ثنائية اللغة، الميزانية 100 ألف ريال من 2027-02-15 إلى 2027-04-25",
  tight: "جناح معرض تراثي في العلا بميزانية 40 ألف ريال من 2027-02-15 إلى 2027-04-25",
};
let S = null;        // last session view
let busy = false;
let PRS = {};        // practitioner id -> public profile (GET /api/practitioners)
let PINS = [];       // [{need_id, practitioner_id?, name?, estimated_cost?}]
let PF_OPEN = null;  // practitioner id shown in the portfolio modal
let CT_OPEN = null;  // [practitioner id, focus] shown in the contact modal
let ADV_SEEN = 0;    // consultation messages already rendered in the chat
let HEALTH;          // last /api/health payload (null = offline)

// ================================================================ api
async function api(path, body, label) {
  if (busy) return null;
  busy = true; setLoading(label);
  const t0 = performance.now();
  try {
    const r = await fetch(path, body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : T("errCode", { n: r.status }));
    data._ms = Math.round(performance.now() - t0);
    $("#error").classList.add("hidden");
    return data;
  } catch (e) {
    showError(e.message === "Failed to fetch" ? T("noServer") : e.message);
    return null;
  } finally { busy = false; setLoading(null); }
}
async function loadPrs() {
  if (Object.keys(PRS).length) return PRS;
  try { PRS = Object.fromEntries((await (await fetch("/api/practitioners")).json()).map((p) => [p.id, p])); } catch {}
  return PRS;
}
function showError(m) { $("#errorText").textContent = "⚠️ " + m; $("#error").classList.remove("hidden"); }
function setLoading(label) {
  $$("button").forEach((b) => (b.disabled = !!label && !b.closest("#error")));
  $("#loading")?.remove();
  if (label) bubble("bot", `<span class="inline-flex items-center gap-2 text-muted"><span class="spin"></span>${esc(label)}</span>`, "loading");
}

// ================================================================ chat
function bubble(who, html, id) {
  const d = document.createElement("div");
  d.className = who === "me" ? "flex justify-start" : "flex justify-end";
  if (id) d.id = id;
  d.innerHTML = `<div class="max-w-[85%] px-3.5 py-2.5 text-sm leading-7 ${who === "me" ? "bg-ink text-white" : "bg-canvas border border-line"}">${html}</div>`;
  $("#chat").appendChild(d); $("#chat").scrollTop = 1e9;
}
function chips(list) {  // items: "text" or [label, value]
  $("#chips").innerHTML = (list || []).map((q) => { const [l, v] = Array.isArray(q) ? q : [q, q];
    return `<button class="chip" data-q="${esc(v)}">${esc(l)}</button>`; }).join("");
}
async function send(text) {
  text = text.trim();
  if (!text) return;
  if (S && S.status === "needs_review") return showError(T("intakeOver"));
  const consulting = S && (S.status === "built" || S.status === "infeasible");
  bubble("me", esc(text)); $("#input").value = ""; chips([]);
  const r = S ? await api(`/api/sessions/${S.session_id}/message`, { text }, consulting ? T("adv.ld") : T("ld.msg"))
              : await api("/api/sessions", { idea: text, lang: LANG }, T("ld.start"));
  if (r) render(r);
}

// ================================================================ render
function render(r) {  // new server state: chat side effects + view
  const prev = S; S = r;
  if (r.status === "clarifying") {
    if (r.question) bubble("bot", esc(r.question));
    chips(r.quick_replies);
  } else if (r.status === "built" || r.status === "infeasible") {
    const n = r.consultation_count || 0, fresh = n > ADV_SEEN;
    if (fresh) {  // new Advisor answer(s): the user's own bubble is already shown by send()
      (r.consultation || []).slice(-(n - ADV_SEEN)).filter((m) => m.role === "assistant")
        .forEach((m) => bubble("bot", esc(m.text).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/^\s*[-*]\s+/gm, "• ").replace(/\n/g, "<br>")));
      ADV_SEEN = n;
    } else if (!prev || (prev.status !== "built" && prev.status !== "infeasible")) {
      bubble("bot", esc(T(r.status === "built" ? "adv.ready" : "adv.readyInf")));
    }
    chips(fresh && (r.advisor_quick_replies || []).length ? r.advisor_quick_replies : T("adv.starters"));
  } else {
    chips([]);
    if (prev?.status === "clarifying" || !prev) {
      if (r.style_rationale) bubble("bot", esc(r.style_rationale));  // tailored creative direction ("اقترح لي طابع")
      bubble("bot", esc(T("intakeDone")));
    }
  }
  if (r.status === "built" || r.status === "infeasible") PINS = (r.pins || []).map((p) => ({ ...p }));
  renderView(r);
}
function renderView(r) {  // pure re-render (also used on language switch)
  $("#statusPill").textContent = tm("STATUS", r.status);
  renderCard(r.card);
  renderDeadlines(r.deadlines);
  $("#needsSec").classList.toggle("hidden", r.status === "clarifying");
  if (r.status !== "clarifying") { renderNeeds(r); renderPinHosts(); }
  const res = r.status === "built" || r.status === "infeasible";
  $("#teamSec").classList.toggle("hidden", !res);
  if (res) renderResults(r);
}

const DATE_FIELDS = ["start_date", "deadline", "show_date"];
function fmtField(k, v) {
  return v == null ? "—" : k === "budget" ? sar(v) : k === "sector" ? tm("SECTORS", v) : k === "stage" ? (T("STAGES")[v] || tm("PHASES", v))
    : DATE_FIELDS.includes(k) ? fmtDate(v) : v;
}
const PILL_CLS = { known: "bg-ok-soft text-ok", assumed: "bg-accent-soft text-accent", missing: "bg-slate-soft text-slate" };
function renderCard(c) {
  const editable = !!S;  // dates are editable as soon as a session exists; the backend re-plans everything
  $("#card").innerHTML = Object.entries(T("FIELDS")).map(([k, label]) => {
    const f = c?.[k] || { status: "missing" };
    const extra = k === "sector" && (c?.secondary_sectors || []).length ? " + " + c.secondary_sectors.map((s) => tm("SECTORS", s)).join(" + ") : "";
    const val = editable && DATE_FIELDS.includes(k)
      ? `<input type="date" class="card-date" data-card="${k}" value="${esc(f.value || "")}" aria-label="${esc(label)}" title="${esc(T("editHint"))}">`
      : `<span class="${k === "style" ? "max-w-[11rem] truncate" : ""}" title="${esc(fmtField(k, f.value) + extra)}">${esc(fmtField(k, f.value) + extra)}</span>`;
    return `<div class="flex items-center justify-between gap-2"><dt class="text-muted">${label}</dt><dd class="flex items-center gap-2 font-medium text-end min-w-0">${val}<span class="pill ${PILL_CLS[f.status]}">${T("PILL")[f.status]}</span></dd></div>`;
  }).join("") + (editable ? `<div class="card-edit-hint pt-1">${T("editHint")}: ${DATE_FIELDS.map((k) => T("FIELDS")[k]).join(" · ")}</div>` : "");
}
async function editCard(field, value) {
  if (!S || !value) return;
  const r = await api(`/api/sessions/${S.session_id}/card`, { [field]: value }, T("ld.card"));
  if (!r) return renderCard(S.card);  // refused (e.g. show date before start): restore the previous value
  S = r;
  if (r.status === "built" || r.status === "infeasible") PINS = (r.pins || []).map((p) => ({ ...p }));
  renderView(r);
  if (!$("#reportModal").hidden) renderReport();
}

// ---------------------------------------------------------------- critical deadlines & constraints
const DL_ICON = {
  availability: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/></svg>`,
  permit: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 2h9l5 5v15H6z"/><path d="M9 13l2 2 4-4"/></svg>`,
  show: `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="5" width="18" height="16"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>`,
};
const dlItem = (a) => `<li class="dl-item ${a.severity}"><span class="dl-ic">${DL_ICON[a.kind] || ""}</span>
  <div class="min-w-0"><div>${esc(LANG === "ar" ? a.ar : a.en)}</div>
    <div class="dl-when">${esc(T("dl.kind")[a.kind] || a.kind)}${a.date ? ` · ${fmtDate(a.date)}` : ""}</div></div></li>`;
function renderDeadlines(list) {
  list = list || [];
  const crit = list.filter((a) => a.severity === "high").length;
  $("#dlCount").textContent = crit ? T("dl.n", { n: num(crit) }) : "";
  $("#deadlines").innerHTML = list.length ? list.map(dlItem).join("") : `<li class="text-xs text-muted leading-6 px-2">${T("dl.empty")}</li>`;
}

// ---------------------------------------------------------------- 1) needs tree
const level = (imp) => (imp >= 0.85 ? "core" : imp >= 0.6 ? "important" : "optional");
const pinName = (p) => (p.practitioner_id ? PRS[p.practitioner_id]?.name || p.practitioner_id : p.name);
function renderNeeds(r) {
  const locked = r.status !== "needs_review";
  $("#build").textContent = locked ? T("rebuild") : T("build");
  const dropped = new Set($$(".drop:checked").map((x) => x.value));
  const groups = { core: [], important: [], optional: [] };
  r.needs.forEach((n) => groups[level(n.importance)].push(n));
  const c = r.card || {}, ar = T("arrow");
  const leaf = (n) => {
    const pin = PINS.find((p) => p.need_id === n.id);
    return `<li class="tree-leaf"><div class="leaf ${dropped.has(n.id) ? "is-dropped" : ""}">
      <div class="flex flex-wrap items-start justify-between gap-2">
        <div class="font-bold leaf-role">${esc(n.role)}</div>
        <div class="flex gap-1 flex-wrap">
          ${n.mentioned ? `<span class="pill bg-ok-soft text-ok">${T("tree.mentioned")}</span>` : `<span class="pill bg-accent-soft text-accent">${T("tree.inferred")}</span>`}
          <span class="pill bg-slate-soft text-slate">${esc(tm("PHASES", n.phase))}</span>
          ${n.remote_ok ? `<span class="pill bg-slate-soft text-slate">${T("tree.remote")}</span>` : ""}
        </div>
      </div>
      ${n.reason ? `<p class="text-sm text-sub leading-6 mt-1">${esc(n.reason)}</p>` : ""}
      ${n.consequence_if_ignored ? `<p class="text-xs text-warn leading-5 mt-1">${T("tree.risk")} ${esc(n.consequence_if_ignored)}</p>` : ""}
      ${pin ? `<p class="text-xs mt-2"><span class="pill bg-accent-soft text-accent">${T("tree.pinned")} ${esc(pinName(pin))}</span></p>` : ""}
      <div class="flex items-center justify-between gap-3 text-xs text-muted mt-2">
        <span class="tag gold">${T("tree.imp")}: ${num(pct(n.importance))}%</span>
        <label class="flex items-center gap-1 cursor-pointer"><input type="checkbox" class="drop" value="${esc(n.id)}" ${dropped.has(n.id) ? "checked" : ""}> ${T("tree.drop")}</label></div>
    </div></li>`;
  };
  const branches = Object.entries(groups).filter(([, ns]) => ns.length).map(([lv, ns]) => `
    <div class="tree-branch lvl-${lv}">
      <div class="tree-bnode"><span class="sq"></span>${T("tree." + lv)} <span class="en">${T("tree." + lv + "En")}</span><span class="cnt">${num(ns.length)}</span></div>
      <ul class="tree-leaves">${ns.map(leaf).join("")}</ul>
    </div>`).join("");
  $("#needs").innerHTML = `<div class="min-w-[520px]">
    <div class="tree-root"><span class="k">${T("tree.root")}</span>
      <span class="text-lg-semibold">${esc([c.sector?.value, ...(c.secondary_sectors || [])].filter(Boolean).map((s) => tm("SECTORS", s)).join(" + ") || "—")}${c.city?.value ? " · " + esc(c.city.value) : ""}</span>
      <span class="text-xs text-white/70">${c.budget?.value ? sar(c.budget.value) : ""}${c.start_date?.value ? ` · <span dir="ltr">${esc(c.start_date.value)} ${ar} ${esc(c.deadline?.value || "")}</span>` : ""}</span>
    </div>
    <div class="tree-levels">${branches}</div></div>`;
  const tips = (r.events || []).filter((e) => e.startsWith("اقتراح إضافي"));
  $("#tips").innerHTML = tips.length ? "💡 " + tips.map(esc).join(" · ") : "";
}

// ---------------------------------------------------------------- 3) pin editor (needs step + What-If bar)
function renderPinHosts() { $$("[data-pinhost]").forEach(renderPinHost); $("#wiPinCount").textContent = PINS.length ? `(${num(PINS.length)})` : ""; }
function renderPinHost(host) {
  if (!S || !S.needs) { host.innerHTML = ""; return; }
  const mode = host.dataset.mode || "db";
  const roleSel = host.querySelector(".pin-role")?.value;
  const roles = S.needs.map((n) => `<option value="${esc(n.id)}" ${n.id === roleSel ? "selected" : ""}>${esc(n.role)}</option>`).join("");
  const nameOf = (id) => S.needs.find((n) => n.id === id)?.role || id;
  host.innerHTML = `
    <div class="flex flex-wrap items-start justify-between gap-3 mb-3">
      <div class="max-w-xl"><div class="font-bold text-sm text-ink">📌 ${T("pin.title")}</div><div class="text-xs text-muted leading-5 mt-0.5">${T("pin.sub")}</div></div>
      <div class="seg" role="tablist"><button type="button" data-pinmode="db" class="${mode === "db" ? "on" : ""}">${T("pin.db")}</button><button type="button" data-pinmode="custom" class="${mode === "custom" ? "on" : ""}">${T("pin.custom")}</button></div>
    </div>
    <div class="grid gap-2 ${mode === "db" ? "md:grid-cols-[minmax(0,1fr)_minmax(0,1.5fr)_auto]" : "md:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)_minmax(0,.9fr)_auto]"} text-ink">
      <select class="pin-field pin-role" aria-label="${T("pin.role")}">${roles}</select>
      ${mode === "db"
        ? `<div class="relative"><input class="pin-field pin-q" autocomplete="off" placeholder="${T("pin.search")}" value="${esc(host.dataset.sel ? PRS[host.dataset.sel]?.name || "" : "")}"><div class="pin-results" hidden></div></div>`
        : `<input class="pin-field pin-name" placeholder="${T("pin.name")}"><input class="pin-field pin-cost" type="number" min="0" step="500" placeholder="${T("pin.cost")}">`}
      <button type="button" class="btn btn-primary" data-pinadd>${T("pin.add")}</button>
    </div>
    <div class="flex flex-wrap gap-2 mt-3">${PINS.length ? PINS.map((p) => `
      <span class="pin-chip"><span>📌 <b>${esc(pinName(p))}</b>${p.practitioner_id ? "" : ` <span class="text-muted">(${T("pin.ext")})</span>`} ${T("arrow")} ${esc(nameOf(p.need_id))}${p.estimated_cost != null ? ` · ${sar(p.estimated_cost)}` : ""}</span>
        <button type="button" data-unpin="${esc(p.need_id)}" aria-label="remove">✕</button></span>`).join("")
      : `<span class="text-xs text-muted">${T("pin.empty")}</span>`}</div>`;
}
function renderPinResults(host) {
  const box = host.querySelector(".pin-results"), q = host.querySelector(".pin-q").value.trim().toLowerCase();
  const sector = S?.card?.sector?.value, need = S?.needs?.find((n) => n.id === host.querySelector(".pin-role").value);
  const sec = need?.sector || sector;
  const list = Object.values(PRS)
    .filter((p) => !q || `${p.name} ${p.specialty} ${p.city}`.toLowerCase().includes(q))
    .sort((a, b) => (b.sectors.includes(sec) - a.sectors.includes(sec)) || a.name.localeCompare(b.name, "ar"))
    .slice(0, 8);
  box.innerHTML = list.length ? list.map((p) => `
    <button type="button" data-pinpick="${esc(p.id)}" class="${host.dataset.sel === p.id ? "on" : ""}">
      <span class="min-w-0"><b>${esc(p.name)}</b>${p.is_rising_talent ? " 🌟" : ""}<span class="block text-xs text-muted truncate">${esc(p.specialty)} · ${esc(p.city)}</span></span>
      <span class="text-xs text-muted whitespace-nowrap">${sar(p.typical_fee_min)} – ${num(p.typical_fee_max)}</span></button>`).join("")
    : `<div class="p-3 text-xs text-muted">${T("pin.noRes")}</div>`;
  box.hidden = false;
}
async function addPin(host) {
  const need_id = host.querySelector(".pin-role").value;
  let pin;
  if ((host.dataset.mode || "db") === "db") {
    const id = host.dataset.sel;
    if (!id) return showError(T("pin.needSel"));
    pin = { need_id, practitioner_id: id };
  } else {
    const name = host.querySelector(".pin-name").value.trim(), cost = parseInt(host.querySelector(".pin-cost").value, 10);
    if (!name) return showError(T("pin.needName"));
    pin = { need_id, name, ...(cost >= 0 ? { estimated_cost: cost } : {}) };
  }
  PINS = PINS.filter((p) => p.need_id !== need_id && (!pin.practitioner_id || p.practitioner_id !== pin.practitioner_id));
  PINS.push(pin); delete host.dataset.sel;
  await pinsChanged();
}
async function pinsChanged() {
  renderPinHosts(); if (S) renderNeeds(S);
  if (S && (S.status === "built" || S.status === "infeasible")) await whatIf({ pins: true });
}

// ---------------------------------------------------------------- results
const nameBtn = (id, name, cls = "") => `<button type="button" class="pname ${cls}" data-contact="${esc(id)}">${esc(name)}</button>`;
const companyBtn = (id, name) => `<button type="button" class="cname" data-contact="${esc(id)}" data-focus="company">🏢 ${esc(name)}</button>`;
const contactOf = (id) => PRS[id]?.contact || S?.team?.find((m) => m.practitioner.id === id)?.practitioner?.contact || null;
function collabIds(r) {
  return new Set((r.notes || []).filter((n) => n.startsWith("collaboration bonus")).flatMap((n) => n.replace(/^collaboration bonus: | worked together before$/g, "").split(" & ")));
}
// Actionable, bar-free member metrics: exact budget share, location status pill, concrete availability, tags.
const MX_IC = {
  budget: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 3v9l6 5"/></svg>`,
  loc: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s7-7.5 7-13a7 7 0 0 0-14 0c0 5.5 7 13 7 13z"/><circle cx="12" cy="9" r="2.5"/></svg>`,
  avail: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="5" width="18" height="16"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>`,
  exp: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2l3 6.5 7 .8-5.2 4.8 1.4 7L12 17.6 5.8 21l1.4-7L2 9.3l7-.8z"/></svg>`,
};
function memberMetrics(m, sector) {
  const p = m.practitioner, a = m.availability || {}, loc = m.location || {};
  const row = (k, body) => `<div class="mx"><span class="mx-k">${MX_IC[k]}${T("mx." + k)}</span><div class="min-w-0">${body}</div></div>`;
  const locTxt = loc.kind === "out_of_scope" ? T("mx.oos", { p: num(loc.surcharge_pct ?? 5) })
    : loc.kind === "remote" ? T("mx.remoteFrom", { city: esc(loc.city || "") }) : T("mx.local", { city: esc(loc.city || p.city || "—") });
  const availTxt = a.full ? `<span class="avail-full">✓ ${T("mx.full")}</span>`
    : a.from ? `<span class="avail-win">${T("mx.win", { a: fmtDate(a.from), b: fmtDate(a.to) })}</span>` : "—";
  const tags = [...(p.specialties || []).slice(0, 3).map((s) => `<span class="tag">${esc(s)}</span>`),
    p.works_count ? `<span class="tag gold">${T("mx.works", { n: num(p.works_count) })}</span>` : "",
    p.since ? `<span class="tag gold">${T("mx.since", { y: esc(p.since) })}</span>` : "",
    sector && (p.sectors || []).includes(sector) ? `<span class="tag">✓ ${T("mx.match")}</span>` : ""].filter(Boolean).join(" ");
  return `<div class="border-y border-line py-1">
    ${row("budget", `<span class="mx-big">${share(m.budget_share)}</span> <span class="text-muted text-xs">${T("mx.ofBudget")}</span> <span class="text-xs text-sub">· ${sar(m.estimated_cost)}</span>`)}
    ${row("loc", `<span class="loc ${esc(loc.kind || "local")}"><i></i>${locTxt}</span>`)}
    ${row("avail", `${availTxt}<div class="text-[11px] text-muted mt-0.5">${T("mx.role", { a: fmtDate(a.role_from), b: fmtDate(a.role_to) })}${a.covers_role === false ? ` · <span class="text-danger">${T("mx.notCover")}</span>` : ""}</div>`)}
    ${row("exp", `<div class="flex flex-wrap gap-1">${tags || "—"}</div>`)}
  </div>`;
}
function renderResults(r) {
  if (document.activeElement?.id !== "wiBudget") { $("#wiBudget").value = r.budget ?? ""; $("#wiRange").value = r.budget ?? 100000; }
  $("#wiShift").value = r.overrides?.shift_days ?? 0;
  $("#wiRemote").checked = (r.overrides?.remote_needs || []).length > 0;

  const inf = $("#infeasible");
  inf.classList.toggle("hidden", r.status !== "infeasible");
  if (r.status === "infeasible") {
    inf.innerHTML = `<div class="font-bold text-danger mb-2">${T("inf.head")}</div>
      <ul class="text-sm space-y-1 mb-3" dir="rtl">${r.blocking.map((b) => `<li>• ${esc(b)}</li>`).join("")}</ul>
      ${r.concessions.length ? `<div class="text-sm font-semibold mb-2">${T("inf.conc")}</div>
      <div class="flex flex-wrap gap-2">${r.concessions.map((c) => `<button class="btn btn-primary !py-1.5 text-xs" data-conc="${esc(c.id)}">${esc(c.label)}</button>`).join("")}</div>` : `<div class="text-sm">${T("inf.tryWi")}</div>`}`;
  }
  const built = r.status === "built";
  $("#openReport").classList.toggle("hidden", !built);
  $("#summary").innerHTML = built ? `
    <span class="card px-3 py-2">${T("sum.cost")} <b>${sar(r.total_cost)}</b></span>
    <span class="card px-3 py-2">${T("sum.budget")} <b>${sar(r.budget)}</b></span>
    <span class="card px-3 py-2">${T("sum.left")} <b class="text-ok">${sar(r.budget - r.total_cost)}</b></span>
    <span class="card px-3 py-2">${r.check?.ok ? `<span class='text-ok'>${T("sum.ok")}</span>` : `<span class='text-danger'>${T("sum.warn")}</span>`}</span>` : "";
  $("#extraSec").classList.toggle("hidden", !built);
  if (!built) { $("#team").innerHTML = ""; return; }

  const collab = collabIds(r), ar = T("arrow");
  const sector = r.card?.sector?.value;
  $("#team").innerHTML = r.team.map((m) => {
    const p = m.practitioner;
    return `<div class="card p-4 space-y-3 ${m.pinned ? "!border-accent" : ""}">
      <div class="flex items-start justify-between gap-3">
        <div class="flex items-start gap-3 min-w-0">${avatar(p)}
        <div class="min-w-0"><div class="text-xs text-accent font-semibold">${esc(m.role)}</div><div class="font-bold text-lg">${nameBtn(p.id, p.name)}</div>
          ${p.contact?.company && p.type !== "company" ? `<div class="mt-0.5">${companyBtn(p.id, p.contact.company.name)}</div>` : ""}
          <div class="text-xs text-muted">${esc(p.city || "—")} · ${esc(tm("PHASES", m.phase))}</div></div></div>
        <div class="text-end shrink-0"><div class="font-bold">${sar(m.estimated_cost)}</div>${m.out_of_scope ? `<div class="text-[11px] text-muted whitespace-nowrap">${T("card.oosBase")} ${sar(m.out_of_scope.base_cost)} + ${num(m.out_of_scope.surcharge)}</div>` : ""}${m.external ? "" : `<div class="text-xs text-muted">${T("card.fit")} ${num(pct(m.score))}%</div>`}</div>
      </div>
      ${m.out_of_scope ? `<div class="oos-note" dir="${LANG === "ar" ? "rtl" : "ltr"}"><b>${T("card.oos")}</b> — ${esc(LANG === "ar" ? m.out_of_scope.note_ar : m.out_of_scope.note_en)}</div>` : ""}
      <div class="flex flex-wrap gap-1">
        ${m.pinned ? `<span class="pill bg-accent text-white">${T("card.pinned")}</span>` : ""}
        ${m.external ? `<span class="pill bg-slate-soft text-slate">${T("card.external")}</span>` : ""}
        ${p.is_rising_talent ? `<span class="pill bg-accent-soft text-accent">${T("card.rising")}</span>` : ""}
        ${collab.has(p.id) ? `<span class="pill bg-slate-soft text-ink">${T("card.collab")}</span>` : ""}
        ${p.verified_license ? `<span class="pill bg-ok-soft text-ok">${T("card.licensed")}</span>` : ""}
      </div>
      ${m.external ? `<p class="text-xs text-muted leading-5">${T("card.extNote")}</p>` : ""}
      ${memberMetrics(m, sector)}
      <p class="text-sm leading-7 bg-canvas border-s-2 border-ink p-3" dir="rtl">${esc(m.explanation)}</p>
      <div class="flex items-center justify-between gap-2 text-xs">
        <span class="text-muted">${T("card.backup")} ${m.backup ? `<b class="text-ink">${nameBtn(m.backup.id, m.backup.name)}</b> (${sar(m.backup.estimated_cost)})` : T("none")}</span>
        <button class="btn btn-danger !py-1 !px-2 text-xs shrink-0" data-reject="${esc(m.need_id)}">${T("card.reject")}</button>
      </div></div>`;
  }).join("");

  const ids = Object.fromEntries(r.team.map((m) => [m.practitioner.name, m.practitioner.id]));
  $("#tab-timeline").innerHTML = `<ol class="relative border-s-2 border-line ms-2 space-y-4">${r.timeline.map((t) => `
    <li class="ps-4 relative"><span class="absolute -start-[7px] top-1.5 w-3 h-3 bg-ink"></span>
      <div class="font-bold">${esc(tm("PHASES", t.phase) || t.phase_ar)} <span class="text-xs text-muted font-normal" dir="ltr">${esc(t.start)} ${ar} ${esc(t.end)}</span></div>
      <div class="text-sm text-muted">${t.roles.map((x, i) => `${esc(x)}: <b class="text-ink">${ids[t.members[i]] ? nameBtn(ids[t.members[i]], t.members[i]) : esc(t.members[i])}</b>`).join(" · ")}</div></li>`).join("")}</ol>`;
  $("#brief").textContent = r.brief || "";
}

// ================================================================ 4) executive report
function renderReport() {
  const r = S; if (!r || r.status !== "built") return;
  const c = r.card || {}, ar = T("arrow"), collab = collabIds(r);
  const used = Math.min(100, Math.round((r.total_cost / r.budget) * 100));
  const today = new Date().toLocaleDateString(LANG === "ar" ? "ar-SA" : "en-GB", { year: "numeric", month: "long", day: "numeric" });
  const dates = r.timeline.flatMap((t) => [new Date(t.start), new Date(t.end)]);
  const t0 = Math.min(...dates), span = Math.max(1, Math.max(...dates) - t0);
  const badge = (m) => [m.pinned && `<span class="pill bg-accent text-white">${T("card.pinned")}</span>`,
    m.external && `<span class="pill bg-slate-soft text-slate">${T("card.external")}</span>`,
    m.practitioner.is_rising_talent && `<span class="pill bg-accent-soft text-accent">${T("card.rising")}</span>`,
    collab.has(m.practitioner.id) && `<span class="pill bg-slate-soft text-ink">${T("card.collab")}</span>`,
    m.practitioner.verified_license && `<span class="pill bg-ok-soft text-ok">${T("card.licensed")}</span>`].filter(Boolean).join(" ");
  $("#reportBody").innerHTML = `
    <header class="flex flex-wrap items-center justify-between gap-6 pb-6 border-b-2 border-ink">
      <div class="flex items-center gap-4">
        <img src="/static/assets/cdf-logo.svg" width="153" height="26" alt="CDF">
        <span class="w-px h-9 bg-line2"></span>
        <div><div class="text-xl font-bold leading-6">${LANG === "ar" ? "وصل" : "Wasl"} <span class="text-muted font-medium text-sm">${LANG === "ar" ? "Wasl" : "وصل"}</span></div><div class="text-xs text-muted">${T("rp.service")}</div></div>
      </div>
      <div class="text-xs text-muted leading-6 text-end"><div>${T("rp.generated")}: <b class="text-ink">${today}</b></div><div>${T("rp.ref")}: <b class="text-ink font-mono" dir="ltr">WSL-${esc(r.session_id).toUpperCase()}</b></div></div>
    </header>

    <section class="rp-sec py-7">
      <div class="step tracking-wider">${T("rp.kicker")}</div>
      <h1 id="rpTitle" class="display-sm-bold mt-1">${T("rp.title")}</h1>
      <p class="text-md-regular text-sub mt-3 leading-7" dir="rtl">${esc(r.idea || "")}</p>
      ${c.style?.value || r.style_notes ? `<p class="text-sm text-muted mt-1">${T("rp.style")}: <b class="text-ink">${esc(c.style?.value || r.style_notes)}</b></p>` : ""}
    </section>

    <section class="rp-sec pb-7">
      <h3>${T("rp.card")}</h3>
      <div class="grid grid-cols-2 md:grid-cols-3 border-t border-s border-line">${Object.entries(T("FIELDS")).map(([k, label]) => { const f = c[k] || { status: "missing" };
        return `<div class="border-b border-e border-line p-3"><div class="text-xs text-muted flex items-center justify-between gap-2">${label}<span class="pill ${PILL_CLS[f.status]}">${T("PILL")[f.status]}</span></div><div class="font-semibold mt-1">${esc(fmtField(k, f.value))}</div></div>`; }).join("")}</div>
    </section>

    <section class="rp-sec pb-7">
      <h3>${T("rp.budget")}</h3>
      <div class="grid sm:grid-cols-3 gap-3">
        <div class="kpi"><div class="step">${T("rp.total")}</div><div class="v">${sar(r.budget)}</div></div>
        <div class="kpi" style="border-top:3px solid #0D121C"><div class="step">${T("rp.teamCost")}</div><div class="v">${sar(r.total_cost)}</div><div class="text-xs text-muted">${num(used)}% ${T("rp.share")}</div></div>
        <div class="kpi" style="border-top:3px solid #1B8354"><div class="step">${T("rp.left")}</div><div class="v text-ok">${sar(r.budget - r.total_cost)}</div><div class="text-xs text-muted">${num(100 - used)}% ${T("rp.share")}</div></div>
      </div>
      <div class="flex h-3 mt-4 bg-ok-soft"><i class="block h-full bg-brand" style="width:${used}%"></i></div>
      <div class="mt-5 text-xs text-muted mb-2">${T("rp.perRole")}</div>
      <div class="space-y-2">${r.team.map((m) => `
        <div class="grid grid-cols-[minmax(0,15rem)_1fr_auto] items-center gap-3 text-sm"><span class="min-w-0">${esc(m.role)} <span class="pct-tag">(${share(m.estimated_cost / r.budget)})</span></span>
          <div class="h-2 bg-canvas"><i class="block h-full ${m.pinned ? "bg-accent" : "bg-brand"}" style="width:${Math.round((m.estimated_cost / r.budget) * 100)}%"></i></div>
          <b class="whitespace-nowrap">${sar(m.estimated_cost)}</b></div>`).join("")}</div>
    </section>

    <section class="pb-7">
      <h3>${T("rp.team")}</h3>
      <div class="overflow-x-auto"><table>
        <thead><tr><th>${T("rp.role")}</th><th>${T("rp.member")}</th><th>${T("rp.cost")}</th><th>${T("rp.fit")}</th><th>${T("rp.backup")}</th><th class="min-w-[16rem]">${T("rp.why")}</th></tr></thead>
        <tbody>${r.team.map((m) => `<tr>
          <td><b>${esc(m.role)}</b> <span class="pct-tag">(${share(m.estimated_cost / r.budget)})</span><div class="text-xs text-muted">${esc(tm("PHASES", m.phase))}</div></td>
          <td><b>${esc(m.practitioner.name)}</b><div class="text-xs text-muted">${esc(m.practitioner.city || "")}${m.practitioner.contact?.company && m.practitioner.type !== "company" ? " · " + esc(m.practitioner.contact.company.name) : ""}</div><div class="flex flex-wrap gap-1 mt-1">${badge(m)}</div></td>
          <td class="whitespace-nowrap font-semibold">${sar(m.estimated_cost)}${m.out_of_scope ? `<div class="text-xs text-warn font-normal">${T("card.oos")} (+${num(m.out_of_scope.surcharge)})</div>` : ""}</td>
          <td>${m.external ? "—" : pct(m.score) + "%"}</td>
          <td>${m.backup ? `${esc(m.backup.name)}<div class="text-xs text-muted whitespace-nowrap">${sar(m.backup.estimated_cost)}</div>` : T("none")}</td>
          <td class="leading-6 text-sub" dir="rtl">${esc(m.explanation)}</td></tr>`).join("")}</tbody>
      </table></div>
    </section>

    <section class="rp-sec pb-7">
      <h3>${T("rp.timeline")}</h3>
      <div class="space-y-3">${r.timeline.map((t) => { const a = (new Date(t.start) - t0) / span * 100, w = Math.max(2, (new Date(t.end) - new Date(t.start)) / span * 100);
        return `<div class="grid md:grid-cols-[12rem_1fr] gap-x-4 gap-y-1 items-center">
          <div><b class="text-sm">${esc(tm("PHASES", t.phase) || t.phase_ar)}</b><div class="text-xs text-muted" dir="ltr">${esc(t.start)} ${ar} ${esc(t.end)}</div></div>
          <div><div class="gantt"><i style="inset-inline-start:${a}%;width:${w}%"></i></div>
            <div class="text-xs text-muted mt-1">${t.roles.map((x, i) => `${esc(x)}: <b class="text-ink">${esc(t.members[i])}</b>`).join(" · ")}</div></div></div>`; }).join("")}</div>
    </section>

    <section class="rp-sec pb-7">
      <h3>${T("rp.deadlines")}</h3>
      ${(r.deadlines || []).length ? `<ul class="space-y-2 text-sm">${r.deadlines.map(dlItem).join("")}</ul>` : `<p class="text-sm text-muted">${T("rp.noDeadlines")}</p>`}
    </section>

    <section class="rp-sec pb-7">
      <h3>${T("rp.permits")}</h3>
      ${(r.permits || []).length ? `<ol class="grid sm:grid-cols-2 gap-2" dir="rtl">${r.permits.map((p, i) => `<li class="flex items-start gap-3 border border-line p-3 text-sm"><span class="w-6 h-6 bg-brand text-white text-xs font-bold flex items-center justify-center shrink-0">${num(i + 1)}</span>${esc(p)}</li>`).join("")}</ol>`
        : `<p class="text-sm text-muted">${T("rp.noPermits")}</p>`}
    </section>

    <section class="pb-7">
      <h3>${T("rp.brief")}</h3>
      <pre class="whitespace-pre-wrap font-sans text-sm leading-7 bg-canvas border border-line p-5" dir="rtl">${esc(r.brief || "")}</pre>
    </section>

    <footer class="rp-sec pt-5 border-t-2 border-ink text-xs text-muted space-y-1">
      <p class="${r.check?.ok ? "text-ok" : "text-danger"} font-medium">${r.check?.ok ? T("rp.checkOk") : `${T("rp.checkWarn")} ${esc((r.check?.issues || []).join("; "))}`}</p>
      <p>${T("rp.foot")}</p>
    </footer>`;
}

// ================================================================ 5) portfolio modal + offline poster art
function hash(s) { let h = 2166136261; for (const ch of String(s)) { h ^= ch.codePointAt(0); h = Math.imul(h, 16777619); } return h >>> 0; }
function rng(seed) { return () => { seed = (seed + 0x6D2B79F5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
function poster(sector, key, year) {
  const R = rng(hash(key)), id = "p" + hash(key).toString(36), f = (x) => x.toFixed(1);
  const yr = (y = 66) => `<text x="376" y="${y}" text-anchor="end" direction="ltr" style="direction:ltr" font-family="IBM Plex Sans Arabic, sans-serif" font-size="56" font-weight="700" fill="none" stroke-width="1.2"`;
  const alt = hash(key) % 2 === 1;  // second motif per sector for variety
  if (sector === "film" && alt) {  // contact sheet: three frames of a horizon with a sun
    const sunX = 0.2 + R() * 0.6, hz = 0.55 + R() * 0.15;
    const frame = (x, i) => { const w = 112, h = 150, y = 75, s = sunX + (i - 1) * 0.12;
      return `<g><rect x="${x}" y="${y}" width="${w}" height="${h}" fill="#1F2A37"/>
        <circle cx="${f(x + w * s)}" cy="${f(y + h * (hz - 0.18))}" r="${f(12 + i * 3)}" fill="#C8A27A" fill-opacity="${f(0.55 + i * 0.2)}"/>
        <path d="M${x} ${f(y + h * hz)} Q ${f(x + w * .5)} ${f(y + h * (hz - .1 + R() * .2))} ${x + w} ${f(y + h * hz)} V${y + h} H${x}Z" fill="#8C6239" fill-opacity=".75"/>
        <rect x="${x}" y="${y}" width="${w}" height="${h}" fill="none" stroke="#F3F4F6" stroke-opacity=".6"/>
        <text x="${x + 6}" y="${y + h + 16}" direction="ltr" style="direction:ltr" font-size="10" fill="#C8A27A" font-family="monospace">${String(i + 1).padStart(2, "0")}A</text></g>`; };
    return `<svg viewBox="0 0 400 300" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <rect width="400" height="300" fill="#0D121C"/>${[20, 144, 268].map(frame).join("")}
      <path d="M${f(40 + R() * 300)} 70 l14 0 l-14 14 z" fill="#B42318"/>
      ${yr(58)} stroke="#ffffff40">${year}</text></svg>`;
  }
  if (sector === "fashion" && alt) {  // pattern-cutting board: stacked fabric folds + tape measure
    const folds = [...Array(5)].map((_, i) => { const y = 60 + i * 42 + R() * 10, c = ["#0D121C", "#1F2A37", "#8C6239", "#C8A27A", "#E9D9C6"][i];
      return `<path d="M-10 ${f(y)} C 120 ${f(y - 30 + R() * 60)}, 260 ${f(y + 40 - R() * 60)}, 410 ${f(y)} V${f(y + 60)} H-10Z" fill="${c}"/>`; }).join("");
    const ticks = [...Array(26)].map((_, i) => `<path d="M${16 + i * 15} 22 v${i % 2 ? 6 : 11}" stroke="#0D121C"/>`).join("");
    return `<svg viewBox="0 0 400 300" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <rect width="400" height="300" fill="#F6EFE7"/>${folds}
      <rect x="0" y="14" width="400" height="22" fill="#F3E2C3"/>${ticks}
      <circle cx="${f(60 + R() * 280)}" cy="${f(110 + R() * 90)}" r="18" fill="none" stroke="#F6EFE7" stroke-width="3" stroke-dasharray="4 4"/>
      ${yr(96)} stroke="#F6EFE7cc">${year}</text></svg>`;
  }
  if (sector === "film") {
    const cx = 120 + R() * 160, cy = 150 + (R() - .5) * 30, rot = R() * 60, rad = 62 + R() * 18;
    const blades = [...Array(6)].map((_, i) => { const a = (i * 60 + rot) * Math.PI / 180, b = a + 1.05;
      return `<path d="M${f(Math.cos(a) * rad * .38)} ${f(Math.sin(a) * rad * .38)} L${f(Math.cos(b) * rad)} ${f(Math.sin(b) * rad)}" stroke="#C8A27A" stroke-width="1.6"/>`; }).join("");
    const hexa = [...Array(6)].map((_, i) => { const a = (i * 60 + rot) * Math.PI / 180; return `${f(Math.cos(a) * rad * .38)},${f(Math.sin(a) * rad * .38)}`; }).join(" ");
    const perf = (y) => [...Array(20)].map((_, i) => `<rect x="${i * 20 + 5}" y="${y}" width="10" height="9" fill="#F3F4F6" opacity=".75"/>`).join("");
    return `<svg viewBox="0 0 400 300" preserveAspectRatio="xMidYMid slice" aria-hidden="true"><defs>
      <linearGradient id="${id}b" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".22"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
      <radialGradient id="${id}g" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#8C6239" stop-opacity=".55"/><stop offset="1" stop-color="#8C6239" stop-opacity="0"/></radialGradient></defs>
      <rect width="400" height="300" fill="#0D121C"/>
      <path d="M${f(cx + 40)} -10 L${f(cx + 230)} 310 L${f(cx - 120)} 310 Z" fill="url(#${id}b)"/>
      <circle cx="${f(cx)}" cy="${f(cy)}" r="${f(rad * 1.9)}" fill="url(#${id}g)"/>
      <g transform="translate(${f(cx)} ${f(cy)})"><circle r="${f(rad)}" fill="none" stroke="#C8A27A" stroke-width="2"/><circle r="${f(rad + 9)}" fill="none" stroke="#C8A27A" stroke-opacity=".35" stroke-dasharray="2 6"/>
        ${blades}<polygon points="${hexa}" fill="#8C6239" fill-opacity=".35" stroke="#C8A27A" stroke-width="1.2"/></g>
      <rect width="400" height="26" fill="#000"/>${perf(8)}<rect y="274" width="400" height="26" fill="#000"/>${perf(282)}
      ${yr()} stroke="#ffffff59">${year}</text></svg>`;
  }
  if (sector === "fashion") {
    const x = 150 + R() * 100, w = 34 + R() * 12, hem = 90 + R() * 30, tilt = (R() - .5) * 8;
    return `<svg viewBox="0 0 400 300" preserveAspectRatio="xMidYMid slice" aria-hidden="true"><defs>
      <pattern id="${id}s" width="14" height="14" patternUnits="userSpaceOnUse"><path d="M0 0V14" stroke="#8C6239" stroke-opacity=".14"/></pattern></defs>
      <rect width="400" height="300" fill="#F6EFE7"/><rect width="400" height="300" fill="url(#${id}s)"/>
      <circle cx="${f(x + 10)}" cy="128" r="${f(96 + R() * 20)}" fill="#E9D9C6"/>
      <path d="M-10 ${f(200 + R() * 40)} C 110 ${f(120 + R() * 60)}, 250 ${f(260 - R() * 50)}, 410 ${f(150 + R() * 40)}" fill="none" stroke="#8C6239" stroke-width="1.6" stroke-dasharray="6 5"/>
      <g transform="rotate(${f(tilt)} ${f(x)} 160)">
        <circle cx="${f(x)}" cy="52" r="11" fill="#0D121C"/><rect x="${f(x - 2)}" y="62" width="4" height="10" fill="#0D121C"/>
        <polygon points="${f(x - w * .75)},74 ${f(x + w * .75)},74 ${f(x + w * .45)},140 ${f(x - w * .45)},140" fill="#0D121C"/>
        <rect x="${f(x - w * .5)}" y="136" width="${f(w)}" height="8" fill="#8C6239"/>
        <polygon points="${f(x - w * .5)},144 ${f(x + w * .5)},144 ${f(x + hem)},282 ${f(x - hem)},282" fill="#1F2A37"/>
        <polygon points="${f(x)},144 ${f(x + hem * .35)},282 ${f(x - hem * .15)},282" fill="#0D121C"/>
      </g>
      ${["#0D121C", "#8C6239", "#C8A27A"].map((c, i) => `<rect x="24" y="${96 + i * 30}" width="22" height="22" fill="${c}"/>`).join("")}
      ${yr()} stroke="#0D121C59">${year}</text></svg>`;
  }
  // heritage (default): arches, mashrabiya stars, dunes
  const n = R() > .5 ? 3 : 1, sun = 60 + R() * 280;
  const arch = (cx, hw, top) => `M${f(cx - hw)} 300 V${f(top)} A${f(hw)} ${f(hw)} 0 0 1 ${f(cx + hw)} ${f(top)} V300 Z`;
  const arches = n === 1 ? [arch(200 + (R() - .5) * 60, 78, 150)] : [arch(110, 46, 170), arch(200, 52, 150), arch(290, 46, 170)];
  return `<svg viewBox="0 0 400 300" preserveAspectRatio="xMidYMid slice" aria-hidden="true"><defs>
    <pattern id="${id}m" width="28" height="28" patternUnits="userSpaceOnUse"><g fill="none" stroke="#C8A27A" stroke-width="1" stroke-opacity=".7">
      <rect x="7" y="7" width="14" height="14"/><rect x="7" y="7" width="14" height="14" transform="rotate(45 14 14)"/></g></pattern></defs>
    <rect width="400" height="300" fill="#EADFCD"/>
    <circle cx="${f(sun)}" cy="${f(70 + R() * 30)}" r="${f(26 + R() * 12)}" fill="#8C6239" fill-opacity=".85"/>
    <path d="M0 ${f(230 + R() * 20)} Q 120 ${f(190 + R() * 30)} 230 ${f(225 + R() * 15)} T 400 ${f(210 + R() * 20)} V300 H0Z" fill="#D9C6A8"/>
    ${arches.map((d) => `<path d="${d}" fill="#1F2A37"/><path d="${d}" fill="url(#${id}m)"/>`).join("")}
    <path d="M0 ${f(262 + R() * 10)} Q 140 ${f(240 + R() * 20)} 260 ${f(265)} T 400 ${f(255 + R() * 10)} V300 H0Z" fill="#C9B08A"/>
    ${yr()} stroke="#1F2A3766">${year}</text></svg>`;
}
// photo failed to load (missing file, offline CDN, ...): fall back to the generated poster and disable the zoom
function pfImgFail(img) {
  const b = img.closest(".pf-photo"); if (!b) return;
  img.outerHTML = poster(b.dataset.sector, b.dataset.key, b.dataset.year);
  b.disabled = true; b.querySelector(".pf-zoom")?.remove();  // keep .pf-photo so the 16:9 frame matches its neighbours
}
function openZoom(src, cap) {
  const img = $("#pfZoomImg");
  img.src = src; img.alt = cap; $("#pfZoomCap").textContent = cap;
  openModal("#pfZoom");
}
const initials = (name) => String(name || "?").trim().split(/\s+/).slice(0, 2).map((w) => w[0]).join(" ");
async function openPortfolio(id) {
  await loadPrs();
  const tm_ = S?.team?.find((m) => m.practitioner.id === id || m.backup?.id === id);
  const ext = tm_ && tm_.practitioner.id === id && tm_.external;
  const p = PRS[id] || (ext ? { id, name: tm_.practitioner.name, type: "individual", specialty: (tm_.practitioner.specialties || []).join("، "),
    sectors: [], city: tm_.practitioner.city, past_works: [], collaborators: [], typical_fee_min: tm_.estimated_cost, typical_fee_max: tm_.estimated_cost } : null);
  if (!p) return;
  PF_OPEN = id;
  const sector = p.sectors?.[0] || S?.card?.sector?.value || "heritage";
  const roles = (S?.team || []).filter((m) => m.practitioner.id === id).map((m) => m.role);
  const fee = p.typical_fee_min ? (p.typical_fee_min === p.typical_fee_max ? sar(p.typical_fee_min) : `${sar(p.typical_fee_min)} – ${num(p.typical_fee_max)}`) : T("pf.unknownFee");
  const nm = (cid) => PRS[cid]?.name || cid;
  $("#pfBody").innerHTML = `
    <div class="p-6 md:p-8 border-b border-line flex flex-wrap gap-5 items-start pe-16">
      ${avatar(p, "lg")}
      <div class="flex-1 min-w-[220px] space-y-2">
        <div class="step tracking-wider">${T("pf.kicker")} · ${tm("TYPE", p.type)}</div>
        <h2 id="pfName" class="display-xs-bold">${esc(p.name)}</h2>
        <div class="text-sm text-sub" dir="rtl">${esc(p.specialty)}${p.city ? " · " + esc(p.city) : ""}</div>
        <div class="flex flex-wrap gap-1">
          ${p.verified_license ? `<span class="pill bg-ok-soft text-ok">${T("pf.verified")}</span>` : ""}
          ${p.is_rising_talent ? `<span class="pill bg-accent-soft text-accent">${T("pf.rising")}</span>` : ""}
          ${p.remote_ok ? `<span class="pill bg-slate-soft text-slate">${T("pf.remote")}</span>` : ""}
          ${(p.sectors || []).map((s) => `<span class="pill bg-slate-soft text-slate">${esc(tm("SECTORS", s))}</span>`).join("")}
          ${ext ? `<span class="pill bg-slate-soft text-slate">${T("card.external")}</span>` : ""}
          ${roles.length ? `<span class="pill bg-brand text-white">${T("pf.inTeam")}${roles.map(esc).join("، ")}</span>` : ""}
        </div>
      </div>
      <div class="space-y-2 min-w-[200px]"><div class="kpi"><div class="step">${T("pf.fee")}</div><div class="v !text-lg">${fee}</div></div>
        ${ext ? "" : `<button type="button" class="ct-act w-full justify-center" data-contact="${esc(id)}">${T("ct.open")}</button>`}</div>
    </div>
    ${(p.collaborators || []).length ? `<div class="px-6 md:px-8 py-4 border-b border-line bg-canvas text-sm flex flex-wrap items-center gap-x-3 gap-y-1">
      <span class="text-muted">${T("pf.collab")}:</span>${p.collaborators.map((c) => `<b>${nameBtn(c.id, c.name)}</b>`).join('<span class="text-line2">/</span>')}</div>` : ""}
    <div class="p-6 md:p-8">
      <h3 class="font-bold mb-4 flex items-center gap-2"><span class="w-2.5 h-2.5 bg-ink"></span>${T("pf.works")} <span class="text-muted font-normal text-sm">(${num((p.past_works || []).length)})</span></h3>
      ${(p.past_works || []).length ? `<div class="grid sm:grid-cols-2 gap-4">${p.past_works.map((w) => `
        <article class="pf-work">
          ${w.image_url ? `<button type="button" class="pf-art pf-photo group" data-zoom="${esc(w.image_url)}" data-zoomcap="${esc(`${w.title} · ${w.year} · ${w.role}`)}"
              data-sector="${esc(sector)}" data-key="${esc(p.id + w.title)}" data-year="${esc(w.year)}" aria-label="${esc(w.title)} — ${T("pf.zoom")}">
              <img src="${esc(w.image_url)}" alt="${esc(w.title)} — ${esc(w.description)}" loading="lazy" decoding="async"
                class="aspect-video w-full object-cover rounded-xl transition-transform duration-500 ease-out group-hover:scale-105" onerror="pfImgFail(this)">
              <span class="pf-zoom" aria-hidden="true">⤢</span>`
            : `<div class="pf-art">${poster(sector, p.id + w.title, w.year)}`}
            <div class="cap" dir="rtl"><div class="text-xs opacity-80">${esc(w.year)} · ${esc(w.role)}</div><div class="font-bold text-lg leading-7">${esc(w.title)}</div></div>
          ${w.image_url ? "</button>" : "</div>"}
          <div class="p-4 space-y-2 flex-1">
            <p class="text-sm text-sub leading-6" dir="rtl">${esc(w.description)}</p>
            ${(w.collaborator_ids || []).length ? `<div class="text-xs text-muted">${T("pf.with")}: ${w.collaborator_ids.map((c) => (PRS[c] ? nameBtn(c, nm(c)) : esc(c))).join("، ")}</div>` : ""}
          </div></article>`).join("")}</div>`
        : `<div class="border border-dashed border-line2 p-8 text-center text-sm text-muted">${ext ? T("pf.extNote") : T("pf.noWorks")}</div>`}
    </div>`;
  openModal("#pfModal");
  $("#pfModal").scrollTop = 0;
  $("#ctModal").hidden = true; CT_OPEN = null;  // swap, don't stack
}

// ---------------------------------------------------------------- contact modal (practitioner + company)
const telHref = (n) => "tel:" + String(n).replace(/[^\d+]/g, "");
const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? u : null);
function ctRow(label, value, href, action, ext) {
  if (!value) return "";
  return `<div class="ct-row"><span class="k">${label}</span><span class="v">${esc(value)}</span>
    ${href ? `<a class="ct-act" href="${esc(href)}"${ext ? ' target="_blank" rel="noopener noreferrer"' : ""}>${action}</a>` : ""}</div>`;
}
async function openContact(id, focus = "person") {
  await loadPrs();
  const tmem = S?.team?.find((m) => m.practitioner.id === id);
  const p = PRS[id] || tmem?.practitioner;
  if (!p) return;
  CT_OPEN = [id, focus];
  const c = contactOf(id), co = c?.company, isCo = p.type === "company";
  const roles = (S?.team || []).filter((m) => m.practitioner.id === id).map((m) => m.role);
  const person = isCo ? `<p class="text-sm text-muted">${T("ct.self")}</p>`
    : c && (c.phone || c.email) ? ctRow(T("ct.phone"), c.phone, c.phone && telHref(c.phone), T("ct.call")) + ctRow(T("ct.email"), c.email, c.email && "mailto:" + c.email, T("ct.mail"))
    : `<p class="text-sm text-muted">${T("ct.none")}</p>`;
  const company = co ? `<div class="font-bold mb-1">${esc(co.name)}</div>`
      + ctRow(T("ct.tel"), co.phone, co.phone && telHref(co.phone), T("ct.call"))
      + ctRow(T("ct.email"), co.email, co.email && "mailto:" + co.email, T("ct.mail"))
      + ctRow(T("ct.web"), co.website, safeUrl(co.website), T("ct.visit"), true)
    : `<p class="text-sm text-muted">${c ? T("ct.noCompany") : T("ct.none")}</p>`;
  const sec = (key, title, body) => `<section class="ct-sec ${focus === key || (isCo && key === "company") ? "focus" : ""}" id="ct-${key}">
    <div class="step mb-2">${title}</div>${body}</section>`;
  $("#ctBody").innerHTML = `
    <div class="p-6 border-b border-line flex gap-4 items-center pe-16">
      ${avatar(p)}
      <div class="min-w-0"><div class="step tracking-wider">${T("ct.kicker")} · ${tm("TYPE", p.type)}</div>
        <h2 id="ctName" class="text-xl font-bold leading-7">${esc(p.name)}</h2>
        <div class="text-xs text-muted">${esc(p.specialty || (p.specialties || []).join("، "))}${p.city ? " · " + esc(p.city) : ""}</div>
        ${roles.length ? `<span class="pill bg-brand text-white mt-1">${T("pf.inTeam")}${roles.map(esc).join("، ")}</span>` : ""}</div>
    </div>
    <div class="p-6 space-y-4">
      ${isCo ? "" : sec("person", T("ct.person"), person)}
      ${sec("company", T("ct.company"), company)}
      <div class="flex items-center justify-between gap-3 pt-1">
        <span class="text-[11px] text-muted">${T("ct.demo")}</span>
        ${PRS[id] ? `<button type="button" class="btn btn-ghost !min-h-[34px] text-sm" data-pf="${esc(id)}">${T("ct.portfolio")}</button>` : ""}
      </div>
    </div>`;
  openModal("#ctModal");
  $("#pfModal").hidden = true; PF_OPEN = null;  // swap, don't stack
  $("#ct-" + focus)?.scrollIntoView({ block: "nearest" });
}

// ---------------------------------------------------------------- modal plumbing (X / Escape / backdrop)
let lastFocus = null;
function openModal(sel) {
  const m = $(sel); if ($$(".modal").every((x) => x.hidden)) lastFocus = document.activeElement;
  m.hidden = false; document.body.classList.add("modal-open");
  document.body.classList.toggle("report-open", !$("#reportModal").hidden);
  m.querySelector("[data-close]")?.focus({ preventScroll: true });
}
function closeModal(m) {
  m.hidden = true; if (m.id === "pfModal") PF_OPEN = null; if (m.id === "ctModal") CT_OPEN = null;
  if ($$(".modal").every((x) => x.hidden)) { document.body.classList.remove("modal-open"); lastFocus?.focus?.({ preventScroll: true }); }
  document.body.classList.toggle("report-open", !$("#reportModal").hidden);
}

// ================================================================ actions
async function buildTeam() {
  const drop = $$(".drop:checked").map((x) => x.value);
  const r = await api(`/api/sessions/${S.session_id}/build-team`, { drop_need_ids: drop, pins: PINS.filter((p) => !drop.includes(p.need_id)) }, T("ld.build"));
  if (r) { render(r); $("#teamSec").scrollIntoView({ behavior: "smooth" }); }
}
async function whatIf(opts = {}) {
  const budget = parseInt($("#wiBudget").value, 10);
  const body = { deadline_shift_days: parseInt($("#wiShift").value, 10) || 0, allow_remote: $("#wiRemote").checked };
  if (budget > 0) body.budget = budget;
  if (opts.pins) body.pins = PINS;
  const r = await api(`/api/sessions/${S.session_id}/what-if`, body, T("ld.wi"));
  if (r) { render(r); $("#latency").textContent = `⚡ ${r._ms} ms`; }
  else if (opts.pins && S) { PINS = (S.pins || []).map((p) => ({ ...p })); renderPinHosts(); renderNeeds(S); }  // server refused: revert
}
function reset() {
  S = null; PINS = []; ADV_SEEN = 0; $("#chat").innerHTML = ""; chips([]); $("#input").value = "";
  ["#needsSec", "#teamSec", "#error"].forEach((s) => $(s).classList.add("hidden"));
  $("#pinBoxWIWrap").hidden = true; $$("[data-pinhost]").forEach((h) => { h.innerHTML = ""; delete h.dataset.sel; });
  $("#latency").textContent = ""; $("#statusPill").textContent = tm("STATUS", "clarifying");
  renderCard({}); renderDeadlines([]);
  bubble("bot", esc(T("welcome")));
  chips(T("starters"));
}

document.addEventListener("click", async (e) => {
  const modal = e.target.closest(".modal");
  if (modal && (e.target === modal || e.target.closest("[data-close]"))) return closeModal(modal);
  if (!e.target.closest(".pin-q, .pin-results")) $$(".pin-results").forEach((b) => (b.hidden = true));
  const t = e.target.closest("button"); if (!t || t.disabled) return;
  const host = t.closest("[data-pinhost]");
  if (t.dataset.q) {
    if (!S) { $("#input").value = t.dataset.q + " "; $("#input").focus(); } else send(t.dataset.q);
  } else if (t.dataset.demo) {
    reset(); const idea = DEMOS[t.dataset.demo];
    $("#input").value = idea; $("#input").focus();
  } else if (t.dataset.conc) {
    const r = await api(`/api/sessions/${S.session_id}/apply-concession`, { concession_id: t.dataset.conc }, T("ld.conc"));
    if (r) render(r);
  } else if (t.dataset.reject) {
    const r = await api(`/api/sessions/${S.session_id}/reject/${t.dataset.reject}`, {}, T("ld.reject"));
    if (r) render(r);
  } else if (t.dataset.contact) {
    openContact(t.dataset.contact, t.dataset.focus || "person");
  } else if (t.dataset.pf) {
    openPortfolio(t.dataset.pf);
  } else if (t.dataset.zoom) {
    openZoom(t.dataset.zoom, t.dataset.zoomcap || "");
  } else if (t.dataset.tab) {
    $$("[data-tab]").forEach((b) => b.classList.toggle("tab-on", b === t));
    $("#tab-timeline").classList.toggle("hidden", t.dataset.tab !== "timeline");
    $("#tab-brief").classList.toggle("hidden", t.dataset.tab !== "brief");
  } else if (host && t.dataset.pinmode) {
    host.dataset.mode = t.dataset.pinmode; delete host.dataset.sel; renderPinHost(host);
  } else if (host && t.dataset.pinpick) {
    host.dataset.sel = t.dataset.pinpick; host.querySelector(".pin-q").value = PRS[t.dataset.pinpick]?.name || "";
    host.querySelector(".pin-results").hidden = true;
  } else if (host && t.hasAttribute("data-pinadd")) {
    addPin(host);
  } else if (host && t.dataset.unpin) {
    PINS = PINS.filter((p) => p.need_id !== t.dataset.unpin); pinsChanged();
  }
});
document.addEventListener("input", (e) => {
  const host = e.target.closest("[data-pinhost]");
  if (host && e.target.matches(".pin-q")) { delete host.dataset.sel; renderPinResults(host); }
});
document.addEventListener("focusin", async (e) => {
  if (e.target.matches?.(".pin-q")) { await loadPrs(); renderPinResults(e.target.closest("[data-pinhost]")); }
});
document.addEventListener("change", (e) => {
  if (e.target.matches(".drop")) e.target.closest(".leaf")?.classList.toggle("is-dropped", e.target.checked);
  if (e.target.matches(".card-date")) editCard(e.target.dataset.card, e.target.value);
  if (e.target.matches(".pin-role")) { const h = e.target.closest("[data-pinhost]"); if (h?.querySelector(".pin-q") && !h.querySelector(".pin-results").hidden) renderPinResults(h); }
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") { const open = $$(".modal").filter((m) => !m.hidden).pop(); if (open) { e.preventDefault(); closeModal(open); } }
  if (e.key === "Enter" && e.target.matches?.(".pin-q, .pin-name, .pin-cost")) {
    e.preventDefault(); const h = e.target.closest("[data-pinhost]");
    if (e.target.matches(".pin-q") && !h.dataset.sel) { const first = h.querySelector("[data-pinpick]"); if (first) first.click(); return; }
    addPin(h);
  }
});
$("#chatForm").addEventListener("submit", (e) => { e.preventDefault(); send($("#input").value); });
$("#input").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send($("#input").value); } });
$("#reset").onclick = reset;
$("#build").onclick = buildTeam;
$("#wiApply").onclick = () => whatIf();
$("#wiRange").oninput = (e) => ($("#wiBudget").value = e.target.value);
$("#wiRange").onchange = () => whatIf();
$("#wiRemote").onchange = () => whatIf();
$("#wiPinToggle").onclick = async () => {
  const w = $("#pinBoxWIWrap"); w.hidden = !w.hidden; $("#wiPinToggle").setAttribute("aria-expanded", !w.hidden);
  if (!w.hidden) { await loadPrs(); renderPinHost($("#pinBoxWI")); w.scrollIntoView({ behavior: "smooth", block: "nearest" }); }
};
$("#openReport").onclick = () => { renderReport(); openModal("#reportModal"); $("#reportModal").scrollTop = 0; };
$("#printReport").onclick = () => { document.body.classList.add("report-open"); window.print(); };
$("#langToggle").onclick = (e) => { e.preventDefault(); setLang(LANG === "ar" ? "en" : "ar"); };
$("#copy").onclick = async () => {
  try { await navigator.clipboard.writeText($("#brief").textContent); $("#copy").textContent = T("copied"); }
  catch { showError(T("copyFail")); }
  setTimeout(() => ($("#copy").textContent = T("copy")), 1500);
};

// voice input (ar-SA); hidden when unsupported
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
if (SR) {
  const rec = new SR(); rec.lang = "ar-SA"; rec.interimResults = false;
  const mic = $("#mic"); mic.classList.remove("hidden");
  let on = false;
  mic.onclick = () => { if (on) return rec.stop(); try { rec.lang = LANG === "en" ? "en-US" : "ar-SA"; rec.start(); on = true; mic.textContent = "⏺️"; } catch {} };
  rec.onresult = (e) => { $("#input").value = ($("#input").value + " " + e.results[0][0].transcript).trim(); };
  rec.onend = () => { on = false; mic.textContent = "🎙️"; };
  rec.onerror = (e) => { if (e.error !== "aborted") showError(T("micFail")); };
}

// health badge
function renderHealth() {
  const el = $("#health");
  if (HEALTH === undefined) { el.textContent = T("health.checking"); return; }
  if (!HEALTH) { el.className = "pill bg-white border border-danger text-danger me-2"; el.textContent = T("health.down"); return; }
  el.className = "pill me-2 " + (HEALTH.models_loaded ? "bg-ok-soft text-ok" : "bg-accent-soft text-accent");
  el.textContent = (HEALTH.models_loaded ? T("health.ok") : T("health.cold")) + (HEALTH.llm_configured ? "" : T("health.nollm"));
}
(async function health() {
  try { HEALTH = await (await fetch("/api/health")).json(); } catch { HEALTH = null; }
  renderHealth();
})();

applyStatic();
reset();
loadPrs();
