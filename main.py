import sys
sys.modules['audioop'] = None
import discord
import os
import time
from keep_alive import keep_alive

# إعدادات الحساب والقناة
TOKEN = os.getenv("TOKEN")
GUILD_ID = 961795359544328203
CHANNEL_ID = 1428594267189678080

# العميل (الفرق هو استخدام discord.Client بدلاً من commands.Bot)
# تحتاج أيضًا إلى تعطيل Intents (النوايا) لتشغيل العميل الذاتي
client = discord.Client(intents=discord.Intents.none(), status=discord.Status.dnd) # dnd هو حالة الحساب

@client.event
async def on_ready():
    print(f"Logged in as {client.user} ({client.user.id}).")
    
    # البحث عن السيرفر (Guild) والقناة الصوتية (Voice Channel)
    guild = client.get_guild(GUILD_ID)
    if not guild:
        print("Guild not found.")
        return
    
    channel = guild.get_channel(CHANNEL_ID)
    
    if channel and isinstance(channel, discord.VoiceChannel):
        print(f"Attempting to join voice channel: {channel.name}")
        try:
            # محاولة الاتصال بالقناة الصوتية
            await channel.connect(self_mute=False, self_deaf=False)
            print("Successfully connected to voice channel.")
        except Exception as e:
            print(f"Error connecting to voice channel: {e}")
    else:
        print("Error: Voice channel not found or not a Voice Channel.")

def run_client():
    # تشغيل خدمة keep_alive
    keep_alive() 
    # تشغيل العميل باستخدام رمز المستخدم (TOKEN)
    client.run(TOKEN, bot=False) # bot=False هي الأهم للإشارة إلى أنه User Token

# البدء بتشغيل العميل
run_client()
