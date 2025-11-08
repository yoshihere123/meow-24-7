import os
import sys
import json
import time
import requests
import websocket
import random # تم إضافة مكتبة العشوائية
from keep_alive import keep_alive 

# --- المتغيرات الثابتة (لا تتغير) ---
GUILD_ID = 961795359544328203
CHANNEL_ID = 1428594267189678080
# سيتم تعيين 'status' و 'SELF_MUTE' و 'SELF_DEAF' بشكل عشوائي في دالة run_joiner

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

userinfo = requests.get('https://canary.discordapp.com/api/v9/users/@me', headers=headers).json()
username = userinfo["username"]
discriminator = userinfo["discriminator"]
userid = userinfo["id"]

# --- دالة الانضمام المعدلة لاستقبال خيارات المايك والسماعة والحالة ---
def joiner(token, status_choice, self_mute_choice, self_deaf_choice):
    ws = websocket.WebSocket()
    ws.connect('wss://gateway.discord.gg/?v=9&encoding=json')
    start = json.loads(ws.recv())
    heartbeat = start['d']['heartbeat_interval']
    
    # حمولة المصادقة وتعيين الحالة (بدون نشاط لعب)
    auth = {
        "op": 2,
        "d": {
            "token": token,
            "properties": {"$os": "Windows 10", "$browser": "Google Chrome", "$device": "Windows"},
            "presence": {"status": status_choice, "afk": False, "activities": []} # تم إزالة النشاط
        },
        "s": None,
        "t": None
    }
    
    # حمولة الانضمام الصوتي وتعيين المايك والسماعة
    vc = {
        "op": 4,
        "d": {
            "guild_id": GUILD_ID,
            "channel_id": CHANNEL_ID,
            "self_mute": self_mute_choice, # القيمة العشوائية
            "self_deaf": self_deaf_choice  # القيمة العشوائية
        }
    }
    
    ws.send(json.dumps(auth))
    ws.send(json.dumps(vc))
    time.sleep(heartbeat / 1000)
    ws.send(json.dumps({"op": 1, "d": None}))

# --- حلقة التشغيل الرئيسية المعدلة للعشوائية ---
def run_joiner():
    os.system("clear")
    print(f"Logged in as {username}#{discriminator} ({userid}).")
    
    # الخيارات المتاحة
    statuses = ["online", "dnd", "idle"]
    boolean_choices = [True, False] # لكتم/فتح المايك والسماعة

    while True:
        # 1. اختيار عشوائي للحالة والمايك والسماعة
        current_status = random.choice(statuses)
        current_mute = random.choice(boolean_choices)
        current_deaf = random.choice(boolean_choices)
        
        # 2. طباعة الخيارات المختارة
        print(f"\n--- Starting join attempt ---")
        print(f"Status: {current_status}")
        print(f"Self Mute: {current_mute} | Self Deaf: {current_deaf}")
        
        # 3. محاولة الانضمام بالخيارات العشوائية
        joiner(usertoken, current_status, current_mute, current_deaf)
        
        # 4. اختيار عشوائي لوقت الانتظار الطويل
        # الانتظار بين 5 إلى 15 دقيقة (300 إلى 900 ثانية)
        wait_time = random.randint(300, 900) 
        print(f"Successfully connected. Waiting for {wait_time} seconds before next check/reconnect...")
        time.sleep(wait_time)

keep_alive()
run_joiner()
