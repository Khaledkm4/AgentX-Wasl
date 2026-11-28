"""One-off: download a real, freely-licensed photo for every seeded portfolio project from Wikimedia Commons
into src/wasl/static/portfolio/ (so the demo works offline) and record attribution in CREDITS.json.

Run: .cache/venv/Scripts/python scripts/fetch_portfolio_images.py [--force] [slug ...]
Pin a specific Commons file for a slug with PINNED below when search picks something off-topic."""
import json
import re
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from seed_db import IMAGES  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "src" / "wasl" / "static" / "portfolio"
API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "WaslDemo/1.0 (offline demo portfolio images; https://commons.wikimedia.org)"}
WIDTH = 1600

# slug -> search queries, most specific first
QUERIES = {
    "palm-frond-weaving": ["palm frond weaving Saudi", "khoos palm leaf weaving", "palm leaf weaving hands"],
    "mud-brick-village": ["Ushaiqer heritage village", "mud brick houses Saudi Arabia", "Najdi mud architecture"],
    "loom-weaving": ["traditional loom weaving woman", "hand loom weaving", "weaving loom"],
    "qaisariya-souq": ["Al Qaisariya Souq Hofuf", "Qaisariya market Al-Ahsa", "Hofuf souq"],
    "pearling-dhow": ["pearl diving dhow", "dhow boat Persian Gulf", "traditional dhow"],
    "folk-festival": ["Ardah Saudi dance", "Saudi folk dance festival", "Janadriyah festival"],
    "jeddah-al-balad": ["Al-Balad Jeddah", "Historic Jeddah", "Jeddah old town"],
    "coppersmith": ["coppersmith souq", "copper craftsman workshop", "coppersmith"],
    "al-ahsa-oasis": ["Al-Ahsa Oasis", "Al Ahsa palm grove", "date palm oasis"],
    "desert-dunes-herder": ["camel herder desert Saudi", "Rub al Khali dunes", "Arabian desert camels"],
    "saudi-crafts": ["Saudi handicrafts", "traditional crafts souq Saudi", "Arabic handicraft artisan"],
    "film-set-sound": ["boom microphone film set", "film shooting crew night", "film set"],
    "red-sea-boats": ["Jeddah fishing boats", "Red Sea fishing boat", "fishing boats harbour Red Sea"],
    "handmade-paper": ["handmade paper making", "papermaking mould deckle", "hand made paper"],
    "palm-basket-craft": ["palm leaf basket weaving", "palm baskets craft", "basket weaving craftsman"],
    "souq-field-recording": ["field recording microphone", "audio field recorder", "sound recordist"],
    "oral-history-recording": ["oral history interview recording", "interview microphone recording", "podcast microphone"],
    "sadu-weaving": ["Al Sadu weaving", "Sadu textile", "Bedouin weaving"],
    "runway-najd": ["fashion show runway model", "runway fashion show", "catwalk fashion show"],
    "runway-summer": ["fashion week catwalk summer collection", "runway models collection", "fashion runway"],
    "jeddah-roshan": ["roshan Jeddah", "rawashin Jeddah wooden windows", "mashrabiya Jeddah"],
    "fashion-week": ["fashion week backstage", "fashion week runway finale", "fashion week"],
    "abaya-embroidery": ["abaya embroidery", "hand embroidery gold thread", "embroidery hand"],
    "diriyah-night": ["At-Turaif Diriyah night", "Diriyah", "Turaif district"],
    "graduation-show": ["fashion design student show", "fashion design graduation show", "fashion students runway"],
    "theatre-lighting": ["stage lighting theatre", "theatre stage lights", "stage lights concert"],
    "corniche-night-lights": ["Khobar corniche night", "Dammam corniche night", "waterfront night lights"],
    "runway-lighting": ["fashion show stage lighting", "runway lights fashion show", "fashion show lights"],
    "asir-dress": ["Asir traditional dress", "Rijal Almaa", "Al-Qatt Al-Asiri"],
    "bisht": ["bisht cloak", "bisht", "Arab cloak bisht"],
    "textile-exhibition": ["textile exhibition museum", "textile museum display", "fabric exhibition"],
    "incense-route-exhibit": ["frankincense incense", "frankincense resin", "incense burner frankincense"],
    "rock-inscriptions": ["Jabal Ikmah inscriptions", "rock inscriptions Saudi Arabia", "petroglyphs Saudi"],
    "saudi-pavilion": ["Saudi pavilion Expo", "Saudi Arabia pavilion", "Expo pavilion"],
    "nasseef-house": ["Nasseef House Jeddah", "Beit Nassif", "Nasseef House"],
    "alula-sandstone": ["AlUla sandstone", "Elephant Rock AlUla", "AlUla rock formations"],
    "dadan": ["Dadan AlUla", "Dedan Al-Ula", "Lion tombs Dadan"],
    "artifact-catalogue": ["archaeological artifacts museum", "archaeology finds documentation", "museum artifacts"],
    "alula-oasis": ["AlUla oasis", "Al-Ula old town", "AlUla old town"],
    "exhibition-build": ["exhibition installation wooden", "museum exhibition design", "exhibition hall"],
    "heritage-market-stalls": ["Souq Al Zal Riyadh", "traditional souq stalls Saudi", "souq stalls"],
    "national-museum": ["National Museum Riyadh", "Saudi National Museum", "Riyadh museum"],
    "ancient-script": ["Dadanitic inscription", "Lihyanite inscription", "ancient Arabian inscription"],
    "festival-identity": ["festival posters wall", "graphic design posters", "poster design"],
    "museum-vitrine": ["museum display case artifacts", "museum vitrine", "museum showcase"],
    "camel-caravan": ["camel caravan desert", "camel caravan", "camels desert Saudi"],
    "pottery-wheel": ["potter wheel hands clay", "pottery wheel", "potter"],
    "film-festival": ["Red Sea International Film Festival", "film festival red carpet", "film festival"],
}
# slug -> exact Commons file, hand-picked after reviewing what keyword search returned
PINNED: dict[str, str] = {
    "abaya-embroidery": "File:A hand Palestinian embroidery.jpg",
    "al-ahsa-oasis": "File:Al-Qarah Mountain, Saudi Arabia.jpg",
    "alula-sandstone": "File:Elephant rock, Al-'Ula (2024).jpg",
    "coppersmith": "File:Artisan du souk En Nhas ou cuivre.jpg",
    "exhibition-build": "File:Paris - Carpenter workshop - 4980.jpg",
    "film-set-sound": "File:Tournage de film.JPG",
    "graduation-show": "File:Dressmaker in the old medina off Sousse, Tunisia.jpg",
    "handmade-paper": "File:Modern papermaking moulds and deckles.jpg",
    "jeddah-al-balad": "File:Historic Jeddah 16.jpg",
    "jeddah-roshan": "File:Historic Jeddah 9.jpg",
    "national-museum": "File:National Museum of Saudi Arabia 03 b.jpg",
    "palm-frond-weaving": "File:Anciana tejiendo clinejas en San Juan Bautísta, Puerto e tabla.JPG",
    "pottery-wheel": "File:Pottery wheel (Unsplash).jpg",
    "runway-summer": "File:Saudi Fashion Week.jpg",
    "sadu-weaving": "File:Bedouin woman weaving.jpg",
    "souq-field-recording": "File:Sound Recordist .jpg",
    "textile-exhibition": "File:Interior view - Textile Museum, George Washington University - DSC09754.JPG",
    "theatre-lighting": "File:A catwalk for stage lighting above the auditorium of a community theatre.jpg",
}

