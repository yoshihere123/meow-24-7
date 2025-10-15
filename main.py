import os
import sys
import json
import time
import threading
import requests
import websocket
from keep_alive import keep_alive  # لو تستخدم استضافة مثل Replit

# ------ إعدادات ------
status = "dnd"  # online / idle / dnd
GUILD_ID = "859063643006173214"
LOBBY_CHANNEL_ID = "882218490570891264"
SELF_MUTE = False
SELF_DEAF = False

# توكن الحساب من المتغيرات البيئية
usertoken = os.getenv("TOKEN")
if not usertoken:
    print("[ERROR] Please add a token inside Secrets.")
    sys.exit()

headers = {"Authorization": usertoken, "Content-Type": "application/json"}

# تحقق من التوكن ومعلومات المستخدم
validate = requests.get('https://canary.discord.com/api/v9/users/@me', headers=headers)
if validate.status_code != 200:
    print("[ERROR] Your token might be invalid. Please check it again.")
    sys.exit()

userinfo = validate.json()
username = userinfo.get("username")
discriminator = userinfo.get("discriminator")
userid = userinfo.get("id")

# حالات وبلوبالز
heartbeat_interval_ms = None
ws = None
current_channel = None           # القناة التي حاولنا الانضمام لها عبر payload
last_known_channel = None        # آخر روم مؤقت انتقلت إليه (لحفظه وإعادة المحاولة)
recv_loop_running = False
stop_signal = False


