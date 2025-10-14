from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    # يمكن تغيير الرسالة
    return "Hello! I am alive!"

def run():
    # يبدأ تشغيل خادم الويب
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    # تشغيل الخادم في موضوع (Thread) منفصل
    t = Thread(target=run)
    t.start()