LICENSE_OK = re.compile(r"^(CC0|CC BY|CC-BY|Public domain|PD|Attribution)", re.I)
strip = lambda s: re.sub(r"<[^>]+>", "", s or "").strip()


def candidates(c: httpx.Client, q: str | None = None, title: str | None = None) -> list[dict]:
    p = dict(action="query", format="json", prop="imageinfo", iiprop="url|size|mime|extmetadata",
             iiurlwidth=WIDTH, iiextmetadatafilter="LicenseShortName|Artist|ObjectName")
    if title:
        p["titles"] = title
    else:
        p.update(generator="search", gsrnamespace=6, gsrlimit=20,
                 gsrsearch=f"{q} filemime:image/jpeg filew:>1500")
    pages = c.get(API, params=p).json().get("query", {}).get("pages", {})
    out = []
    for pg in sorted(pages.values(), key=lambda x: x.get("index", 0)):
        ii = (pg.get("imageinfo") or [{}])[0]
        md = ii.get("extmetadata", {})
        lic = strip(md.get("LicenseShortName", {}).get("value"))
        if ii.get("mime") != "image/jpeg" or not LICENSE_OK.match(lic) or not ii.get("thumburl"):
            continue
        if not title and not (ii["width"] >= 1500 and ii["width"] >= ii["height"] * 1.15):  # landscape for 16:9
            continue
        out.append({"file": pg["title"], "thumb": ii["thumburl"], "page": ii["descriptionurl"], "license": lic,
                    "artist": strip(md.get("Artist", {}).get("value"))[:160], "w": ii["width"], "h": ii["height"]})
    return out


def is_jpeg(b: bytes) -> bool:
    return len(b) > 20_000 and b[:3] == b"\xff\xd8\xff" and b.rstrip(b"\x00")[-2:] == b"\xff\xd9"


def main():
    force = "--force" in sys.argv
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    OUT.mkdir(parents=True, exist_ok=True)
    cred_path = OUT / "CREDITS.json"
    credits = json.loads(cred_path.read_text("utf-8")) if cred_path.exists() else {}
    used = {v["file"] for k, v in credits.items() if k not in only}
    with httpx.Client(headers=UA, timeout=60, follow_redirects=True) as c:
        for slug in sorted(set(IMAGES.values())):
            dest = OUT / f"{slug}.jpg"
            if (only and slug not in only) or (not only and not force and dest.exists() and slug in credits):
                continue
            got = None
            lists = [candidates(c, title=PINNED[slug])] if slug in PINNED else (candidates(c, q) for q in QUERIES[slug])
            for cands in lists:
                for cand in cands:
                    if cand["file"] in used:
                        continue
                    b = c.get(cand["thumb"]).content
                    if is_jpeg(b):
                        got = cand
                        dest.write_bytes(b)
                        break
                    time.sleep(0.5)
                if got:
                    break
            if not got:
                print(f"!! {slug}: nothing suitable")
                continue
            used.add(got["file"])
            credits[slug] = {k: got[k] for k in ("file", "page", "license", "artist")}
            print(f"ok {slug:24s} {dest.stat().st_size // 1024:5d} KB  {got['file']}")
            time.sleep(0.3)
    cred_path.write_text(json.dumps(dict(sorted(credits.items())), ensure_ascii=False, indent=1), "utf-8")
    missing = [s for s in set(IMAGES.values()) if not (OUT / f"{s}.jpg").exists()]
    print("missing:", missing or "none")


if __name__ == "__main__":
    main()
