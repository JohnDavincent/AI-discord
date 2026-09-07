"""Bot Discord: baca pesan -> parse jadi transaksi -> simpan ke Postgres."""

import os
import discord
from dotenv import load_dotenv
load_dotenv() # baca .env

import db
from handler import handle



ALLOWED = {c.strip() for c in os.getenv("CHANNEL_IDS", "").split(",") if c.strip()}

intents = discord.Intents.default()
intents.message_content = True

class Bot(discord.Client):
    async def setup_hook(self):
        await db.connect()
        print("database sudah siap")
        
client = Bot(intents=intents)

@client.event
async def on_ready():
    print(f"login sebagai {client.user}")


@client.event
async def on_message(message):
    if message.author.bot:
        return 

    if ALLOWED and str(message.channel.id) not in ALLOWED:
        return

    print(f"{message.author} : {message.content!r}")
    reply = await handle(message.content, message.id, message.channel.id, message.created_at)
    if( reply):
        await message.channel.send(reply)



client.run(os.environ["DISCORD_TOKEN"])
