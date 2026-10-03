import asyncio, os, json, hmac, hashlib, sqlite3
from urllib.parse import parse_qsl
from datetime import datetime, timedelta
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram import F
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton

TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_ID"])
WEBAPP_URL = os.environ["WEBAPP_URL"]  # https://sizning-domen.uz
PORT = int(os.getenv("PORT", 8080))
REMIND_MIN = 30  # bron boshlanishidan necha daqiqa oldin eslatish

# Zonalarni shu yerda o'zgartiring: nomi -> narx (soatiga) va kompyuterlar soni
ZONES = {
    "MAIN": {"price": 15000, "pcs": list(range(1, 31))},
    "SOLO": {"price": 25000, "pcs": [31, 132]},
    "TRIO": {"price": 20000, "pcs": list(range(33, 39))},
    "SUPERVIP": {"price": 40000, "pcs": list(range(39, 45))},
    "WOMEN": {"price": 15000, "pcs": list(range(45, 51))},
    "STARWARS": {"price": 25000, "pcs": list(range(51, 57))},
    "MARVEL": {"price": 25000, "pcs": list(range(57, 63))},
}

bot = Bot(TOKEN)
dp = Dispatcher()
db = sqlite3.connect(os.getenv("DB_PATH", "club.db"), check_same_thread=False)
db.execute("""CREATE TABLE IF NOT EXISTS bookings(
    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, name TEXT,
    zone TEXT, pc INTEGER, start TEXT, end TEXT,
    reminded INTEGER DEFAULT 0, started INTEGER DEFAULT 0, status TEXT DEFAULT 'pending')""")
try:
    db.execute("ALTER TABLE bookings ADD COLUMN status TEXT DEFAULT 'pending'")
except sqlite3.OperationalError:
    pass
db.commit()

ST = {"pending": "⏳ kutilmoqda", "confirmed": "✅ tasdiqlangan", "rejected": "❌ rad etilgan", "cancelled": "🚫 bekor qilingan"}
ACTIVE = "status IN ('pending','confirmed')"
COLS = "id,user_id,name,zone,pc,start,end,status"


def price(zone, st, en):
    h = (datetime.fromisoformat(en) - datetime.fromisoformat(st)).total_seconds() / 3600
    return int(ZONES[zone]["price"] * h)


def line(r):
    return f"#{r[0]} {r[3]} PC{r[4]} | {r[5][5:10]} {r[5][11:]}–{r[6][11:]} | {ST[r[7]]}"


def kb(*btns):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=d) for t, d in btns]])



INFO = {k: os.getenv(v, "") for k, v in {"address": "CLUB_ADDRESS", "phone": "CLUB_PHONE", "hours": "CLUB_HOURS", "admin": "ADMIN_USERNAME"}.items()}
INFO["admin"] = INFO["admin"].lstrip("@")


