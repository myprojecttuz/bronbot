import asyncio, os, json, hmac, hashlib, sqlite3, uuid
from urllib.parse import parse_qsl
from datetime import datetime, timedelta
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, CallbackQuery, Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])
WEBAPP_URL = os.environ["WEBAPP_URL"]
PORT = int(os.getenv("PORT", 8080))
REMIND_MIN = 30  # bron boshlanishidan necha daqiqa oldin eslatish
INFO = {k: os.getenv(v, "") for k, v in {"address": "CLUB_ADDRESS", "phone": "CLUB_PHONE", "hours": "CLUB_HOURS", "admin": "ADMIN_USERNAME"}.items()}
INFO["admin"] = INFO["admin"].lstrip("@")

# Zonalar: sarlavha, narx (soatiga), kompyuter raqamlari va xususiyatlari.
def spec(cpu, gpu, ram, mon, kbd, mouse, hp):
    return {"Protsessor": cpu, "Videokarta": gpu, "Operativ xotira": ram, "Monitor": mon,
            "Klaviatura": kbd, "Sichqoncha": mouse, "Quloqchin": hp}


_BASE = ("Intel Core i5-12400", "Nvidia RTX 2060 Super", "16 GB, 3200 MHz", 'MSI 27", 240 Hz')
ZONES = {
    "MAIN": {"title": "Main zone", "price": 20000, "pcs": list(range(1, 31)),
             "specs": spec(*_BASE, "VGN N75", "Asus ROG Gladius 3", "Asus TUF H1 Gen2")},
    "SOLO": {"title": "Solo + Stream Room", "price": 50000, "pcs": [31, 132],
             "specs": spec("AMD Ryzen 5 7500F", "GeForce RTX 5060 (8 GB)", "32 GB, 5600 MHz", 'HKC 24.5", 400 Hz',
                           "Red Square Alumix Kitsune", "Lamzu Atlantis OG V2 Pro", "Red Square Graphite V2 Mint")},
    "TRIO": {"title": "Trio Room", "price": 35000, "pcs": list(range(33, 39)),
             "specs": spec("AMD Ryzen 5 7500F", "RTX 5060 (8 GB)", "32 GB, 5600 MHz", 'HKC 24.5", 400 Hz',
                           "Aula F99 Pro", "Logitech G Pro X Superlight", "Logitech G Pro X")},
    "SUPERVIP": {"title": "Super VIP Room", "price": 40000, "pcs": list(range(39, 45)),
                 "specs": spec("AMD Ryzen 7 7800X3D (suv sovutgichli)", "GeForce RTX 5070 (12 GB)", "32 GB, 4800 MHz",
                               'Alienware 25", 500 Hz', "VXE V87 Pro", "Logitech G Pro Superlight 2", "Logitech G Pro X Wireless")},
    "WOMEN": {"title": "Women's Area", "price": 30000, "pcs": list(range(45, 51)),
              "specs": spec(*_BASE, "Redragon Evia", "Redragon K1ng Pro", "Razer BlackShark V2 X")},
    "STARWARS": {"title": "Star Wars Area", "price": 30000, "pcs": list(range(51, 57)),
                 "specs": spec(*_BASE, "Royal Kludge M87", "VGN ATK Mad G Pro", "Razer BlackShark V2 X")},
    "MARVEL": {"title": "Marvel Area", "price": 30000, "pcs": list(range(57, 63)),
               "specs": spec(*_BASE, "Royal Kludge M87", "VGN ATK Mad G Pro", "Razer BlackShark V2 X")},
}

bot = Bot(TOKEN)
dp = Dispatcher()
db = sqlite3.connect(os.getenv("DB_PATH", "club.db"), check_same_thread=False)
db.execute("""CREATE TABLE IF NOT EXISTS bookings(
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, name TEXT,
    zone TEXT, pc INTEGER, start TEXT, end TEXT,
    reminded INTEGER DEFAULT 0, started INTEGER DEFAULT 0, status TEXT DEFAULT 'pending', grp TEXT)""")
