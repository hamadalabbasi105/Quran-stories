#!/usr/bin/env python3
"""Render the daily Quran Instagram Story slides for @al.quran.kareem105.

Usage:  python3 render.py content.json OUTPUT_DIR
Writes 1.jpg, 2.jpg, 3.jpg (and friday.jpg when content has "friday").
Exits with code 2 and prints the problem if any text has a character
the fonts cannot draw, or if text does not fit; nothing should be posted then.

content.json keys (all strings unless noted):
  date_label   e.g. "الإثنين ٢٤ نوفمبر"
  hook         curiosity question for slide 1
  ayahs        object {"surah": 36, "name": "يس", "from": 26, "to": 27}
               The verse text is downloaded from the King Fahd Complex Hafs
               edition (never typed by hand) and the reference is built from it.
  meaning, meaning_src
  story, story_src            (story may quote Quran inside «» quotes)
  lesson
  friday       optional object: {"title": "...", "items": [["text","source"], ...], "closing": "..."}
"""
import json, math, os, random, sys, unicodedata
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
FD = os.path.join(HERE, "fonts")
QURAN = os.path.join(FD, "AmiriQuran-Regular.ttf")
BOLD = os.path.join(FD, "Tajawal-Bold.ttf")
MED = os.path.join(FD, "Tajawal-Medium.ttf")

W, H = 1080, 1920
TOP_SAFE, BOT_SAFE = 250, 1590          # Instagram UI covers above/below these
CONTENT_TOP, CONTENT_BOT = TOP_SAFE + 110, BOT_SAFE - 90

NAVY_IN, NAVY_OUT = (16, 42, 92), (5, 16, 40)
GOLD, YELLOW, WHITE, SOFT = (212, 175, 55), (255, 210, 63), (255, 255, 255), (200, 210, 230)
HANDLE = "@al.quran.kareem105"


SRC = "https://raw.githubusercontent.com/fawazahmed0/quran-api/1/editions/ara-quranuthmanihaf/{s}/{a}.json"
AR_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")

def fetch_verse(surah, a_from, a_to):
    """Exact King Fahd Complex (Madinah mushaf, Hafs) text, never typed by hand."""
    import urllib.request
    parts = []
    for a in range(int(a_from), int(a_to) + 1):
        url = SRC.format(s=int(surah), a=a)
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                data = json.load(r)
        except Exception as e:
            raise RenderError(f"could not fetch Quran text {surah}:{a} ({e})")
        if int(data.get("chapter", -1)) != int(surah) or int(data.get("verse", -1)) != a or not data.get("text"):
            raise RenderError(f"unexpected Quran source data for {surah}:{a}")
        parts.append(data["text"].strip() + " ﴿" + str(a).translate(AR_DIGITS) + "﴾")
    return " ".join(parts)

def make_ref(name, a_from, a_to):
    a_from, a_to = int(a_from), int(a_to)
    nums = str(a_from).translate(AR_DIGITS) if a_from == a_to else \
        f"{str(a_from).translate(AR_DIGITS)}–{str(a_to).translate(AR_DIGITS)}"
    return f"سورة {name}: {nums}"

_cmaps = {}
def cmap(path):
    if path not in _cmaps:
        _cmaps[path] = set(TTFont(path).getBestCmap().keys())
    return _cmaps[path]

class RenderError(Exception):
    pass

def plain(text):
    """Make text safe for the Tajawal (non-Quran) font: map/drop Quranic-only marks."""
    text = text.replace("ﷺ", "صلى الله عليه وسلم").replace("﴿", "«").replace("﴾", "»").replace("ٱ", "ا")
    have = cmap(BOLD)
    out = []
    for ch in text:
        if ord(ch) in have or ch in " \n":
            out.append(ch)
        elif unicodedata.category(ch) == "Mn":
            continue  # drop decorative combining marks the font lacks
        else:
            out.append(ch)  # keep; check_glyphs will flag it
    return "".join(out)

def check_glyphs(text, path, label):
    have = cmap(path)
    bad = sorted({ch for ch in text if ch not in " \n‏‎" and ord(ch) not in have})
    if bad:
        raise RenderError(f"{label}: font {os.path.basename(path)} cannot draw " +
                          ", ".join(f"U+{ord(c):04X}" for c in bad))

def font(path, size):
    return ImageFont.truetype(path, size, layout_engine=ImageFont.Layout.RAQM)

def tw(d, s, f):
    return d.textlength(s, font=f, direction="rtl", language="ar")

def wrap(d, text, f, maxw):
    lines = []
    for para in text.split("\n"):
        cur = ""
        for w in para.split():
            t = (cur + " " + w).strip()
            if not cur or tw(d, t, f) <= maxw:
                cur = t
            else:
                lines.append(cur); cur = w
        if cur:
            lines.append(cur)
    return lines

