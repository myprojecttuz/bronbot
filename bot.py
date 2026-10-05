import asyncio, os, json, hmac, hashlib, sqlite3, uuid
from urllib.parse import parse_qsl
from datetime import datetime, timedelta
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])
WEBAPP_URL = os.environ["WEBAPP_URL"]
PORT = int(os.getenv("PORT", 8080))
REMIND_MIN = 30  # bron boshlanishidan necha daqiqa oldin eslatish
INFO = {k: os.getenv(v, "") for k, v in {"address": "CLUB_ADDRESS", "phone": "CLUB_PHONE", "hours": "CLUB_HOURS", "admin": "ADMIN_USERNAME"}.items()}
INFO["admin"] = INFO["admin"].lstrip("@")

# Zonalar: narx (soatiga), kompyuter raqamlari va xususiyatlari.
# DIQQAT: "specs" ichidagi xususiyatlar NAMUNA, o'zingizning haqiqiy ma'lumotlaringizga almashtiring.
ZONES = {
    "MAIN": {"price": 15000, "pcs": list(range(1, 31)), "specs": ["Core i5", "RTX 3060", "16 GB RAM", "24\" 165 Hz"]},
    "SOLO": {"price": 25000, "pcs": [31, 132], "specs": ["Core i7", "RTX 4060", "32 GB RAM", "27\" 240 Hz", "Alohida xona"]},
    "TRIO": {"price": 20000, "pcs": list(range(33, 39)), "specs": ["Core i5", "RTX 3060 Ti", "16 GB RAM", "24\" 165 Hz", "3 kishilik xona"]},
    "SUPERVIP": {"price": 40000, "pcs": list(range(39, 45)), "specs": ["Core i9", "RTX 4080", "64 GB RAM", "27\" 360 Hz", "Premium kreslo"]},
    "WOMEN": {"price": 15000, "pcs": list(range(45, 51)), "specs": ["Core i5", "RTX 3060", "16 GB RAM", "24\" 165 Hz", "Qizlar zonasi"]},
    "STARWARS": {"price": 25000, "pcs": list(range(51, 57)), "specs": ["Core i7", "RTX 4070", "32 GB RAM", "27\" 240 Hz", "Tematik zona"]},
    "MARVEL": {"price": 25000, "pcs": list(range(57, 63)), "specs": ["Core i7", "RTX 4070", "32 GB RAM", "27\" 240 Hz", "Tematik zona"]},
}

bot = Bot(TOKEN)
dp = Dispatcher()
db = sqlite3.connect(os.getenv("DB_PATH", "club.db"), check_same_thread=False)
db.execute("""CREATE TABLE IF NOT EXISTS bookings(
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, name TEXT,
    zone TEXT, pc INTEGER, start TEXT, end TEXT,
    reminded INTEGER DEFAULT 0, started INTEGER DEFAULT 0, status TEXT DEFAULT 'pending', grp TEXT)""")
for col in ("status TEXT DEFAULT 'pending'", "grp TEXT"):
    try:
        db.execute(f"ALTER TABLE bookings ADD COLUMN {col}")
    except sqlite3.OperationalError:
        pass
db.commit()

ST = {"pending": "⏳ kutilmoqda", "confirmed": "✅ tasdiqlangan", "rejected": "❌ rad etilgan", "cancelled": "🚫 bekor qilingan"}
ACTIVE = "status IN ('pending','confirmed')"
COLS = "id,user_id,name,zone,pc,start,end,status,grp"


def now_iso():
    return datetime.now().isoformat(timespec="minutes")


def price(zone, st, en):
    h = (datetime.fromisoformat(en) - datetime.fromisoformat(st)).total_seconds() / 3600
    return int(ZONES[zone]["price"] * h)


def kb(*btns):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=d) for t, d in btns]])


def groups(where, params=(), order="start"):
    g = {}
    for r in db.execute(f"SELECT {COLS} FROM bookings WHERE {where} ORDER BY {order}, id", params):
        g.setdefault(r[8] or f"i{r[0]}", []).append(r)
    return list(g.values())


def group_of(id_):
    r = db.execute("SELECT grp FROM bookings WHERE id=?", (id_,)).fetchone()
    if not r:
        return None
    g = groups("grp=?", (r[0],)) if r[0] else groups("id=?", (id_,))
    return g[0] if g else None


def pcs_text(g):
    by = {}
    for r in g:
        by.setdefault(r[3], []).append(f"{r[4]:03d}")
    return " | ".join(f"{z} {', '.join(v)}" for z, v in by.items())


def total(g):
    return sum(price(r[3], r[5], r[6]) for r in g if r[3] in ZONES)


def gtext(g):
    r = g[0]
    return f"🖥 {len(g)} ta: {pcs_text(g)}\n🕒 {r[5][5:10]} {r[5][11:]}–{r[6][11:]}\n💰 {total(g):,} so'm\n{ST[r[7]]}"


def mark(g, col, val=1):
    db.execute(f"UPDATE bookings SET {col}=? WHERE id IN ({','.join('?' * len(g))})", (val, *[r[0] for r in g]))
    db.commit()


