# SAFAR bot yangilanishi

Hudud tanlash yo‘q. To‘rtta haydovchi guruhi avvalgidek navbat bilan ishlaydi.
Brend arizasi avvalgi guruhga tushadi. Operator arizasida Tayyor, Izoh,
Jarayonda, Chala rasm, Boshqa park, ZIP va tasdiqlanadigan O‘chirish mavjud.

Mahalliy OCR uchun `pip install -r requirements.txt -r requirements-ocr.txt`
va `.env` ichida `DOCUMENT_OCR_BACKEND=rapid`, `DOCUMENT_AI_ENABLED=1` qo‘ying.
OCR tashqi AI xizmatiga rasm yubormaydi; natija operator tekshiruvidan o‘tadi.
Kutubxona o‘rnatilmagan yoki o‘qish amalga oshmagan holatda rasmlar saqlanadi,
operatorga qo‘lda tekshirish xabari chiqadi.

Chala rasm va Boshqa park guruhlarini botni administrator qilib qo‘shgach,
`.env` ichida `INCOMPLETE_GROUP=-...` va `OTHER_PARK_GROUP=-...` qo‘ying.
Guruhlar sozlanmagan paytda tugma arizani joyidan ko‘chirmaydi.
`ARCHIVE_GROUP` ham to‘g‘ri guruhga ulangan bo‘lishi kerak. Ko‘chirish va
o‘chirish uchun botda xabar o‘chirish huquqi zarur.

Ishlayotgan serverdagi `.env`, `bot_persistence.pkl`, shablon rasmlari va
systemd konfiguratsiyasini saqlang. `git pull`dan oldin `git status --short`
bilan mahalliy o‘zgarishlarni tekshiring va holat faylidan zaxira nusxa oling.
Repo avvaldan kuzatib kelgan `bot_persistence.pkl`ga tegilmadi; serverdagi
haqiqiy holat faylini o‘chirmang. ZIP operator guruhida Telegram fayli sifatida
yuboriladi; operator uni bir bosib qurilmasiga yuklab oladi. Bot Telegram orqali
kompyuterning Download papkasiga avtomatik yozolmaydi.