class Block:
    def __init__(self, text, path, size, color, maxw=900, lh=1.55, gap=0, min_size=None, kind="text"):
        self.text, self.path, self.size, self.color = text, path, size, color
        self.maxw, self.lh, self.gap, self.min_size, self.kind = maxw, lh, gap, min_size or size, kind

    def layout(self, d, scale=1.0):
        self.cur = max(self.min_size, int(self.size * scale))
        self.f = font(self.path, self.cur)
        self.lines = [] if self.kind == "divider" else wrap(d, self.text, self.f, self.maxw)
        self.step = int(self.cur * self.lh)
        self.h = 40 if self.kind == "divider" else self.step * len(self.lines)
        if self.path == QURAN and self.lines:
            self.h += int(self.cur * 1.0)  # Amiri Quran marks hang below the line
        return self.gap + self.h

def stack(d, blocks, top=CONTENT_TOP, bot=CONTENT_BOT):
    """Shrink all blocks together until they fit, then centre vertically."""
    scale = 1.0
    while True:
        total = sum(b.layout(d, scale) for b in blocks)
        too_wide = any(tw(d, ln, bl.f) > W - 100 for bl in blocks for ln in bl.lines)
        if total <= bot - top and not too_wide:
            break
        if all(b.cur <= b.min_size for b in blocks):
            raise RenderError("text too long to fit on one slide")
        scale -= 0.04
    y = top + (bot - top - total) // 2
    for b in blocks:
        y += b.gap
        if b.kind == "divider":
            gold_divider(d, y + 20)
        else:
            for ln in b.lines:
                d.text((W / 2 - tw(d, ln, b.f) / 2, y), ln, font=b.f, fill=b.color,
                       direction="rtl", language="ar")
                y += b.step
            y += b.h - b.step * len(b.lines)  # extra padding (e.g. under Quran lines)
            continue
        y += b.h