for col in ("status TEXT DEFAULT 'pending'", "grp TEXT", "rate INTEGER"):
    try:
        db.execute(f"ALTER TABLE bookings ADD COLUMN {col}")
    except sqlite3.OperationalError:
        pass
db.execute("CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY, phone TEXT, name TEXT, created TEXT)")
db.execute("CREATE TABLE IF NOT EXISTS prices(zone TEXT PRIMARY KEY, price INTEGER)")
for _z, _p in db.execute("SELECT zone,price FROM prices").fetchall():
    if _z in ZONES:
        ZONES[_z]["price"] = _p
db.commit()

ST = {"pending": "⏳ kutilmoqda", "confirmed": "✅ tasdiqlangan", "rejected": "❌ rad etilgan", "cancelled": "🚫 bekor qilingan"}
ACTIVE = "status IN ('pending','confirmed')"
COLS = "id,user_id,name,zone,pc,start,end,status,grp,rate"


def now_iso():
    return datetime.now().isoformat(timespec="minutes")


def price(zone, st, en, rate=None):
    h = (datetime.fromisoformat(en) - datetime.fromisoformat(st)).total_seconds() / 3600
    return int((rate or ZONES[zone]["price"]) * h)


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
    return sum(price(r[3], r[5], r[6], r[9]) for r in g if r[3] in ZONES)


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


def registered(uid):
    return db.execute("SELECT 1 FROM users WHERE user_id=?", (uid,)).fetchone() is not None


def phone_of(uid):
    r = db.execute("SELECT phone FROM users WHERE user_id=?", (uid,)).fetchone()
    return r[0] if r else ""


async def send_menu(m: Message):
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Bron qilish", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton(text="📋 Mening bronlarim", callback_data="my")]])
    await m.answer("Arcade Games ga xush kelibsiz 🎮\nKompyuterlarni bron qilish uchun tugmani bosing.", reply_markup=markup)


@dp.message(CommandStart())
async def start(m: Message):
    if not registered(m.from_user.id):
        kbd = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📱 Raqamni yuborish", request_contact=True)]],
                                  resize_keyboard=True, one_time_keyboard=True)
        return await m.answer("Salom! Arcade Games ga xush kelibsiz 🎮\nRo'yxatdan o'tish uchun telefon raqamingizni yuboring (pastdagi tugma).", reply_markup=kbd)
    await send_menu(m)


@dp.message(F.contact)
async def got_contact(m: Message):
    c = m.contact
    print("contact keldi:", m.from_user.id, c.user_id)
    if c.user_id and c.user_id != m.from_user.id:
        return await m.answer("Iltimos, o'zingizning raqamingizni tugma orqali yuboring.")
    phone = c.phone_number if c.phone_number.startswith("+") else "+" + c.phone_number
    db.execute("INSERT OR REPLACE INTO users(user_id,phone,name,created) VALUES(?,?,?,?)",
               (m.from_user.id, phone, m.from_user.full_name, now_iso()))
    db.commit()
    await m.answer("✅ Ro'yxatdan o'tdingiz! Endi web app orqali bron qilishingiz mumkin.", reply_markup=ReplyKeyboardRemove())
    await send_menu(m)
    try:
        await bot.send_message(ADMIN_ID, f"🆕 Yangi mijoz: {m.from_user.full_name} {phone}")
    except Exception as e:
        print("admin xabari yuborilmadi:", e)


