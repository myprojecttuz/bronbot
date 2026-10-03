# Game Club bron boti

## Ishga tushirish
1. @BotFather orqali bot yarating, tokenni oling.
2. Admin Telegram ID ni @userinfobot orqali bilib oling.
3. O'rnatish:
   ```
   pip install aiogram aiohttp
   ```
4. Sozlash va ishga tushirish:
   ```
   export BOT_TOKEN="..."
   export ADMIN_ID="123456789"
   export WEBAPP_URL="https://sizning-domen.uz"
   python bot.py
   ```
5. Web app HTTPS bo'lishi shart. Sinash uchun `ngrok http 8080` yoki `cloudflared tunnel --url http://localhost:8080`,
   chiqqan https manzilni WEBAPP_URL ga yozing.

## Sozlamalar (bot.py boshida)
- `ZONES` — zonalar, narxlar, kompyuterlar soni
- `REMIND_MIN` — bron boshlanishidan necha daqiqa oldin eslatish

Vaqt server soat mintaqasi bo'yicha ishlaydi (`export TZ=Asia/Tashkent`).

## Buyruqlar
- Mijoz: `/start` (bron qilish), `/my` (bronlarim va bekor qilish)
- Admin: `/admin` (bugungi bronlar, kutilayotganlar, statistika). Yangi bron kelganda ✅/❌ tugmalari chiqadi.

Bron holatlari: kutilmoqda → tasdiqlangan / rad etilgan / bekor qilingan.
Eslatmalar faqat tasdiqlangan bronlarga boradi. Rad etilgan va bekor qilingan bronlar PCni bo'shatadi.
Eski `club.db` bo'lsa, `status` ustuni avtomatik qo'shiladi.

## Klub ma'lumotlari ("Aloqa" bo'limi uchun, ixtiyoriy)
Railway Variables ga qo'shing: `CLUB_ADDRESS`, `CLUB_PHONE`, `CLUB_HOURS`, `ADMIN_USERNAME` (@siz).
