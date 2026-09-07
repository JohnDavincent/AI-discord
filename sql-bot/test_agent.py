"""Tes agent tanpa Discord.

Tujuannya dua: memastikan DeepSeek + Postgres tersambung, dan melihat
BENTUK UiComponent yang di-yield - itu yang menentukan bagaimana bot.py
nanti mengubahnya jadi pesan Discord.

Jalankan:  .\\.venv\\Scripts\\python.exe test_agent.py
"""

import asyncio

from vanna_agent import build_agent, konteks_discord

PERTANYAAN = "Berapa total pengeluaran saya sejauh ini?"


async def main():
    agent = build_agent()
    ctx = konteks_discord(user_id="123456789", username="pemilik")

    print(f"TANYA: {PERTANYAAN}\n" + "-" * 70)

    n = 0
    async for komponen in agent.send_message(
        ctx, PERTANYAAN, conversation_id="tes-lokal"
    ):
        n += 1
        print(f"\n[{n}] {type(komponen).__name__}")
        try:
            for k, v in komponen.model_dump().items():
                teks = str(v)
                if len(teks) > 400:
                    teks = teks[:400] + " ...(dipotong)"
                print(f"      {k} = {teks}")
        except AttributeError:
            print(f"      {komponen}")

    print("\n" + "-" * 70 + f"\nTotal {n} komponen.")


asyncio.run(main())
