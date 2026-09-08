import json, os, logging, asyncio
from openai import AsyncOpenAI
import openai
from prompt import SYSTEM_PROMPT
from validator import validate, ValidationError

log = logging.getLogger(__name__)

# Ganti lewat .env kalau nama modelnya berbeda (mis. deepseek-chat).
MODEL = os.getenv("DEEPSEEK_MODEL") or "deepseek-v4-flash"

_client = None


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=os.getenv("DEEPSEEK_API"),
            base_url="https://api.deepseek.com",
        )
    return _client


class ParseFailed(Exception):
    """Model still failed after try about 1 or 2 times"""


def _echo(answer: dict) -> str:
    """Jawaban AI sebelumnya, dikirim balik sebagai konteks percakapan."""
    return json.dumps(
        {
            "reply": answer.get("reply"),
            "transactions": answer.get("transactions", []),
            "query": None,
        },
        default=str,
        ensure_ascii=False,
    )


async def parse_message(text: str) -> dict:
    return await _calling([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": text},
    ])


async def answer_with_data(text: str, answer: dict, result) -> dict:
    """Langkah kedua: AI menjawab memakai angka asli dari database."""
    return await _calling([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": text},
        {"role": "assistant", "content": _echo(answer)},
        {"role": "user", "content":
            f"Hasil query dari database: {result}. "
            f"Jawab pertanyaan user memakai angka ini. Set query menjadi null."},
    ])


async def regenerate(text: str, previous: dict) -> dict:
    """Tombol 'Catat ulang': minta tafsiran baru atas pesan yang sama.

    Temperature sengaja dinaikkan, kalau 0 hasilnya akan sama persis.
    """
    return await _calling(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
            {"role": "assistant", "content": _echo(previous)},
            {"role": "user", "content":
                "Catatan di atas kurang tepat menurut user. Baca ulang pesan aslinya "
                "dan berikan tafsiran yang BERBEDA: bisa judulnya, kategorinya, "
                "jumlah item transaksinya, atau income/expense-nya. "
                "Jangan mengulang jawaban yang sama. Balas hanya JSON."},
        ],
        temperature=1.0,
    )


async def _calling(conversation, max_attempt=3, temperature=0) -> dict:
    for attempt in range(1, max_attempt + 1):
        # called the API
        try:
            response = await get_client().chat.completions.create(
                model=MODEL,
                messages=conversation,
                response_format={"type": "json_object"},
                max_tokens=1024,
                temperature=temperature,
            )

        except (openai.APIConnectionError, openai.APITimeoutError, openai.RateLimitError):
            if attempt == max_attempt:
                raise
            await asyncio.sleep(2 ** attempt)
            continue

        except (openai.AuthenticationError, openai.BadRequestError):
            raise

        content = response.choices[0].message.content or ""

        # Validation for the Model
        try:
            return validate(json.loads(content))
        except (json.JSONDecodeError, ValidationError) as e:
            log.warning("percobaan %d gagal: %s", attempt, e)
            if attempt == max_attempt:
                raise ParseFailed(str(e)) from e

            # give the feedback to the model
            conversation.append({"role": "assistant", "content": content})
            conversation.append({
                "role": "user",
                "content": f"Output json tadi salah: {e}. "
                           f"Perbaiki, balas ulang hanya dengan json yang benar.",
            })

    raise ParseFailed("kehabisan percobaan")
