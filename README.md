# 📦 Sklad Bot — Ombor Boshqaruv Telegram Boti

Telegram orqali omborni boshqarish uchun bot. 2D matritsa (uzunlik × kenglik) ko'rinishida zaxirani saqlaydi.

## 📁 Loyiha strukturasi

```
sklad/
├── api/
│   └── webhook.py          # Vercel serverless webhook handler
├── bot/
│   ├── __init__.py
│   ├── main.py              # Bot dispatcher va handlerlar
│   ├── db.py                # SQLite ma'lumotlar bazasi
│   ├── parser.py            # Erkin matn tahlilchisi
│   ├── image.py             # PNG matritsa rasmini yaratish
│   └── states.py            # Chat holat mashinasi
├── tests/
│   ├── __init__.py
│   └── test_parser.py       # Parser testlari
├── run_local.py             # Lokal ishga tushirish (polling)
├── requirements.txt
├── vercel.json              # Vercel konfiguratsiyasi
└── README.md
```

## 🚀 Lokal ishga tushirish

### 1. Python muhitini tayyorlash

```bash
# Virtual muhit yaratish (ixtiyoriy)
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# Kutubxonalarni o'rnatish
pip install -r requirements.txt
```

### 2. Bot tokenini sozlash

Telegram [@BotFather](https://t.me/BotFather) dan yangi bot yarating va tokenni oling.

```bash
# Windows
set BOT_TOKEN=your_bot_token_here

# Linux/Mac
export BOT_TOKEN=your_bot_token_here
```

### 3. Botni ishga tushirish (Polling rejimi)

```bash
python run_local.py
```

Bot polling rejimida ishga tushadi — webhook shart emas.
Telegramdan botga `/start` yuboring.

### 4. Ngrok bilan webhook rejimi (ixtiyoriy)

Agar webhook rejimida sinash kerak bo'lsa:

```bash
# Ngrokni o'rnating: https://ngrok.com/download
ngrok http 8443

# Chiqgan URL bilan webhookni o'rnating:
# https://api.telegram.org/bot<TOKEN>/setWebhook?url=<NGROK_URL>/api/webhook
```

## 🧪 Testlarni ishga tushirish

```bash
pytest tests/test_parser.py -v
```

## ☁️ Vercel'ga deploy qilish

### 1. Vercel CLI o'rnatish

```bash
npm install -g vercel
```

### 2. Loyihani deploy qilish

```bash
cd sklad
vercel --prod
```

### 3. Environment variable qo'shish

Vercel dashboardida:
- Settings → Environment Variables
- `BOT_TOKEN` = `your_bot_token_here`

### 4. Webhookni o'rnatish

Brauzerda quyidagi URLni oching:

```
https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook?url=https://<YOUR_VERCEL_DOMAIN>/api/webhook
```

Javob `{"ok": true}` bo'lishi kerak.

## 📝 Foydalanish misollari

### Kirim (qo'shish)
```
/kirim
5 680
3 740
10 400 50
```

Yoki bitta xabarda:
```
kirim
5ta 680
3 600x80
10 400 50
```

### Chiqim (ayirish)
```
/chiqim
2 680
1 740
```

### Holat (ombor rasmi)
```
/holat
```

### Qo'llab-quvvatlanadigan formatlar

| Format | Natija |
|--------|--------|
| `5 ta 680` | 5 dona 600×80 |
| `5ta 680` | 5 dona 600×80 |
| `5 шт 680` | 5 dona 600×80 |
| `+5 680` | 5 dona 600×80 |
| `680 5` | 5 dona 600×80 |
| `5 600x80` | 5 dona 600×80 |
| `5 600 80` | 5 dona 600×80 |
| `600x80 5` | 5 dona 600×80 |
| `5pcs 670` | 5 dona 600×70 |
| `5 дана 740` | 5 dona 700×40 |
| `5, 680` | 5 dona 600×80 |
| `5;680` | 5 dona 600×80 |
| `5:680` | 5 dona 600×80 |

### O'lcham kodlash qoidasi

Bitta raqam berilganda:
- `680` → uzunlik = 600, kenglik = 80
- `740` → uzunlik = 700, kenglik = 40
- `350` → uzunlik = 300, kenglik = 50

### Ruxsat etilgan o'lchamlar

- **Uzunlik:** 200, 300, 400, 500, 600, 700
- **Kenglik:** 0, 10, 20, 30, 40, 50, 60, 70, 80, 90

## ⚠️ Vercel'da SQLite cheklovlari

Vercel serverless muhitda SQLite fayli `/tmp/sklad.db` da saqlanadi.
Bu ma'lumotlar faqat bitta serverless konteyner ichida saqlanadi va konteyner o'chirilganda yo'qoladi.

**Doimiy saqlash uchun quyidagilardan foydalaning:**
- [Turso](https://turso.tech/) — SQLite-compat, serverless-friendly
- [Supabase](https://supabase.com/) — PostgreSQL
- [Neon](https://neon.tech/) — Serverless PostgreSQL
- [PlanetScale](https://planetscale.com/) — MySQL

`bot/db.py` dagi `aiosqlite` chaqiruvlarini tegishli async driver bilan almashtiring.

## 📄 Litsenziya

MIT
