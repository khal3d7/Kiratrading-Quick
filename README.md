# Crypto Trading Intelligence System

نظام تداول ذكي مكتوب بـ Python لتحليل العملات الرقمية الكبيرة وتوليد صفقات بناءً على استراتيجيات حقيقية مع إدارة رأس مال صارمة، يتواصل مع المستخدم عبر تليجرام (قناتين منفصلتين + بوت تحكم تفاعلي).

## المزايا

- 📡 جلب بيانات لحظية من Binance عبر `ccxt` (أسعار، شموع متعددة الأطر، كتاب الأوامر، السيولة، Funding Rate).
- 🧮 تحليل فني شامل: RSI, MACD, EMA, ADX, Bollinger Bands, ATR, OBV, MFI, Ichimoku, دعم/مقاومة تلقائي، Pivot Points، Fibonacci.
- 🧭 5 استراتيجيات حقيقية: Trend Following, Breakout, Mean Reversion, Ichimoku, Smart Money Concept.
- 🛡 إدارة رأس مال صارمة: 2% مخاطرة كحد أقصى، R/R لا يقل عن 1:2، TP متعدد المراحل، نقل SL إلى التعادل.
- 🤖 تنسيق التقارير عبر LLM (OpenAI/Anthropic) مع منع اختراع البيانات.
- 📢 قناتان: تحليل يومي + إشعارات الصفقات.
- 🎛 بوت تليجرام تفاعلي للمسؤولين (صفقات جديدة/جارية/منتهية، إحصائيات، سجل، إعدادات).
- 🗓 جدولة تلقائية: تحاليل صباحية ومسائية، فحص استراتيجيات كل 5 دقائق، مراقبة الصفقات كل دقيقة، تقارير أسبوعية وشهرية.
- 💾 تخزين كامل (SQLite للتطوير / PostgreSQL للإنتاج) عبر SQLAlchemy.

## التشغيل المحلي

```bash
cd trading_system
cp .env.example .env
# املأ المتغيرات في .env
pip install -r requirements.txt
python main.py
```

## النشر على Railway

1. ادفع المشروع إلى GitHub.
2. أنشئ مشروعاً جديداً على Railway واربطه بالـ repo.
3. أضف متغيرات البيئة من `.env.example`.
4. (اختياري) أضف خدمة PostgreSQL وضع `DATABASE_URL` تلقائياً.
5. الخدمة ستعمل تلقائياً عبر `python main.py` (موجود في `Procfile` و `railway.json`).

## المتغيرات المطلوبة

انظر `.env.example`. أهمها:
- `TELEGRAM_BOT_TOKEN` — توكن البوت من BotFather.
- `DAILY_ANALYSIS_CHANNEL_ID` — معرف قناة التحليل (يبدأ بـ `-100`).
- `TRADES_CHANNEL_ID` — معرف قناة الصفقات.
- `ADMIN_USER_IDS` — قائمة معرفات تلجرام للمسؤولين (مفصولة بفواصل).
- `OPENAI_API_KEY` أو `ANTHROPIC_API_KEY` للتنسيق الذكي.
- `DATABASE_URL` — رابط قاعدة البيانات.

## هيكل المشروع

```
trading_system/
├── config/          إعدادات النظام والقائمة المعتمدة
├── data/            جلب بيانات الأسعار والسيولة
├── analysis/        المؤشرات + الدعم/المقاومة + هيكل السوق
├── strategies/      الاستراتيجيات الخمس
├── risk/            إدارة المخاطر والحجم
├── ai_formatter/    تنسيق التقارير عبر LLM
├── telegram_bot/    البوت + ناشر القنوات + لوحة التحكم
├── scheduler/       جدولة المهام التلقائية
├── reports/         التقارير الأسبوعية والشهرية
├── database/        النماذج والاتصال
├── utils/           أدوات مساعدة (logger)
├── main.py          نقطة الدخول
├── requirements.txt
├── Dockerfile
├── Procfile
├── railway.json
└── nixpacks.toml
```

## ملاحظات مهمة

- النظام في الوضع الحالي **يحاكي الصفقات (Paper Trading)**: يحفظها في قاعدة البيانات ويتابع SL/TP من السعر الحقيقي، لكنه لا يرسل أوامر تنفيذ فعلية إلى Binance. لتفعيل التداول الفعلي يجب إضافة وحدة `executor` تستدعي `exchange.create_order()` بحذر شديد.
- الذكاء الاصطناعي **لا يولّد توصيات**؛ يقتصر دوره على صياغة وتنسيق البيانات الفعلية.
- العملات الميمية مستبعدة عمداً من القائمة المعتمدة.
