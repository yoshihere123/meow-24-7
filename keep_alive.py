# محتوى ملف keep_alive.py

from flask import Flask
from threading import Thread
import os

app = Flask('')

@app.route('/')
def home():
    # هذا المسار يستخدمه Render لفحص حالة الخدمة (Health Check)
    return "Bot is alive!"

def run():
    # استخدام المنفذ الذي يحدده Render (عادة 8080)
    port = int(os.environ.get('PORT', 8080))
    # تشغيل الخادم على جميع العناوين
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    # تشغيل خادم Flask في خيط منفصل (Background thread)
    t = Thread(target=run)
    t.start()
