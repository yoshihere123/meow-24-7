# محتوى ملف keep_alive.py (النهائي والمبسط)

from flask import Flask

# لا نحتاج لاستيراد threading أو os بعد الآن

app = Flask('')

@app.route('/')
def home():
    # هذا المسار يستخدمه Gunicorn/Render لفحص حالة الخدمة (Health Check)
    return "Bot is alive!"

# تم حذف دالتي run() و keep_alive() بالكامل
# لأن Gunicorn سيتولى تشغيل تطبيق Flask مباشرة (عبر أمر البدء)
