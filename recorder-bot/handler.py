"""Otak bot: pesan -> tafsir AI -> draft -> (setelah dikonfirmasi) simpan."""

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from message_repository import save_message
from deepseek_client import (
    parse_message,
    answer_with_data,
    regenerate as ai_regenerate,
    ParseFailed,
)
from transaction_repository import save_transactions
from query_repository import calculate_money

log = logging.getLogger(__name__)

__all__ = ["Draft", "analyze", "regenerate", "commit", "ParseFailed"]


@dataclass
class Draft:
    """Hasil tafsiran AI yang BELUM masuk database."""
    text: str                       # pesan asli user, dipakai jadi raw_message
    created_at: Any
    reply: str                      # kalimat dari AI
    transactions: list = field(default_factory=list)
    raw: dict = field(default_factory=dict)   # konteks untuk 'catat ulang'
    attempt: int = 1
    saved: bool = False

    @property
    def total(self) -> Decimal:
        """Positif = pemasukan bersih, negatif = pengeluaran bersih."""
        jumlah = Decimal(0)
        for t in self.transactions:
            jumlah += t["value"] if t["transaction_type"] == "income" else -t["value"]
        return jumlah


def _ringkas(data) -> str:
    """Hasil query jadi teks pendek yang enak dibaca model."""
    if isinstance(data, list):
        if not data:
            return "tidak ada transaksi"
        baris = []
        for r in data:
            waktu = r["created_time"].strftime("%d-%m-%Y") if r.get("created_time") else "-"
            baris.append(
                f"{waktu} | {r['title']} | {r['category']} | "
                f"{r['transaction_type']} | {r['value']}"
            )
        return " ;; ".join(baris)
    return str(data)


async def _resolve(text: str, result: dict) -> dict:
    """Kalau AI minta data, jalankan query lalu suruh AI menjawab pakai angkanya.

    Transaksi dari langkah pertama dipertahankan, karena di langkah kedua model
    hanya menjawab pertanyaan dan biasanya mengembalikan transactions kosong.
    """
    query = result.get("query")
    if not query:
        return result

    try:
        data = await calculate_money(**query)
    except Exception:
        log.exception("query gagal: %s", query)
        data = "QUERY GAGAL, data tidak bisa diambil"

    try:
        kedua = await answer_with_data(text, result, _ringkas(data))
    except Exception:
        log.exception("gagal menjawab dengan data")
        return result

    return {
        "reply": kedua["reply"],
        # sengaja dari langkah pertama: di langkah kedua model hanya menjawab
        # pertanyaan, dan kadang mengarang transaksi baru.
        "transactions": result["transactions"],
        "query": None,
    }


async def analyze(text, message_id, channel_id, created_at) -> Draft:
    """Tafsirkan pesan. Tidak menyentuh tabel transactions sama sekali."""
    await save_message(message_id, channel_id, text, created_at)

    result = await _resolve(text, await parse_message(text))
    return Draft(
        text=text,
        created_at=created_at,
        reply=result["reply"],
        transactions=result["transactions"],
        raw=result,
    )


async def regenerate(draft: Draft) -> Draft:
    """Tombol 'Catat ulang': tafsiran baru untuk pesan yang sama."""
    result = await _resolve(draft.text, await ai_regenerate(draft.text, draft.raw))
    return Draft(
        text=draft.text,
        created_at=draft.created_at,
        reply=result["reply"],
        transactions=result["transactions"],
        raw=result,
        attempt=draft.attempt + 1,
    )


async def commit(draft: Draft) -> list:
    """Tombol 'Oke': baru di sini transaksi masuk database."""
    if draft.saved:
        return []
    ids = await save_transactions(draft.transactions, draft.text, draft.created_at)
    draft.saved = True
    return ids