def check_init(init: str):
    d = dict(parse_qsl(init))
    h = d.pop("hash", "")
    s = "\n".join(f"{k}={v}" for k, v in sorted(d.items()))
    key = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(hmac.new(key, s.encode(), hashlib.sha256).hexdigest(), h):
        return None
    return json.loads(d["user"])


async def do_cancel(uid, id_):
    g = group_of(id_)
    if not g or g[0][1] != uid or g[0][7] not in ("pending", "confirmed") or g[0][5] <= now_iso():
        return None
    mark(g, "status", "cancelled")
    g = group_of(id_)
    await bot.send_message(ADMIN_ID, f"🚫 Mijoz bronni bekor qildi:\n👤 {g[0][2]}\n{gtext(g)}")
    return g


@dp.message(CommandStart())
async def start(m: Message):
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Bron qilish", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton(text="📋 Mening bronlarim", callback_data="my")]])
    await m.answer("Salom! Arcade Games ga xush kelibsiz 🎮\nKompyuterlarni bron qilish uchun tugmani bosing.", reply_markup=markup)


async def send_my(uid):
    gs = groups(f"user_id=? AND {ACTIVE} AND end>?", (uid, now_iso()))
    if not gs:
        return await bot.send_message(uid, "Sizda faol bronlar yo'q.")
    for g in gs:
        await bot.send_message(uid, gtext(g), reply_markup=kb(("🚫 Bekor qilish", f"cx:{g[0][0]}")))


@dp.message(Command("my"))
async def my_cmd(m: Message):
    await send_my(m.from_user.id)


@dp.callback_query(F.data == "my")
async def my_cb(c: CallbackQuery):
    await c.answer()
    await send_my(c.from_user.id)


@dp.callback_query(F.data.startswith("cx:"))
async def cancel_cb(c: CallbackQuery):
    g = await do_cancel(c.from_user.id, int(c.data[3:]))
    if not g:
        return await c.answer("Bekor qilib bo'lmaydi", show_alert=True)
    await c.message.edit_text(gtext(g))


# ---------- ADMIN ----------
def admin_menu():
    return kb(("📅 Bugun", "adm:today"), ("⏳ Kutilayotgan", "adm:pending"), ("📊 Statistika", "adm:stats"))


@dp.message(Command("admin"))
async def admin_cmd(m: Message):
    if m.from_user.id == ADMIN_ID:
        await m.answer("🛠 Admin panel", reply_markup=admin_menu())


