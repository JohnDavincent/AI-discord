import asyncio
from dotenv import load_dotenv

load_dotenv()

from deepseek_client import parse_message, ParseFailed

KASUS = [
    "makan siang nasi padang 25rb",
    "makan 25rb, bensin 50rb",
    "halo apa kabar",
    "gaji bulan ini 5jt",
    "menurutmu saya boros nggak?",
    "catat makan 50rb. menurutmu kemahalan nggak?",
]

async def main():
    for teks in KASUS:
        print("=" * 60)
        print("INPUT :", teks)
        try:
            hasil = await parse_message(teks)
        except ParseFailed as e:
            print("PARSE GAGAL :", e)
            continue
        except Exception as e:
            print("ERROR :", type(e).__name__, "-", e)
            continue

        print("REPLY :", hasil["reply"])
        print("TRX   :", len(hasil["transactions"]))
        for t in hasil["transactions"]:
            print(f"   - {t['transaction_type']:<8} {t['value']:>12,} | {t['title']}")

asyncio.run(main())
