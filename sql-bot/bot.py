"""Bot Discord kedua: menjawab pertanyaan tentang database, ditenagai Vanna.

Bot ini HANYA membaca. Kredensial databasenya role brain_reader yang tidak
punya izin tulis sama sekali - lihat initdb/02_readonly_role.sql.
"""

import logging
import os

import discord
from dotenv import load_dotenv

load_dotenv()

from vanna_agent import build_agent, konteks_discord

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
log = logging.getLogger("sql-bot")

OWNER_ID = int(os.getenv("OWNER_ID", "0"))
ALLOWED = {c.strip() for c in os.getenv("CHANNEL_IDS", "").split(",") if c.strip()}

BATAS_DISCORD = 1900  # batas asli 2000, sisakan ruang aman

intents = discord.Intents.default()
intents.message_content = True


class SqlBot(discord.Client):
    async def setup_hook(self):
        self.agent = build_agent()
        log.info("agent vanna siap")


client = SqlBot(intents=intents)


def potong(teks: str):
    """Discord menolak pesan di atas 2000 karakter; jawaban LLM gampang lewat."""
    for i in range(0, len(teks), BATAS_DISCORD):
        yield teks[i : i + BATAS_DISCORD]


def ambil_teks(komponen) -> str | None:
    """Dari ~10 komponen per jawaban, hanya yang bertipe TEXT yang berisi jawaban.

    Sisanya status bar, task tracker, dan chat input - itu untuk web UI Vanna,
    tidak ada gunanya di Discord.
    """
    rc = komponen.rich_component
    if rc is None:
        return None
    tipe = getattr(rc, "type", None)
    if getattr(tipe, "value", tipe) != "text":
        return None
    return getattr(rc, "content", None)


@client.event
async def on_ready():
    log.info("login sebagai %s", client.user)
    if OWNER_ID:
        log.info("hanya melayani user %s", OWNER_ID)


@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    # Gerbang terkuat: identitas dari Discord, tidak bisa dipalsukan
    # tanpa membajak akun. Lebih kuat daripada password yang diketik di chat.
    if OWNER_ID and message.author.id != OWNER_ID:
        return
    if ALLOWED and str(message.channel.id) not in ALLOWED:
        return

    log.info("tanya: %r", message.content)
    bagian = []

    # Vanna butuh ~10 detik: introspeksi skema, query, lalu merangkai jawaban.
    # Tanpa indikator ini, bot terlihat mati.
    async with message.channel.typing():
        try:
            async for komponen in client.agent.send_message(
                konteks_discord(message.author.id, message.author.name),
                message.content,
                # Satu percakapan per channel - Vanna yang mengurus historinya.
                conversation_id=str(message.channel.id),
            ):
                teks = ambil_teks(komponen)
                if teks:
                    bagian.append(teks)
        except Exception:
            log.exception("agent gagal")
            await message.channel.send("Maaf, ada gangguan saat memproses pertanyaan.")
            return

    jawaban = "\n".join(bagian).strip()
    if not jawaban:
        jawaban = "Tidak ada jawaban yang bisa saya berikan untuk itu."

    for potongan in potong(jawaban):
        await message.channel.send(potongan)


def main():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("DISCORD_TOKEN belum diisi di sql-bot/.env")
    if not OWNER_ID:
        log.warning("OWNER_ID kosong - siapa pun di channel ini bisa query database")
    client.run(token, log_handler=None)


if __name__ == "__main__":
    main()