@dp.message(Command("status"))
async def status_cmd(m: Message):
    ph = phone_of(m.from_user.id)
    await m.answer(f"Bot versiyasi: {APP_VERSION}\nRo'yxatdan o'tgan: {'ha, ' + ph if ph else "yo'q"}\nID: {m.from_user.id}")


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
            rows = db.execute("SELECT zone,start,end,rate FROM bookings WHERE status='confirmed' AND start>=?", (since,)).fetchall()
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
APP_VERSION = "v5"


async def version(_):
    return web.json_response({"version": APP_VERSION})


async def index(_):
    return web.FileResponse(os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html"), headers={"Cache-Control": "no-store"})


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
    if not registered(user["id"]):
        return web.json_response({"error": "Avval ro'yxatdan o'ting", "register": True}, status=403)
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
    ph = phone_of(user["id"])
    name += f" 📞 {ph}" if ph else ""
    for z, p in sorted(items):
        db.execute("INSERT INTO bookings(user_id,name,zone,pc,start,end,grp,rate) VALUES(?,?,?,?,?,?,?,?)", (user["id"], name, z, p, s_, e_, grp, ZONES[z]["price"]))
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


async def admin_auth(req):
    b = await req.json()
    u = check_init(b.get("initData", ""))
    return b, (u if u and u["id"] == ADMIN_ID else None)


def gdict(g):
    return {"id": g[0][0], "name": g[0][2], "count": len(g), "pcs": pcs_text(g), "start": g[0][5],
            "end": g[0][6], "status": g[0][7], "price": total(g)}


async def admin_data(req):
    _, u = await admin_auth(req)
    if not u:
        return web.json_response({"error": "Ruxsat yo'q"}, status=403)
    now = datetime.now()
    day = now.strftime("%Y-%m-%d")

    def stat(since):
        rows = db.execute("SELECT zone,start,end,rate FROM bookings WHERE status='confirmed' AND start>=?", (since,)).fetchall()
        return {"n": len(rows), "sum": sum(price(*r) for r in rows if r[0] in ZONES)}
    return web.json_response({
        "zones": {z: {"title": v["title"], "price": v["price"]} for z, v in ZONES.items()},
        "users": db.execute("SELECT COUNT(*) FROM users").fetchone()[0],
        "stats": {"today": stat(day), "week": stat((now - timedelta(days=7)).strftime("%Y-%m-%d"))},
        "pending": [gdict(g) for g in groups("status='pending' AND end>?", (now_iso(),))],
        "today": [gdict(g) for g in groups(f"start LIKE ? AND {ACTIVE}", (day + "%",))]})


async def admin_decide(req):
    b, u = await admin_auth(req)
    if not u:
        return web.json_response({"error": "Ruxsat yo'q"}, status=403)
    act = b.get("action")
    g = group_of(int(b.get("id", 0)))
    if act not in ("ok", "no") or not g or g[0][7] not in ("pending", "confirmed"):
        return web.json_response({"error": "Bu bron endi faol emas"}, status=400)
    mark(g, "status", "confirmed" if act == "ok" else "rejected")
    g = group_of(g[0][0])
    if act == "ok":
        await bot.send_message(g[0][1], f"✅ Bronigiz tasdiqlandi!\n{gtext(g)}")
    else:
        await bot.send_message(g[0][1], f"❌ Afsus, bronigiz bekor qilindi (admin tomonidan).\n{gtext(g)}\nBoshqa vaqt yoki joy tanlab ko'ring.")
    return web.json_response({"ok": True})


async def me(req):
    u = check_init((await req.json()).get("initData", ""))
    if not u:
        return web.json_response({"error": "Ruxsat yo'q"}, status=403)
    return web.json_response({"registered": registered(u["id"]), "phone": phone_of(u["id"]), "admin": u["id"] == ADMIN_ID})


async def admin_price(req):
    b, u = await admin_auth(req)
    if not u:
        return web.json_response({"error": "Ruxsat yo'q"}, status=403)
    z = b.get("zone")
    try:
        p = int(b.get("price"))
    except (TypeError, ValueError):
        p = 0
    if z not in ZONES or not 1000 <= p <= 10_000_000:
        return web.json_response({"error": "Narx noto'g'ri"}, status=400)
    ZONES[z]["price"] = p
    db.execute("INSERT OR REPLACE INTO prices(zone,price) VALUES(?,?)", (z, p))
    db.commit()
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
                    web.get("/api/info", info), web.get("/api/version", version), web.post("/api/admin", admin_data), web.post("/api/admin/decide", admin_decide),
                    web.post("/api/me", me), web.post("/api/admin/price", admin_price)])
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    try:
        INFO["bot"] = (await bot.get_me()).username
    except Exception as e:
        print("get_me xatosi:", e)
    asyncio.create_task(reminder_loop())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
