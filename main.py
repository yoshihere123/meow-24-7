import os
import sys
import json
import time
import requests
import websocket
import random
from keep_alive import keep_alive 

# --- المتغيرات الثابتة ---
GUILD_ID = 961795359544328203
CHANNEL_ID = 1428594267189678080

# --- 1. جلب التوكن والتحقق منه وتعريف متغيرات المستخدم ---
usertoken = os.getenv("TOKEN")
if not usertoken:
    print("[ERROR] Please add a token inside Secrets.")
    sys.exit()

headers = {"Authorization": usertoken, "Content-Type": "application/json"}

# التحقق من صلاحية التوكن
validate = requests.get('https://canary.discordapp.com/api/v9/users/@me', headers=headers)
if validate.status_code != 200:
    print("[ERROR] Your token might be invalid. Please check it again.")
    sys.exit()

# جلب معلومات المستخدم وتعريف المتغيرات المطلوبة في run_joiner
userinfo = requests.get('https://canary.discordapp.com/api/v9/users/@me', headers=headers).json()
username = userinfo["username"]
discriminator = userinfo["discriminator"]
userid = userinfo["id"]

# --- دالة البقاء والتحديث المستمر ---
def maintain_session(token):
    
    statuses = ["online", "dnd", "idle"]
    boolean_choices = [True, False] # لكتم/فتح المايك والسماعة
    
    # *** الإصلاح هنا: نقل التعريفات خارج حلقة while True ***
    # التحديث العشوائي للحالة يتم بين 10 إلى 15 دقيقة (600-900 ثانية)
    STATUS_UPDATE_INTERVAL = random.randint(600, 900) 
    last_update_time = time.time()
    # *******************************************************
    
    while True:
        # 1. إنشاء اتصال WebSocket جديد
        ws = websocket.WebSocket()
        try:
            ws.connect('wss://gateway.discord.gg/?v=9&encoding=json')
        except Exception as e:
            print(f"[ERROR] Failed to connect WebSocket: {e}. Retrying in 10s...")
            time.sleep(10)
            continue

        # 2. استقبال رسالة Hello وحساب Heartbeat
        try:
            start = json.loads(ws.recv())
            heartbeat_interval_ms = start['d']['heartbeat_interval'] 
            heartbeat_interval_s = heartbeat_interval_ms / 1000 
        except Exception:
            print("[ERROR] Failed to receive Hello or calculate Heartbeat. Restarting connection.")
            continue
            
        # 3. اختيار الحالة الأولية
        current_status = random.choice(statuses)
        current_mute = random.choice(boolean_choices)
        current_deaf = random.choice(boolean_choices)
        
        print(f"\n--- New Session Started ---")
        print(f"Initial Status: {current_status} | Mute: {current_mute} | Deaf: {current_deaf}")

        # 4. إرسال Identify (المصادقة وتعيين الحالة)
        auth = {
            "op": 2, "d": {"token": token, "properties": {"$os": "Windows 10", "$browser": "Google Chrome", "$device": "Windows"},
                           "presence": {"status": current_status, "afk": False, "activities": []}}}
        ws.send(json.dumps(auth))
        
        # 5. إرسال Voice State Update (الانضمام الصوتي)
        vc = {
            "op": 4, "d": {"guild_id": GUILD_ID, "channel_id": CHANNEL_ID, 
                           "self_mute": current_mute, "self_deaf": current_deaf}}
        ws.send(json.dumps(vc))

        # 6. حلقة Heartbeat والبقاء في القناة
        while ws.connected:
            try:
                # 6.1. إرسال نبضة القلب (Heartbeat)
                ws.send(json.dumps({"op": 1, "d": None}))
                
                # 6.2. التحقق من وقت التحديث العشوائي
                if time.time() - last_update_time >= STATUS_UPDATE_INTERVAL:
                    
                    # اختيار حالات جديدة عشوائياً
                    current_status = random.choice(statuses)
                    current_mute = random.choice(boolean_choices)
                    current_deaf = random.choice(boolean_choices)
                    
                    print(f"[UPDATE] Changing state. New Status: {current_status} | Mute: {current_mute} | Deaf: {current_deaf}")

                    # إرسال Voice State Update لتحديث المايك والسماعة
                    vc_update = {
                        "op": 4, "d": {"guild_id": GUILD_ID, "channel_id": CHANNEL_ID, 
                                       "self_mute": current_mute, "self_deaf": current_deaf}}
                    ws.send(json.dumps(vc_update))
                    
                    # إرسال تحديث الحضور لتغيير الحالة الشخصية
                    presence_update = {
                        "op": 3, "d": {"status": current_status, "afk": False, "activities": []}}
                    ws.send(json.dumps(presence_update))

                    # إعادة تعيين مؤقت التحديث وفترة الانتظار العشوائية الجديدة
                    # يتم التعيين هنا فقط، مما يمنع التصفير عند إعادة الاتصال
                    last_update_time = time.time()
                    STATUS_UPDATE_INTERVAL = random.randint(600, 900) 
                    print(f"Next random update scheduled in {STATUS_UPDATE_INTERVAL} seconds.")

                # 6.3. الانتظار حتى الموعد التالي لـ Heartbeat
                time.sleep(heartbeat_interval_s)
                
                # 6.4. محاولة استقبال رسائل (لتجنب تراكمها)
                ws.recv_ex() 
                
            except websocket.WebSocketConnectionClosedException:
                print("\n[INFO] WebSocket connection closed by server. Attempting immediate reconnect...")
                break # الخروج وإعادة التشغيل
            except Exception as e:
                print(f"\n[ERROR] An error occurred: {e}. Attempting immediate reconnect...")
                break # الخروج وإعادة التشغيل

# --- حلقة التشغيل الرئيسية ---
def run_joiner():
    os.system("clear")
    print(f"Logged in as {username}#{discriminator} ({userid}).")
    # نبدأ جلسة البقاء المستمر
    maintain_session(usertoken)

keep_alive()
run_joiner()
