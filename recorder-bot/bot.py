"""Bot Discord: baca pesan -> AI menafsirkan -> user konfirmasi -> simpan ke Postgres."""

import logging
import os

import discord
from dotenv import load_dotenv

load_dotenv()  # baca .env

import db
from handler import analyze, ParseFailed
from receipt import build_embed
from view import ConfirmView

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("bot")

ALLOWED = {c.strip() for c in os.getenv("CHANNEL_IDS", "").split(",") if c.strip()}


def _wajib(nama: str) -> str:
    """Ambil env var yang wajib ada. Kosong = berhenti dengan pesan jelas.

    os.environ tidak melempar error untuk 'KUNCI=' yang kosong, dan nilai
    kosong itu baru ketahuan jauh di dalam library sebagai 401.
    """
    nilai = (os.getenv(nama) or "").strip()
    if not nilai:
        raise SystemExit(
            f"{nama} belum diisi di file .env "
            f"({os.path.abspath('.env')}). Isi dulu, lalu jalankan lagi."
        )
    return nilai


TOKEN = _wajib("DISCORD_TOKEN")
_wajib("DEEPSEEK_API")   # dipakai deepseek_client, dicek di awal biar tidak gagal di tengah jalan

intents = discord.Intents.default()
intents.message_content = True


class Bot(discord.Client):
    async def setup_hook(self):
        await db.connect()
        log.info("database sudah siap")

    async def close(self):
        await super().close()
        await db.close()


client = Bot(intents=intents)


@client.event
async def on_ready():
    log.info("login sebagai %s", client.user)


@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if ALLOWED and str(message.channel.id) not in ALLOWED:
        return

    if not message.content.strip():
        return

    log.info("%s : %r", message.author, message.content)

    async with message.channel.typing():
        try:
            draft = await analyze(message.content, message.created_at)
        except ParseFailed:
            await message.reply(
                "Maaf, saya belum bisa membaca pesan itu. "
                "Coba tulis lebih terstruktur, contoh: `makan siang 25rb`"
            )
            return
        except Exception:
            log.exception("gagal memanggil AI")
            await message.reply("Sedang ada gangguan, coba lagi sebentar lagi.")
            return

    # Ngobrol, tanya data, atau minta saran keuangan -> jawab langsung,
    # tidak ada yang perlu dicatat dan tidak perlu tombol.
    if not draft.transactions:
        await message.reply(draft.reply[:1900])
        return

    view = ConfirmView(draft, message.author.id)
    view.message = await message.reply(
        content="Baik, saya buatkan dulu catatan transaksinya 👇",
        embed=build_embed(draft, "draft"),
        view=view,
    )


client.run(TOKEN)