@dp.callback_query(F.data.startswith("adm:"))
async def admin_cb(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("Ruxsat yo'q", show_alert=True)
    await c.answer()
    act, now = c.data[4:], datetime.now()
    day = now.strftime("%Y-%m-%d")
    if act in ("today", "pending"):
        gs = groups(f"start LIKE ? AND {ACTIVE}", (day + "%",)) if act == "today" else groups("status='pending' AND end>?", (now_iso(),))
        for g in gs:
            i = g[0][0]
            btns = [("✅ Tasdiqlash", f"ok:{i}"), ("❌ Rad etish", f"no:{i}")] if act == "pending" else [("🚫 Bekor qilish", f"no:{i}")]
            await bot.send_message(ADMIN_ID, f"👤 {g[0][2]}\n{gtext(g)}", reply_markup=kb(*btns))
        if not gs:
            await bot.send_message(ADMIN_ID, "Bronlar yo'q.")
    else:
        def stat(since):
            rows = db.execute("SELECT zone,start,end FROM bookings WHERE status='confirmed' AND start>=?", (since,)).fetchall()
            return len(rows), sum(price(*r) for r in rows if r[0] in ZONES)
        (tc, tr), (wc, wr) = stat(day), stat((now - timedelta(days=7)).strftime("%Y-%m-%d"))
        pend = len(groups("status='pending'"))
        await bot.send_message(ADMIN_ID, f"📊 Statistika (tasdiqlangan)\nBugun: {tc} ta PC, {tr:,} so'm\n7 kun: {wc} ta PC, {wr:,} so'm\n⏳ Kutilayotgan bronlar: {pend} ta")


@dp.callback_query(F.data.regexp(r"^(ok|no):"))
async def decide_cb(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return await c.answer("Ruxsat yo'q", show_alert=True)
    act, id_ = c.data.split(":")
    g = group_of(int(id_))
    if not g or g[0][7] not in ("pending", "confirmed"):
        return await c.answer("Bu bron endi faol emas", show_alert=True)
    mark(g, "status", "confirmed" if act == "ok" else "rejected")
    g = group_of(int(id_))
    await c.message.edit_text(f"👤 {g[0][2]}\n{gtext(g)}")
    await c.answer()
    if act == "ok":
        await bot.send_message(g[0][1], f"✅ Bronigiz tasdiqlandi!\n{gtext(g)}")
    else:
        await bot.send_message(g[0][1], f"❌ Afsus, bronigiz bekor qilindi (admin tomonidan).\n{gtext(g)}\nBoshqa vaqt yoki joy tanlab ko'ring.")


# ---------- WEB ----------
async def index(_):
    return web.FileResponse(os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html"))


async def zones(_):
    return web.json_response(ZONES)


async def info(_):
    return web.json_response(INFO)


async def busy(req):
    zone, date = req.query["zone"], req.query["date"]
    hi = (datetime.fromisoformat(date) + timedelta(days=2)).strftime("%Y-%m-%dT00:00")
    rows = db.execute(f"SELECT pc,start,end FROM bookings WHERE zone=? AND {ACTIVE} AND end>? AND start<?",
                      (zone, date + "T00:00", hi)).fetchall()
    return web.json_response([{"pc": r[0], "start": r[1], "end": r[2]} for r in rows])


async def book(req):
    b = await req.json()
    user = check_init(b.get("initData", ""))
    if not user:
        return web.json_response({"error": "Ruxsat yo'q"}, status=403)
    try:
        items = {(i["zone"], int(i["pc"])) for i in b["pcs"]}
        minutes = int(b["minutes"])
        start = datetime.fromisoformat(b["start"])
    except Exception:
        return web.json_response({"error": "Noto'g'ri ma'lumot"}, status=400)
    if not items or len(items) > 30 or not 30 <= minutes <= 1440 or any(z not in ZONES or p not in ZONES[z]["pcs"] for z, p in items):
        return web.json_response({"error": "Noto'g'ri ma'lumot"}, status=400)
    if start < datetime.now() - timedelta(minutes=1):
        return web.json_response({"error": "O'tgan vaqtni tanlab bo'lmaydi"}, status=400)
    s_ = start.isoformat(timespec="minutes")
    e_ = (start + timedelta(minutes=minutes)).isoformat(timespec="minutes")
    for z, p in sorted(items):
        if db.execute(f"SELECT 1 FROM bookings WHERE zone=? AND pc=? AND {ACTIVE} AND start<? AND end>?", (z, p, e_, s_)).fetchone():
            return web.json_response({"error": f"{z} {p:03d} shu vaqtda band"}, status=409)
    grp = uuid.uuid4().hex[:8]
    name = user.get("first_name", "") + (" @" + user["username"] if user.get("username") else "")
    for z, p in sorted(items):
        db.execute("INSERT INTO bookings(user_id,name,zone,pc,start,end,grp) VALUES(?,?,?,?,?,?,?)", (user["id"], name, z, p, s_, e_, grp))
    db.commit()
    g = groups("grp=?", (grp,))[0]
    await bot.send_message(ADMIN_ID, f"🆕 Yangi bron\n👤 {name}\n{gtext(g)}",
                           reply_markup=kb(("✅ Tasdiqlash", f"ok:{g[0][0]}"), ("❌ Rad etish", f"no:{g[0][0]}")))
    await bot.send_message(user["id"], f"📨 Bron yuborildi, admin tasdiqlashini kuting.\n{gtext(g)}",
                           reply_markup=kb(("📋 Mening bronlarim", "my")))
    return web.json_response({"ok": True})


async def my(req):
    user = check_init((await req.json()).get("initData", ""))
    if not user:
        return web.json_response({"error": "Ruxsat yo'q"}, status=403)
    now = now_iso()
    gs = groups("user_id=?", (user["id"],), "start DESC")[:30]
    return web.json_response([{"id": g[0][0], "count": len(g), "pcs": pcs_text(g), "start": g[0][5], "end": g[0][6],
                               "status": g[0][7], "price": total(g),
                               "can_cancel": g[0][7] in ("pending", "confirmed") and g[0][5] > now} for g in gs])


async def cancel(req):
    b = await req.json()
    user = check_init(b.get("initData", ""))
    if not user:
        return web.json_response({"error": "Ruxsat yo'q"}, status=403)
    if not await do_cancel(user["id"], int(b.get("id", 0))):
        return web.json_response({"error": "Bekor qilib bo'lmaydi"}, status=400)
    return web.json_response({"ok": True})


async def reminder_loop():
    while True:
        try:
            now = datetime.now()
            soon = (now + timedelta(minutes=REMIND_MIN)).isoformat(timespec="minutes")
            for g in groups("status='confirmed' AND reminded=0 AND start<=?", (soon,)):
                await bot.send_message(g[0][1], f"⏰ Eslatma: bronigiz {REMIND_MIN} daqiqadan keyin boshlanadi.\n{gtext(g)}")
                mark(g, "reminded")
            for g in groups("status='confirmed' AND started=0 AND start<=?", (now.isoformat(timespec="minutes"),)):
                await bot.send_message(g[0][1], f"🎮 Vaqtingiz boshlandi! Kutib turibmiz!\n{gtext(g)}")
                await bot.send_message(ADMIN_ID, f"🔔 Mijoz vaqti boshlandi: {g[0][2]}\n{gtext(g)}")
                mark(g, "started")
        except Exception as e:
            print("reminder error:", e)
        await asyncio.sleep(30)


async def main():
    app = web.Application()
    app.add_routes([web.get("/", index), web.get("/api/zones", zones), web.get("/api/busy", busy),
                    web.post("/api/book", book), web.post("/api/my", my), web.post("/api/cancel", cancel),
                    web.get("/api/info", info)])
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    asyncio.create_task(reminder_loop())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
