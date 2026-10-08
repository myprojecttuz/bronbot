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

Vaqt har doim **Toshkent (UTC+5)** bo'yicha ishlaydi: server va mijoz telefoni qaysi soat mintaqasida bo'lishidan qat'i nazar.

## Buyruqlar
- Mijoz: `/start` (bron qilish), `/my` (bronlarim va bekor qilish)
- Admin: `/admin` (bugungi bronlar, kutilayotganlar, statistika). Yangi bron kelganda ✅/❌ tugmalari chiqadi.

Bron holatlari: kutilmoqda → tasdiqlangan / rad etilgan / bekor qilingan.
Eslatmalar faqat tasdiqlangan bronlarga boradi. Rad etilgan va bekor qilingan bronlar PCni bo'shatadi.
Eski `club.db` bo'lsa, `status` ustuni avtomatik qo'shiladi.

## Klub ma'lumotlari ("Aloqa" bo'limi uchun, ixtiyoriy)
Railway Variables ga qo'shing: `CLUB_ADDRESS`, `CLUB_PHONE`, `CLUB_HOURS`, `ADMIN_USERNAME` (@siz).

Yoki botda admin sifatida Mini App → **Admin → Aloqa** bo'limidan to'ldiring: manzil, ish vaqti, **bir nechta admin** (ism, telefon, @username) va xarita koordinatasi
(`41.311081, 69.240562` yoki Google xaritadagi to'liq havola; `maps.app.goo.gl` qisqa havolasi ishlamaydi). Mijozlar buni **Aloqa** bo'limida (xarita, qo'ng'iroq va Telegram tugmalari bilan) va `/support` da ko'radi.

## Supabase (doimiy baza)
Railway'da `club.db` har deployda o'chib ketishi mumkin. Supabase ulansa, bronlar va mijozlar doimiy saqlanadi.
1. Supabase → **Project Settings → Database → Connection string** → **Session pooler** ni tanlang va nusxalang
   (Railway IPv6 ni qo'llamaydi, shuning uchun oddiy "Direct connection" ishlamasligi mumkin). Parolni `[YOUR-PASSWORD]` o'rniga qo'ying.
2. Railway **Variables** ga `DATABASE_URL` nomi bilan qo'shing. Bot qayta ishga tushganda jadvallarni o'zi yaratadi.
   Loglarda `Baza: Supabase (Postgres)` chiqishi kerak. `DATABASE_URL` bo'lmasa, avvalgidek SQLite ishlaydi.
3. Eski ma'lumotlarni ko'chirish (ixtiyoriy, bir marta): `DATABASE_URL="..." python migrate_to_supabase.py club.db`
Jadvallarda Row Level Security yoqiladi, shuning uchun telefon raqamlarga Supabase ochiq API orqali kirib bo'lmaydi (bot to'g'ridan-to'g'ri ulanadi).

## Xabarlar
Bron qilinganda, tasdiqlanganda, rad etilganda mijozga chiroyli kartochka yuboriladi. Tasdiqlangan bron boshlanishigacha **har soatda** "N soat qoldi" xabari keladi
(oxirgi `HOURLY_MAX_H` = 24 soat ichida; kechasi 23:00–08:00 ovozsiz), keyin 30 daqiqa oldin eslatma va boshlanish vaqtida xabar.

## /start GIF
`/start` xabari `welcome.gif` animatsiyasi bilan boradi (matn GIF ostida, pastida tugmalar). Fayl birinchi yuborishda Telegramga yuklanadi, keyin `file_id` saqlanadi.
Boshqa GIF xohlasangiz: `welcome.gif` ni almashtiring yoki Railway Variables ga `WELCOME_GIF` (GIF havolasi yoki file_id) qo'shing.
`python make_welcome_gif.py logo.png welcome.gif` bilan logotipdan yangi GIF yasash mumkin. GIF yuborilmasa, oddiy matnli xabar boradi.

## Band holati xaritada
Xaritada kompyuter **hozir** yoki **keyingi 24 soatda** bron qilingan bo'lsa «band» ko'rinadi (kutilayotgan bron sariq). Keyingi vaqtga qilingan bronda kompyuter ustida 🕒 belgisi chiqadi.
Belgi bor kompyuterni boshqa bo'sh vaqt uchun baribir tanlash mumkin: ilova 2-qadamda vaqt to'qnashuvini tekshiradi. Zonadagi hamma kompyuter band bo'lsa, zona tugmasida «Band» yoziladi.

## Aksiyalar va reklama
Admin sifatida Mini App → **Admin → Aksiya** bo'limidan aksiya qo'shasiz: sarlavha, matn, rasm havolasi (ixtiyoriy), tugma (Bron qilish / Paketlar / Zonalar / Aloqa / havola), tugash sanasi.
- **Ilovada:** mijoz kirganda popup chiqadi (har aksiya 3 soatda bir marta), chekkadan sirpanib chiqadigan xabar vaqti-vaqti bilan eslatadi, yuqoridagi 🎁 belgi doim ochiq turadi.
- **Botda:** «Botda hamma mijozga yuborish» belgilansa, aksiya 10:00–21:00 oralig'ida (`PUSH_FROM`, `PUSH_TO`) hamma ro'yxatdan o'tgan mijozga yuboriladi. «Takrorlash» ga kun kiritilsa (masalan 3), shuncha kunda qayta yuboriladi, 0 bo'lsa bir marta. «📣 Hoziroq yuborish» tugmasi darrov yuboradi.
- Mijoz botda **🎁 Aksiyalar** tugmasi yoki `/promo` orqali faol aksiyalarni istalgan vaqt ko'radi.

## Ishonchlilik
- `/start` hech qachon jim qolmaydi: avval to'liq menyu, tugma rad etilsa faqat «🎮 Bron qilish» tugmasi, u ham bo'lmasa matn va havola yuboriladi.
- `WEBAPP_URL` avtomatik to'g'rilanadi (`https://` qo'shiladi, bo'sh joy va qo'shtirnoq olib tashlanadi). To'g'rilangan bo'lsa, admin ogohlantiriladi.
- Kutilmagan xato bo'lsa, mijozga xabar beriladi, admin esa (10 daqiqada bir marta) xato matnini oladi.
- Supabase'ga ulanib bo'lmasa, bot o'chib qolmaydi: vaqtincha SQLite bilan ishlaydi va adminga ogohlantirish yuboradi. `DATABASE_URL` ni to'g'rilab qayta deploy qiling.

## Versiyani tekshirish
Deploydan keyin `https://sizning-domen.uz/api/version` yoki botda `/status` ni oching. Hozirgi versiya: **v15**. Eski versiya chiqsa, yangi deploy ishga tushmagan: Railway → Deployments → Logs ni tekshiring.
Kod Python 3.10+ da ishlaydi.

## Xususiyatlar va guruh bron
`bot.py` dagi `ZONES[...]["specs"]` ro'yxatida har zona kompyuterlarining xususiyatlari turadi (Narxlar bo'limida va tanlashda ko'rinadi). Ularni haqiqiyiga almashtiring.
Mijoz bir bronda 30 tagacha kompyuter va 30 daqiqadan 24 soatgacha istalgan vaqtni tanlay oladi.

## Kompyuter xususiyatlari
`bot.py` boshidagi `ZONES` ichida har zona uchun `specs` bor (protsessor, videokarta, RAM, monitor, jihozlar). Ular **namuna**, haqiqiy ma'lumotga almashtiring.
