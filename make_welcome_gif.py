"""Botning /start xabari uchun welcome.gif ni yaratadi (logotip + neon "arcade" fon).

Ishlatish:  python make_welcome_gif.py logo.png welcome.gif
Matn yoki ranglarni o'zgartirmoqchi bo'lsangiz, pastdagi TEXT va ACCENT ni tahrirlang.
"""
import math, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, N, MS = 432, 243, 40, 70           # o'lcham, kadrlar soni, kadr davomiyligi (ms)
BG, ACCENT, TEXT = (11, 11, 14), (10, 186, 181), "PRESS START"
HORIZON = 142
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

logo = Image.open(sys.argv[1] if len(sys.argv) > 1 else "logo.png").convert("RGBA")
logo = logo.crop(logo.getbbox())
lh = 112
logo = logo.resize((round(logo.width * lh / logo.height), lh), Image.LANCZOS)
try:
    font = ImageFont.truetype(FONT, 15)
except OSError:
    font = ImageFont.load_default()
stars = [(37, 22, 0), (88, 61, 7), (151, 17, 13), (214, 48, 21), (279, 14, 3), (338, 57, 17), (395, 26, 10), (62, 108, 25), (372, 99, 30), (20, 78, 15), (410, 70, 5)]


def frame(i):
    t = i / N
    img = Image.new("RGBA", (W, H), BG + (255,))
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    # perspektiv to'r (pastki yarmi): gorizontal chiziqlar yaqinlashadi, vertikallari markazga yig'iladi
    for k in range(-9, 10):
        d.line([(W / 2, HORIZON), (W / 2 + k * 58, H + 4)], fill=ACCENT + (70,), width=1)
    rows = 9
    for r in range(rows):
        p = ((r + t * 1) % rows) / rows
        y = HORIZON + (p ** 2) * (H - HORIZON)
        d.line([(0, y), (W, y)], fill=ACCENT + (int(30 + 150 * p),), width=1)
    d.line([(0, HORIZON), (W, HORIZON)], fill=ACCENT + (190,), width=1)
    img = Image.alpha_composite(img, ov)
    # yulduzlar (miltillaydi)
    px = ImageDraw.Draw(img)
    for x, y, ph in stars:
        a = 0.5 + 0.5 * math.sin(2 * math.pi * (t * 2 + ph / 30))
        c = int(60 + 150 * a)
        px.rectangle([x, y, x + 1, y + 1], fill=(c, c, min(255, c + 25), 255))
    # logotip orqasidagi nur (pulsatsiya)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = ImageDraw.Draw(glow)
    s = 0.55 + 0.35 * (0.5 + 0.5 * math.sin(2 * math.pi * t))
    cy = 78
    g.ellipse([W / 2 - 92, cy - 62, W / 2 + 92, cy + 62], fill=ACCENT + (int(120 * s),))
    glow = glow.filter(ImageFilter.GaussianBlur(26))
    img = Image.alpha_composite(img, glow)
    # logotip (yengil tebranadi)
    bob = round(3 * math.sin(2 * math.pi * t))
    img.alpha_composite(logo, (round((W - logo.width) / 2), 22 + bob))
    # "PRESS START" (yonib-o'chadi)
    if i % 20 < 13:
        tw = d.textlength(TEXT, font=font) if hasattr(d, "textlength") else 100
        bx0, by0 = (W - tw) / 2 - 14, 191
        pl = ImageDraw.Draw(img)
        pl.rounded_rectangle([bx0, by0, bx0 + tw + 28, by0 + 28], radius=14, fill=(11, 11, 14, 235), outline=ACCENT + (255,), width=1)
        pl.text(((W - tw) / 2, by0 + 5), TEXT, font=font, fill=(63, 216, 211, 255))
    return img.convert("RGB")


frames = [frame(i) for i in range(N)]
pal = [f.quantize(colors=96, method=Image.MEDIANCUT, dither=Image.NONE) for f in frames]
pal[0].save(sys.argv[2] if len(sys.argv) > 2 else "welcome.gif", save_all=True, append_images=pal[1:], duration=MS, loop=0, optimize=True, disposal=1)
print("tayyor")