# ----- دوال مساعدة -----
def check_channel_exists(channel_id):
    """يتحقق إن القناة موجودة ويمكن الوصول إليها عبر REST API"""
    try:
        url = f"https://discord.com/api/v9/channels/{channel_id}"
        r = requests.get(url, headers=headers, timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def get_channel_name(channel_id):
    try:
        url = f"https://discord.com/api/v9/channels/{channel_id}"
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            return r.json().get("name", "Unknown")
    except Exception:
        pass
    return "Unknown"


def send_identify(sock):
    payload = {
        "op": 2,
        "d": {
            "token": usertoken,
            "properties": {
                "$os": "Windows 10",
                "$browser": "Google Chrome",
                "$device": "Windows"
            },
            "presence": {"status": status, "afk": False}
        }
    }
    sock.send(json.dumps(payload))


def send_voice_state(sock, channel_id):
    """ارسال طلب الانضمام/تغيير الحالة الصوتية إلى قناة"""
    global current_channel
    current_channel = channel_id
    payload = {
        "op": 4,
        "d": {
            "guild_id": GUILD_ID,
            "channel_id": channel_id,
            "self_mute": SELF_MUTE,
            "self_deaf": SELF_DEAF
        }
    }
    try:
        sock.send(json.dumps(payload))
        print(f"[INFO] Sent VOICE_STATE payload -> channel_id: {channel_id}")
    except Exception as e:
        print(f"[ERROR] Failed to send VOICE_STATE payload: {e}")


def heartbeat_thread(sock):
    """يرسل heartbeat بشكل دوري بناءً على القيمة التي أعطاها السيرفر"""
    global heartbeat_interval_ms, stop_signal
    while not stop_signal:
        if heartbeat_interval_ms:
            try:
                sock.send(json.dumps({"op": 1, "d": None}))
            except Exception as e:
                print(f"[Heartbeat Error] {e}")
                # لو فشل الإرسال، اترك الحلقة لتسمح لإعادة الاتصال بالخارج
                return
            time.sleep(heartbeat_interval_ms / 1000.0)
        else:
            time.sleep(1)


# ----- حلقة استقبال ومعالجة الرسائل (مطابقة للكود الأصلي) -----
def recv_loop(sock):
    global heartbeat_interval_ms, last_known_channel, current_channel, recv_loop_running, stop_signal
    recv_loop_running = True
    # بعد الIdentify وارسال الـ VOICE_STATE، نقرأ الرسائل ونتعامل مع الأحداث
    try:
        while not stop_signal:
            try:
                raw = sock.recv()
            except websocket.WebSocketConnectionClosedException:
                print("[WARN] WebSocket connection closed by remote.")
                break
            except Exception as e:
                print(f"[ERROR] ws.recv() failed: {e}")
                break

            if not raw:
                continue

            try:
                msg = json.loads(raw)
            except Exception:
                continue

            # استقبال op 10 (HELLO) — نأخذ heartbeat interval ثم نرسل identify
            if msg.get("op") == 10:
                heartbeat_interval_ms = msg["d"]["heartbeat_interval"]
                # نبدأ الثريد الذي يرسل heartbeat دوري
                hb_t = threading.Thread(target=heartbeat_thread, args=(sock,), daemon=True)
                hb_t.start()
                # نرسل identify كما في الكود الأصلي
                send_identify(sock)
                # بعد identify، نطلب الانضمام للـ LOBBY (المرجع)
                time.sleep(1)
                print("[INFO] Identified. Joining lobby channel...")
                send_voice_state(sock, LOBBY_CHANNEL_ID)
                current_channel = LOBBY_CHANNEL_ID
                continue

            # تعاطي مع الايفنتات حسب نوعها
            t = msg.get("t")
            if t == "VOICE_STATE_UPDATE":
                data = msg.get("d", {})
                # اهتم فقط بحالة المستخدم الحالي
                if data.get("user_id") == userid:
                    new_channel = data.get("channel_id")  # ممكن تكون None عند الطرد/الخروج
                    # حالة الطرد/الخروج (channel_id == None)
                    if new_channel is None:
                        print("[INFO] Voice state: disconnected (channel_id = null).")
                        # نحاول نرجع للروم المؤقت الأخير إن موجود ويمكن الوصول له
                        if last_known_channel:
                            exists = check_channel_exists(last_known_channel)
                            if exists:
                                print(f"[INFO] Attempting to rejoin last known temp channel: {last_known_channel}")
                                time.sleep(1)
                                send_voice_state(sock, last_known_channel)
                                current_channel = last_known_channel
                                continue
                            else:
                                print("[INFO] Last known temp channel doesn't exist or access denied.")
                        # لو ما نقدر نرجع للروم المؤقت، نرجع للـ Lobby
                        print("[INFO] Rejoining Lobby channel...")
                        time.sleep(1)
                        send_voice_state(sock, LOBBY_CHANNEL_ID)
                        current_channel = LOBBY_CHANNEL_ID
                        continue

                    # حالة النقل إلى روم جديد (قد يكون روم مؤقت أنشأه البوت)
                    if new_channel != current_channel:
                        last_known_channel = new_channel
                        ch_name = get_channel_name(new_channel)
                        print(f"[INFO] Detected move -> new channel id: {new_channel} (name: {ch_name})")
                        # نؤكد الانضمام بمرسلة VOICE_STATE كما في الكود الأصلي
                        send_voice_state(sock, new_channel)
                        current_channel = new_channel
                        continue

            # لو فيه رسائل أخرى يمكن طباعتها للـ debug
            # print("DEBUG MSG:", msg)

    finally:
        recv_loop_running = False
        # نوقف الـ heartbeat إن كان شغال
        stop_signal = True


# ----- دالة الإنشاء / إعادة الاتصال (شبيهة بكودك الأصلي) -----
def joiner(token, status):
    global ws, heartbeat_interval_ms, current_channel, last_known_channel, stop_signal

    # نحاول عدة مرات في حلقة (مثل كودك الأصلي)
    while True:
        try:
            ws = websocket.WebSocket()
            ws.connect('wss://gateway.discord.gg/?v=9&encoding=json', timeout=20)
            print("[INFO] Connected to Gateway.")
        except Exception as e:
            print(f"[ERROR] Failed to connect gateway: {e}. Retrying in 5s...")
            time.sleep(5)
            continue

        # نستقبل أول رسالة (HELLO عادة) مثل كودك القديم
        try:
            start = json.loads(ws.recv())
        except Exception as e:
            print(f"[ERROR] Failed to receive initial hello: {e}. Reconnecting...")
            try:
                ws.close()
            except:
                pass
            time.sleep(3)
            continue

        # أخذ heartbeat interval وبدء حلقة استقبال متقدمة
        heartbeat_interval_ms = start.get('d', {}).get('heartbeat_interval') or heartbeat_interval_ms
        # أرسل Identify (مرة أخرى لضمان المطابقة مع الكود الأصلي)
        send_identify(ws)

        # أرسل أمر الانضمام للـ lobby (حتى لو تم نقلك لاحقاً)
        time.sleep(1)
        try:
            send_voice_state(ws, LOBBY_CHANNEL_ID)
        except Exception as e:
            print(f"[ERROR] failed to send initial VOICE_STATE: {e}")

        # نبدأ حلقة استقبال تعالج الايفنتات وتستمر بعمل heartbeat عبر ثريد
        stop_signal = False
        recv_loop(ws)

        # لو خرجنا من recv_loop، نغلق ونعاود المحاولة بعد تأخير
        try:
            ws.close()
        except:
            pass
        print("[INFO] Connection lost — will reconnect in 5 seconds...")
        time.sleep(5)
        # تابع الحلقة وأعد الاتصال (كما في الloop الأصلي)
        continue


def run_joiner():
    os.system("clear" if os.name != "nt" else "cls")
    print(f"Logged in as {username}#{discriminator} ({userid}).")
    try:
        joiner(usertoken, status)
    except KeyboardInterrupt:
        print("[INFO] Exiting by user.")
        sys.exit(0)
    except Exception as e:
        print(f"[FATAL] Unexpected error: {e}")
        sys.exit(1)


# لو تستخدم خدمة تبقي السكربت حي
keep_alive()

# بدء التشغيل
run_joiner()