# ---------- decoration ----------
def navy_bg(seed):
    small = Image.new("RGB", (W // 4, H // 4))
    sp = small.load()
    cx, cy, R = W / 2, H * 0.42, math.hypot(W, H) * 0.62
    for y in range(H // 4):
        for x in range(W // 4):
            t = min(1, math.hypot(x * 4 - cx, y * 4 - cy) / R)
            sp[x, y] = tuple(int(NAVY_IN[i] * (1 - t) + NAVY_OUT[i] * t) for i in range(3))
    img = small.resize((W, H), Image.BILINEAR)
    stars(img, seed, 140)
    return img

def stars(img, seed, n, color=(255, 255, 255)):
    rnd = random.Random(seed)
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = ImageDraw.Draw(layer)
    for _ in range(n):
        x, y, r = rnd.randint(0, W), rnd.randint(0, H), rnd.choice([1, 1, 1, 2, 2, 3])
        g.ellipse((x - r, y - r, x + r, y + r), fill=color + (rnd.randint(60, 200),))
    img.paste(layer.filter(ImageFilter.GaussianBlur(2)), (0, 0), layer.filter(ImageFilter.GaussianBlur(2)))
    img.paste(layer, (0, 0), layer)

def star(d, cx, cy, r, color):
    pts = [(cx + (r if i % 2 == 0 else r * 0.45) * math.cos(math.pi / 8 * i - math.pi / 2),
            cy + (r if i % 2 == 0 else r * 0.45) * math.sin(math.pi / 8 * i - math.pi / 2)) for i in range(16)]
    d.polygon(pts, fill=color)

def gold_divider(d, y, w=360):
    d.line((W / 2 - w / 2, y, W / 2 - 22, y), fill=GOLD, width=3)
    d.line((W / 2 + 22, y, W / 2 + w / 2, y), fill=GOLD, width=3)
    star(d, W / 2, y, 14, GOLD)

def pill(d, text, cy, fg=NAVY_OUT, bg=GOLD, size=32):
    f = font(BOLD, size)
    w = tw(d, text, f) + 64
    d.rounded_rectangle((W / 2 - w / 2, cy - 34, W / 2 + w / 2, cy + 34), radius=34, fill=bg)
    d.text((W / 2 - tw(d, text, f) / 2, cy - size * 0.68), text, font=f, fill=fg, direction="rtl", language="ar")

def footer(d, color=SOFT):
    f = font(MED, 30)
    d.text((W / 2 - d.textlength(HANDLE, font=f) / 2, BOT_SAFE - 20), HANDLE, font=f, fill=color)

def save(img, path):
    img.convert("RGB").save(path, "JPEG", quality=92)

# ---------- slides ----------
def render(c, out):
    os.makedirs(out, exist_ok=True)
    ay = c["ayahs"]  # {"surah": 36, "name": "يس", "from": 26, "to": 27}
    c["verse"] = fetch_verse(ay["surah"], ay["from"], ay["to"])
    c["ref"] = make_ref(ay["name"], ay["from"], ay["to"])
    for k in ("hook", "meaning", "meaning_src", "story", "story_src", "lesson", "date_label", "ref"):
        c[k] = plain(c[k])
        check_glyphs(c[k], BOLD, k)
    check_glyphs(c["verse"], QURAN, "verse")

    # 1: hook + verse
    img = navy_bg(1); d = ImageDraw.Draw(img); pill(d, "آية اليوم  ١/٣", TOP_SAFE + 40)
    stack(d, [Block(c["hook"], BOLD, 58, WHITE, lh=1.4, min_size=44),
              Block("", BOLD, 10, GOLD, gap=40, kind="divider"),
              Block(c["verse"], QURAN, 66, WHITE, maxw=920, lh=1.95, gap=50, min_size=46),
              Block(c["ref"], BOLD, 36, GOLD, gap=30, lh=1.3)])
    footer(d); save(img, os.path.join(out, "1.jpg"))

    # 2: story
    img = navy_bg(2); d = ImageDraw.Draw(img); pill(d, "آية اليوم  ٢/٣", TOP_SAFE + 40)
    stack(d, [Block("القصة", BOLD, 56, GOLD, lh=1.3),
              Block("", BOLD, 10, GOLD, gap=20, kind="divider"),
              Block(c["story"], BOLD, 48, WHITE, lh=1.62, gap=50, min_size=36),
              Block("(" + c["story_src"] + ")", MED, 30, SOFT, gap=20, lh=1.4, min_size=26)])
    footer(d); save(img, os.path.join(out, "2.jpg"))

    # 3: meaning + lesson
    img = navy_bg(3); d = ImageDraw.Draw(img); pill(d, "آية اليوم  ٣/٣", TOP_SAFE + 40)
    stack(d, [Block("المعنى", BOLD, 44, GOLD, lh=1.3),
              Block(c["meaning"], BOLD, 46, WHITE, lh=1.58, gap=16, min_size=34),
              Block("(" + c["meaning_src"] + ")", MED, 28, SOFT, gap=8, lh=1.5),
              Block("", BOLD, 10, GOLD, gap=30, kind="divider"),
              Block("الفائدة", BOLD, 44, GOLD, gap=40, lh=1.3),
              Block(c["lesson"], BOLD, 52, YELLOW, maxw=880, lh=1.6, gap=16, min_size=38)])
    footer(d); save(img, os.path.join(out, "3.jpg"))

    if c.get("friday"):
        render_friday(c["friday"], out)

def render_friday(fr, out):
    title = plain(fr.get("title", "جمعة مباركة"))
    items = [(plain(t), plain(s)) for t, s in fr["items"]]
    closing = plain(fr.get("closing", ""))
    for t, s in items:
        check_glyphs(t + s, BOLD, "friday item")
    check_glyphs(title + closing, BOLD, "friday title")

    img = Image.new("RGB", (W, H), (8, 8, 8))
    stars(img, 7, 70, color=(212, 175, 55))
    d = ImageDraw.Draw(img)
    m = 70
    d.rectangle((m, TOP_SAFE - 20, W - m, BOT_SAFE + 10), outline=GOLD, width=3)
    d.rectangle((m + 16, TOP_SAFE - 4, W - m - 16, BOT_SAFE - 6), outline=(120, 98, 30), width=2)
    for x, y in [(m, TOP_SAFE - 20), (W - m, TOP_SAFE - 20), (m, BOT_SAFE + 10), (W - m, BOT_SAFE + 10)]:
        star(d, x, y, 22, GOLD)
    blocks = [Block(title, BOLD, 84, GOLD, lh=1.25, min_size=60),
              Block("", BOLD, 10, GOLD, gap=24, kind="divider")]
    for i, (t, s) in enumerate(items):
        blocks.append(Block(t, BOLD, 50, WHITE, maxw=820, lh=1.5, gap=56 if i == 0 else 44, min_size=36))
        if s:
            blocks.append(Block("(" + s + ")", MED, 28, (170, 150, 90), maxw=820, lh=1.4, gap=6))
    if closing:
        blocks += [Block("", BOLD, 10, GOLD, gap=50, kind="divider"),
                   Block(closing, BOLD, 46, (235, 225, 200), maxw=820, lh=1.6, gap=50, min_size=34)]
    stack(d, blocks, top=TOP_SAFE + 60, bot=BOT_SAFE - 100)
    f = font(MED, 30)
    d.text((W / 2 - d.textlength(HANDLE, font=f) / 2, BOT_SAFE - 70), HANDLE, font=f, fill=GOLD)
    save(img, os.path.join(out, "friday.jpg"))

if __name__ == "__main__":
    try:
        render(json.load(open(sys.argv[1], encoding="utf-8")), sys.argv[2])
        print("OK")
    except RenderError as e:
        print("RENDER ERROR:", e); sys.exit(2)
