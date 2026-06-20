# سكينة — Apple Wallet Passes

بطاقات أذكار رقمية لـ Apple Wallet.

## البطاقات

| الملف | العنوان |
|-------|---------|
| `dist/morning.pkpass` | أذكار الصباح |
| `dist/morning_alt.pkpass` | أذكار الصباح (بديل) |
| `dist/evening.pkpass` | أذكار المساء |
| `dist/sleep.pkpass` | أذكار النوم |
| `dist/waking.pkpass` | أذكار الاستيقاظ |
| `dist/after_prayer.pkpass` | أذكار بعد الصلاة |
| `dist/leaving.pkpass` | دعاء الخروج |
| `dist/rizq.pkpass` | دعاء الرزق |

## إعادة البناء

```bash
pip install pillow cryptography requests
python rebuild_all.py
```

الملفات الموقعة تظهر في `dist/`.

## إرسال للعميل

- أرسل ملفات `.pkpass` منفردة بالإيميل (وليس ZIP)
- على العميل **حذف البطاقات القديمة من Apple Wallet أولاً** قبل تثبيت الجديدة
- رقم البطاقة الداخلي (serial) يتغير في كل بناء — هذا يمنع الآيفون من عرض التصميم القديم المخزن في الكاش

## المتطلبات

- Apple Pass Type ID certificate (`.p12`) في `C:/Users/wenim/.kimi/wallet-passes/certs/`
- صور التصميم في `C:/Users/wenim/.kimi/wallet-passes/assets/client/previews/previews/`