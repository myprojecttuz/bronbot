"""Eski club.db (SQLite) ma'lumotlarini Supabase (Postgres) ga ko'chiradi.

Ishlatish:
    export DATABASE_URL="postgresql://..."      # Supabase connection string
    python migrate_to_supabase.py club.db

Bir necha marta ishga tushirsa ham xavfsiz: mavjud qatorlar o'tkazib yuboriladi.
"""
import os, sys, sqlite3

os.environ.setdefault("BOT_TOKEN", "123456:ABCdefGHIjklMNOpqrsTUVwxyz012345678")  # faqat import uchun
os.environ.setdefault("ADMIN_ID", "1")
os.environ.setdefault("WEBAPP_URL", "https://example.com")
if not os.getenv("DATABASE_URL"):
    sys.exit("DATABASE_URL o'rnatilmagan")

import bot  # jadvallarni Supabase'da yaratadi

src = sqlite3.connect(sys.argv[1] if len(sys.argv) > 1 else "club.db")
for table in ("users", "prices", "settings", "support", "bookings"):
    cols = [r[1] for r in src.execute(f"PRAGMA table_info({table})")]
    if not cols:
        continue
    rows = src.execute(f"SELECT {','.join(cols)} FROM {table}").fetchall()
    sql = f"INSERT INTO {table}({','.join(cols)}) VALUES({','.join('?' * len(cols))}) ON CONFLICT DO NOTHING"
    for r in rows:
        bot.db.execute(sql, r)
    print(f"{table}: {len(rows)} qator ko'chirildi")
bot.db.execute("SELECT setval(pg_get_serial_sequence('bookings','id'), COALESCE((SELECT MAX(id) FROM bookings), 0) + 1, false)")
print("Tayyor.")
