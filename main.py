import os
import sys
import json
import time
import requests
import websocket
from keep_alive import keep_alive 

status = "dnd"  # online/dnd/idle

GUILD_ID = 859063643006173214
CHANNEL_ID = 882218490570891264  # اللوبي
SELF_MUTE = False
SELF_DEAF = False

usertoken = os.getenv("TOKEN")
if not usertoken:
    print("[ERROR] Please add a token inside Secrets.")
    sys.exit()

headers = {"Authorization": usertoken, "Content-Type": "application/json"}

validate = requests.get('https://canary.discordapp.com/api/v9/users/@me', headers=headers)
if validate.status_code != 200:
    print("[ERROR] Your token might be invalid. Please check it again.")
    sys.exit()

userinfo = validate.json()
username = userinfo["username"]
discriminator = userinfo["discriminator"]
userid = userinfo["id"]

current_channel_id = None  # لتتبع الروم المؤقت

def get_user_voice_channel():
    url = f"https://discord.com/api/v9/guilds/{GUILD_ID}/voice-states/{userid}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        return data.get("channel_id")
    return None

def get_channel_info(channel_id):
    url = f"https://discord.com/api/v9/channels/{channel_id}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()  # ✅ تم التعديل هنا
    return None

def move_to_channel(channel_id):
    ws = websocket.WebSocket()
    ws.connect('wss://gateway.discord.gg/?v=9&encoding=json')
    start = json.loads(ws.recv())
    heartbeat = start['d']['heartbeat_interval']

    auth = {
        "op": 2,
        "d": {
            "token": usertoken,
            "properties": {
                "$os": "Windows",
                "$browser": "Chrome",
                "$device": "Windows"
            },
            "presence": {"status": status, "afk": False}
        }
    }

    vc = {
        "op": 4,
        "d": {
            "guild_id": GUILD_ID,
            "channel_id": channel_id,
            "self_mute": SELF_MUTE,
            "self_deaf": SELF_DEAF
        }
    }

    ws.send(json.dumps(auth))
    time.sleep(1)
    ws.send(json.dumps(vc))
    time.sleep(heartbeat / 1000)
    ws.send(json.dumps({"op": 1, "d": None}))
    ws.close()

def run_joiner():
    global current_channel_id

    os.system("clear")
    print(f"Logged in as {username}#{discriminator} ({userid}).")

    print("[INFO] Joining lobby...")
    move_to_channel(CHANNEL_ID)

    while True:
        time.sleep(30)

        current_voice = get_user_voice_channel()

        if current_voice is None:
            print("[WARN] Not connected to any voice channel.")

            if current_channel_id:
                print(f"[INFO] Trying to rejoin previous channel: {current_channel_id}")
                resp = get_channel_info(current_channel_id)
                if resp:
                    move_to_channel(current_channel_id)
                    print("[INFO] Rejoined temporary channel.")
                else:
                    print("[ERROR] Temp channel not found. Joining lobby again.")
                    move_to_channel(CHANNEL_ID)
                    current_channel_id = None
            else:
                print("[INFO] Joining lobby again...")
                move_to_channel(CHANNEL_ID)

        elif current_channel_id is None and current_voice != CHANNEL_ID:
            current_channel_id = current_voice
            print(f"[INFO] Joined temporary channel: {current_channel_id}")

        elif current_channel_id and current_voice != current_channel_id:
            print(f"[WARN] Moved from temp channel. Trying to return...")
            resp = get_channel_info(current_channel_id)
            if resp:
                move_to_channel(current_channel_id)
                print("[INFO] Rejoined temporary channel.")
            else:
                print("[ERROR] Temp channel no longer exists. Going back to lobby...")
                move_to_channel(CHANNEL_ID)
                current_channel_id = None

        else:
            print("[INFO] Still in temporary channel. All good.")

keep_alive()
run_joiner()