def check_init(init: str):
    """Telegram initData imzosini tekshiradi, user qaytaradi."""
    d = dict(parse_qsl(init))
    h = d.pop("hash", "")
    s = "\n".join(f"{k}={v}" for k, v in sorted(d.items()))
    key = hmac.new(b"WebAppData", TOKEN.encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(hmac.new(key, s.encode(), hashlib.sha256).hexdigest(), h):
        return None
    return json.loads(d["user"])


@dp.message(CommandStart())
async def start(m: Message):
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Bron qilish", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton(text="📋 Mening bronlarim", callback_data="my")]])
    await m.answer("Salom! Game clubga xush kelibsiz 🎮\nZona va kompyuterni bron qilish uchun tugmani bosing.", reply_markup=markup)


async def send_my(uid):
    rows = db.execute(f"SELECT {COLS} FROM bookings WHERE user_id=? AND {ACTIVE} AND end>? ORDER BY start",
                      (uid, datetime.now().isoformat(timespec="minutes"))).fetchall()
    if not rows:
        return await bot.send_message(uid, "Sizda faol bronlar yo'q.")
    for r in rows:
        await bot.send_message(uid, line(r), reply_markup=kb(("🚫 Bekor qilish", f"cx:{r[0]}")))


@dp.message(Command("my"))
async def my_cmd(m: Message):
    await send_my(m.from_user.id)


@dp.callback_query(F.data == "my")
async def my_cb(c: CallbackQuery):
    await c.answer()
    await send_my(c.from_user.id)


@dp.callback_query(F.data.startswith("cx:"))
async def cancel_cb(c: CallbackQuery):
    r = db.execute(f"SELECT {COLS} FROM bookings WHERE id=? AND user_id=? AND {ACTIVE}",
                   (c.data[3:], c.from_user.id)).fetchone()
    if not r or r[5] <= datetime.now().isoformat(timespec="minutes"):
        return await c.answer("Bekor qilib bo'lmaydi", show_alert=True)
    db.execute("UPDATE bookings SET status='cancelled' WHERE id=?", (r[0],))
    db.commit()
    await c.message.edit_text(line(r[:7] + ("cancelled",)))
    await bot.send_message(ADMIN_ID, f"🚫 Mijoz bronni bekor qildi:\n{r[2]}\n{line(r[:7] + ('cancelled',))}")


# ---------- ADMIN ----------
def is_admin(uid):
    return uid == ADMIN_ID


def admin_menu():
    return kb(("📅 Bugun", "adm:today"), ("⏳ Kutilayotgan", "adm:pending"), ("📊 Statistika", "adm:stats"))


@dp.message(Command("admin"))
async def admin_cmd(m: Message):
    if is_admin(m.from_user.id):
        await m.answer("🛠 Admin panel", reply_markup=admin_menu())


@dp.callback_query(F.data.startswith("adm:"))
async def admin_cb(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Ruxsat yo'q", show_alert=True)
    await c.answer()
    act, now = c.data[4:], datetime.now()
    day = now.strftime("%Y-%m-%d")
    if act == "today":
        rows = db.execute(f"SELECT {COLS} FROM bookings WHERE start LIKE ? AND {ACTIVE} ORDER BY start", (day + "%",)).fetchall()
        for r in rows:
            await bot.send_message(ADMIN_ID, f"👤 {r[2]}\n{line(r)}",
                                   reply_markup=kb(("🚫 Bekor qilish", f"no:{r[0]}")))
        if not rows:
            await bot.send_message(ADMIN_ID, "Bugun bronlar yo'q.")
    elif act == "pending":
        rows = db.execute(f"SELECT {COLS} FROM bookings WHERE status='pending' AND end>? ORDER BY start",
                          (now.isoformat(timespec="minutes"),)).fetchall()
        for r in rows:
            await bot.send_message(ADMIN_ID, f"👤 {r[2]}\n{line(r)}",
                                   reply_markup=kb(("✅ Tasdiqlash", f"ok:{r[0]}"), ("❌ Rad etish", f"no:{r[0]}")))
        if not rows:
            await bot.send_message(ADMIN_ID, "Kutilayotgan bronlar yo'q.")
    else:
        week = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        def stat(since):
            rows = db.execute("SELECT zone,start,end FROM bookings WHERE status='confirmed' AND start>=?", (since,)).fetchall()
            return len(rows), sum(price(*r) for r in rows)
        (tc, tr), (wc, wr) = stat(day), stat(week)
        pend = db.execute("SELECT COUNT(*) FROM bookings WHERE status='pending'").fetchone()[0]
        await bot.send_message(ADMIN_ID, f"📊 Statistika (tasdiqlangan)\nBugun: {tc} ta, {tr:,} so'm\n7 kun: {wc} ta, {wr:,} so'm\n⏳ Kutilayotgan: {pend} ta")


@dp.callback_query(F.data.regexp(r"^(ok|no):"))
async def decide_cb(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        return await c.answer("Ruxsat yo'q", show_alert=True)
    act, id_ = c.data.split(":")
    r = db.execute(f"SELECT {COLS} FROM bookings WHERE id=? AND {ACTIVE}", (id_,)).fetchone()
    if not r:
        return await c.answer("Bu bron endi faol emas", show_alert=True)
    new = "confirmed" if act == "ok" else "rejected"
    db.execute("UPDATE bookings SET status=? WHERE id=?", (new, id_))
    db.commit()
    r = r[:7] + (new,)
    await c.message.edit_text(f"👤 {r[2]}\n{line(r)}")
    await c.answer()
    if new == "confirmed":
        await bot.send_message(r[1], f"✅ Bronigiz tasdiqlandi!\n{line(r)}\n💰 {price(r[3], r[5], r[6]):,} so'm")
    else:
        await bot.send_message(r[1], f"❌ Afsus, bronigiz bekor qilindi (admin tomonidan).\n{line(r)}\nBoshqa vaqt yoki PC tanlab ko'ring.")


async def index(_):
    return web.FileResponse(os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html"))


async def zones(_):
    return web.json_response(ZONES)


async def busy(req):
    zone, date = req.query["zone"], req.query["date"]
    rows = db.execute(f"SELECT pc,start,end FROM bookings WHERE zone=? AND start LIKE ? AND {ACTIVE}",
                      (zone, date + "%")).fetchall()
    return web.json_response([{"pc": r[0], "start": r[1], "end": r[2]} for r in rows])


async def book(req):
    b = await req.json()
    user = check_init(b.get("initData", ""))
    if not user:
        return web.json_response({"error": "Ruxsat yo'q"}, status=403)
    zone, pc, hours = b["zone"], int(b["pc"]), int(b["hours"])
    if zone not in ZONES or pc not in ZONES[zone]["pcs"] or not 1 <= hours <= 12:
        return web.json_response({"error": "Noto'g'ri ma'lumot"}, status=400)
    start = datetime.fromisoformat(b["start"])
    if start < datetime.now():
        return web.json_response({"error": "O'tgan vaqtni tanlab bo'lmaydi"}, status=400)
    end = start + timedelta(hours=hours)
    clash = db.execute(f"SELECT 1 FROM bookings WHERE zone=? AND pc=? AND {ACTIVE} AND start<? AND end>?",
                       (zone, pc, end.isoformat(timespec="minutes"), start.isoformat(timespec="minutes"))).fetchone()
    if clash:
        return web.json_response({"error": "Bu kompyuter shu vaqtda band"}, status=409)
    name = user.get("first_name", "") + (" @" + user["username"] if user.get("username") else "")
    cur = db.execute("INSERT INTO bookings(user_id,name,zone,pc,start,end) VALUES(?,?,?,?,?,?)",
               (user["id"], name, zone, pc, start.isoformat(timespec="minutes"), end.isoformat(timespec="minutes")))
    db.commit()
    price = ZONES[zone]["price"] * hours
    when = f"{start:%d.%m %H:%M} – {end:%H:%M}"
    await bot.send_message(ADMIN_ID, f"🆕 Yangi bron\n👤 {name}\n🖥 {zone}, PC #{pc}\n🕒 {when}\n💰 {price:,} so'm",
                           reply_markup=kb(("✅ Tasdiqlash", f"ok:{cur.lastrowid}"), ("❌ Rad etish", f"no:{cur.lastrowid}")))
    await bot.send_message(user["id"], f"📨 Bron yuborildi, admin tasdiqlashini kuting.\n🖥 {zone}, PC #{pc}\n🕒 {when}\n💰 {price:,} so'm",
                           reply_markup=kb(("📋 Mening bronlarim", "my")))
    return web.json_response({"ok": True})


async def info(_):
    return web.json_response(INFO)


async def my(req):
    user = check_init((await req.json()).get("initData", ""))
    if not user:
        return web.json_response({"error": "Ruxsat yo'q"}, status=403)
    now = datetime.now().isoformat(timespec="minutes")
    rows = db.execute(f"SELECT {COLS} FROM bookings WHERE user_id=? ORDER BY start DESC LIMIT 30", (user["id"],)).fetchall()
    return web.json_response([{"id": r[0], "zone": r[3], "pc": r[4], "start": r[5], "end": r[6], "status": r[7],
                               "price": price(r[3], r[5], r[6]) if r[3] in ZONES else 0,
                               "can_cancel": r[7] in ("pending", "confirmed") and r[5] > now} for r in rows])


async def cancel(req):
    b = await req.json()
    user = check_init(b.get("initData", ""))
    if not user:
        return web.json_response({"error": "Ruxsat yo'q"}, status=403)
    r = db.execute(f"SELECT {COLS} FROM bookings WHERE id=? AND user_id=? AND {ACTIVE}", (b.get("id"), user["id"])).fetchone()
    if not r or r[5] <= datetime.now().isoformat(timespec="minutes"):
        return web.json_response({"error": "Bekor qilib bo'lmaydi"}, status=400)
    db.execute("UPDATE bookings SET status='cancelled' WHERE id=?", (r[0],))
    db.commit()
    await bot.send_message(ADMIN_ID, f"🚫 Mijoz bronni bekor qildi:\n{r[2]}\n{line(r[:7] + ('cancelled',))}")
    return web.json_response({"ok": True})


async def reminder_loop():
    while True:
        try:
            now = datetime.now()
            soon = (now + timedelta(minutes=REMIND_MIN)).isoformat(timespec="minutes")
            for id_, uid, zone, pc, st in db.execute(
                    "SELECT id,user_id,zone,pc,start FROM bookings WHERE status='confirmed' AND reminded=0 AND start<=?", (soon,)).fetchall():
                await bot.send_message(uid, f"⏰ Eslatma: bronigiz {REMIND_MIN} daqiqadan keyin boshlanadi.\n🖥 {zone}, PC #{pc}, {st[11:]}")
                db.execute("UPDATE bookings SET reminded=1 WHERE id=?", (id_,))
            for id_, uid, zone, pc in db.execute(
                    "SELECT id,user_id,zone,pc FROM bookings WHERE status='confirmed' AND started=0 AND start<=?",
                    (now.isoformat(timespec="minutes"),)).fetchall():
                await bot.send_message(uid, f"🎮 Vaqtingiz boshlandi! {zone}, PC #{pc}. Kutib turibmiz!")
                await bot.send_message(ADMIN_ID, f"🔔 Mijoz vaqti boshlandi: {zone}, PC #{pc}")
                db.execute("UPDATE bookings SET started=1 WHERE id=?", (id_,))
            db.commit()
        except Exception as e:
            print("reminder error:", e)
        await asyncio.sleep(30)


async def main():
    app = web.Application()
    app.add_routes([web.get("/", index), web.get("/api/zones", zones),
                    web.get("/api/busy", busy), web.post("/api/book", book),
                    web.post("/api/my", my), web.post("/api/cancel", cancel), web.get("/api/info", info)])
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", PORT).start()
    asyncio.create_task(reminder_loop())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
