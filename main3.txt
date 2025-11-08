import os
import sys
import json
import time
import requests
import websocket
import random

# --- المتغيرات الثابتة ---
GUILD_ID = 961795359544328203
CHANNEL_ID = 1428594267189678080

# --- متغيرات الجلسة (لRESUME) ---
SESSION_ID = None  
LAST_SEQUENCE = None 
HEARTBEAT_INTERVAL_S = 40.0 

# --- 1. جلب التوكن والتحقق منه وتعريف متغيرات المستخدم ---
usertoken = os.getenv("TOKEN")
if not usertoken:
    print("[ERROR] Please add a token inside Secrets.", flush=True) 
    sys.exit()

headers = {"Authorization": usertoken, "Content-Type": "application/json"}

validate = requests.get('https://canary.discordapp.com/api/v9/users/@me', headers=headers)
if validate.status_code != 200:
    print("[ERROR] Your token might be invalid. Please check it again.", flush=True) 
    sys.exit()

userinfo = requests.get('https://canary.discordapp.com/api/v9/users/@me', headers=headers).json()
username = userinfo["username"]
discriminator = userinfo["discriminator"]
userid = userinfo["id"]

# --- المتغيرات العامة (العدادات المحفوظة) ---
STATUS_UPDATE_INTERVAL = random.randint(300, 900) 
last_update_time = time.time()
# ----------------------------------------------------

# --- دالة إرسال واستقبال الرسائل (مخصصة لـ Resume) ---
def receive_and_process(ws):
    global LAST_SEQUENCE, SESSION_ID
    
    try:
        ws.settimeout(HEARTBEAT_INTERVAL_S / 2) 
        response = json.loads(ws.recv())
        
        # 1. تحديث Sequence Number
        if 's' in response and response['s'] is not None:
            LAST_SEQUENCE = response['s']
            
        # 2. حفظ Session ID عند أول اتصال (Identify)
        if response.get('op') == 0 and response.get('t') == 'READY':
            SESSION_ID = response['d']['session_id']
            print(f"[READY] Session ID saved: {SESSION_ID}", flush=True)
            
        # 3. إرسال Voice State Update (انضمام) عند أي حدث مهم (READY أو RESUMED)
        if response.get('op') == 0 and response.get('t') in ['READY', 'RESUMED']:
            vc = {
                "op": 4, "d": {"guild_id": GUILD_ID, "channel_id": CHANNEL_ID, 
                               "self_mute": random.choice([True, False]), "self_deaf": random.choice([True, False])}}
            ws.send(json.dumps(vc))

        # 4. إذا أرسل Discord طلب Heartbeat
        elif response.get('op') == 1:
            ws.send(json.dumps({"op": 1, "d": LAST_SEQUENCE}))
            
    except websocket.WebSocketTimeoutException:
        return True 
    except websocket.WebSocketConnectionClosedException:
        raise 
    except Exception as e:
        print(f"[WARN] Error receiving/processing message: {e}", flush=True)
        return True 

# --- دالة البقاء والتحديث المستمر ---
def maintain_session(token):
    
    global STATUS_UPDATE_INTERVAL, last_update_time, SESSION_ID, LAST_SEQUENCE, HEARTBEAT_INTERVAL_S
    
    statuses = ["online", "dnd", "idle"]
    boolean_choices = [True, False] 
    
    while True:
        ws = websocket.WebSocket()
        
        # 1. محاولة الاتصال
        try:
            ws.settimeout(10) 
            ws.connect('wss://gateway.discord.gg/?v=9&encoding=json')
        except Exception as e:
            print(f"[ERROR] Failed to connect WebSocket: {e}. Retrying in 10s...", flush=True) 
            time.sleep(10)
            continue

        # 2. استقبال Hello
        try:
            start = json.loads(ws.recv())
            HEARTBEAT_INTERVAL_S = start['d']['heartbeat_interval'] / 1000 
        except Exception:
            print("[ERROR] Failed to receive Hello. Restarting connection.", flush=True) 
            continue
            
        # 3. محاولة الاستئناف (Resume)
        if SESSION_ID and LAST_SEQUENCE:
            resume = {
                "op": 6, "d": {"token": token, "session_id": SESSION_ID, "seq": LAST_SEQUENCE}}
            ws.send(json.dumps(resume))
            print(f"[RESUME] Attempting to resume session {SESSION_ID}...", flush=True)
            
            # انتظر رسالة RESUMED لتأكيد العودة
            try:
                receive_and_process(ws) 
            except:
                print("[RESUME FAIL] Failed to confirm resume. Re-identifying.", flush=True)
                SESSION_ID = None
                continue 
        
        # 4. المصادقة (Identify) - يتم تنفيذها فقط إذا فشل Resume أو كانت أول محاولة
        if not SESSION_ID:
            current_status = random.choice(statuses)
            current_mute = random.choice(boolean_choices)
            current_deaf = random.choice(boolean_choices)
            
            print(f"\n--- New Session (Identify) Started ---", flush=True) 
            
            auth = {
                "op": 2, "d": {"token": token, "properties": {"$os": "Windows 10", "$browser": "Google Chrome", "$device": "Windows"},
                               "presence": {"status": current_status, "afk": False, "activities": []}}}
            ws.send(json.dumps(auth))
            
            # استقبال رسالة READY لحفظ Session ID
            try:
                receive_and_process(ws) 
            except:
                print("[ERROR] Failed to receive READY after Identify.", flush=True)
                continue

        # 5. حلقة Heartbeat والبقاء
        while ws.connected:
            try:
                # إرسال نبضة القلب مع آخر Sequence Number
                ws.send(json.dumps({"op": 1, "d": LAST_SEQUENCE}))
                
                # استقبال ومعالجة الرسائل
                receive_and_process(ws)
                
                # تحديث حالة الصوت بشكل دوري 
                if time.time() - last_update_time >= STATUS_UPDATE_INTERVAL:
                    current_mute = random.choice(boolean_choices)
                    current_deaf = random.choice(boolean_choices)
                    
                    print(f"[UPDATE] Changing Voice State. Mute: {current_mute} | Deaf: {current_deaf}", flush=True) 

                    vc_update = {
                        "op": 4, "d": {"guild_id": GUILD_ID, "channel_id": CHANNEL_ID, 
                                       "self_mute": current_mute, "self_deaf": current_deaf}}
                    ws.send(json.dumps(vc_update))
                    
                    last_update_time = time.time()
                    STATUS_UPDATE_INTERVAL = random.randint(300, 900) 
                    print(f"Next random update scheduled in {STATUS_UPDATE_INTERVAL} seconds.", flush=True) 

                # الانتظار حتى الموعد التالي لـ Heartbeat
                time.sleep(HEARTBEAT_INTERVAL_S) 
                
            except websocket.WebSocketConnectionClosedException:
                print("\n[INFO] WebSocket closed by Discord. Attempting Resume...", flush=True) 
                break 
            except Exception as e:
                print(f"\n[ERROR] Inner connection loop failed: {e}. Attempting Resume...", flush=True) 
                break 

# --- حلقة التشغيل الرئيسية (الحماية القصوى من الانهيار) ---
def run_joiner():
    os.system("clear")
    print(f"Logged in as {username}#{discriminator} ({userid}).", flush=True) 
    
    while True:
        try:
            maintain_session(usertoken)
        except Exception as e:
            print(f"[FATAL ERROR] The main session crashed entirely: {e}. Waiting 60s and re-launching...", flush=True) 
            time.sleep(60)

run_joiner()
