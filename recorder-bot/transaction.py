"""Parsing pesan Discord bebas-format menjadi satu baris transaksi.

Dipakai oleh bot.py. Tidak ada dependensi ke discord/asyncpg supaya gampang
dites sendiri:  python transaction.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

# Suffix angka ala Indonesia: 25rb, 1.5jt, 2m.
MULTIPLIERS: dict[str, Decimal] = {
    "rb": Decimal(1_000),
    "ribu": Decimal(1_000),
    "k": Decimal(1_000),
    "jt": Decimal(1_000_000),
    "juta": Decimal(1_000_000),
    "m": Decimal(1_000_000),
    "miliar": Decimal(1_000_000_000),
    "milyar": Decimal(1_000_000_000),
    "b": Decimal(1_000_000_000),
}

# Kata kunci yang memaksa jenis transaksi. Dicek sebagai kata utuh.
INCOME_WORDS = {
    "gaji", "bonus", "thr", "masuk", "pemasukan", "terima", "diterima",
    "dapat", "dapet", "untung", "profit", "jual", "refund", "cashback",
    "income", "salary", "bayaran", "komisi", "bunga", "dividen",
}
EXPENSE_WORDS = {
    "beli", "bayar", "keluar", "pengeluaran", "jajan", "belanja", "top-up",
    "topup", "expense", "spend", "buy", "pay", "tagihan", "bakar", "rugi",
}

_AMOUNT_RE = re.compile(
    r"""
    (?P<sign>[+-])?\s*
    (?:rp\.?\s*)?                                   # 'Rp' opsional
    (?P<num>
        \d{1,3}(?:[.,]\d{3})+                       # 25.000 / 1,250,000
      | \d+(?:[.,]\d{1,2})?                         # 25000 / 1.5 / 12,50
    )
    \s*
    (?P<suffix>rb|ribu|k|jt|juta|miliar|milyar|m|b)?
    (?![\w.,])                                      # jangan potong di tengah token
    """,
    re.IGNORECASE | re.VERBOSE,
)

_CURRENCY_RE = re.compile(r"\brp\.?\b", re.IGNORECASE)
_WORD_RE = re.compile(r"[a-zA-ZÀ-ÿ0-9_'-]+")

MAX_TITLE_LEN = 120


class ParseError(ValueError):
    """Pesan tidak mengandung transaksi yang bisa dibaca."""


@dataclass(frozen=True)
class Transaction:
    title: str
    description: str
    transaction_type: str  # 'income' | 'expense'
    value: Decimal

    def __str__(self) -> str:  # buat log & balasan bot
        sign = "+" if self.transaction_type == "income" else "-"
        return f"{sign}{self.value:,.2f} — {self.title}"


def _to_decimal(num: str, suffix: str | None) -> Decimal:
    """Ubah teks angka jadi Decimal, sadar konvensi ribuan Indonesia.

    Aturan pemisah:
      - ada suffix  -> pemisah terakhir dibaca sebagai koma desimal (1.5jt = 1_500_000)
      - pola X.XXX  -> pemisah ribuan, dibuang (25.000 = 25000)
      - selain itu  -> pemisah dibaca desimal (12,50 = 12.50)
    """
    if suffix:
        cleaned = num.replace(".", "#").replace(",", "#")
        head, _, tail = cleaned.rpartition("#")
        cleaned = f"{head.replace('#', '')}.{tail}" if head else tail
    elif re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", num):
        cleaned = re.sub(r"[.,]", "", num)
    else:
        cleaned = num.replace(",", ".")

    try:
        value = Decimal(cleaned)
    except InvalidOperation as exc:  # pragma: no cover - dijaga regex
        raise ParseError(f"angka tidak valid: {num!r}") from exc

    if suffix:
        value *= MULTIPLIERS[suffix.lower()]
    return value


def _pick_amount(content: str) -> re.Match[str]:
    """Pilih token angka yang paling mungkin jadi nominal.

    Prioritas: ada 'Rp'/suffix > kandidat terakhir. Ini menangani kalimat
    seperti 'beli 2 kopi 30rb' -> 30rb, bukan 2.
    """
    matches = [m for m in _AMOUNT_RE.finditer(content) if m.group("num")]
    if not matches:
        raise ParseError("tidak ada nominal di pesan")

    explicit = [
        m for m in matches
        if m.group("suffix") or _CURRENCY_RE.search(content[max(0, m.start() - 4):m.start() + 1])
    ]
    return (explicit or matches)[-1]


def _detect_type(content: str, sign: str | None) -> str:
    if sign == "+":
        return "income"
    if sign == "-":
        return "expense"

    words = {w.lower() for w in _WORD_RE.findall(content)}
    if words & INCOME_WORDS:
        return "income"
    if words & EXPENSE_WORDS:
        return "expense"
    return "expense"  # default: catatan pengeluaran


def _build_title(content: str, amount_span: tuple[int, int]) -> str:
    """Sisa kalimat setelah nominal dibuang, dipakai sebagai judul."""
    start, end = amount_span
    leftover = f"{content[:start]} {content[end:]}"
    leftover = _CURRENCY_RE.sub(" ", leftover)
    leftover = re.sub(r"\s+", " ", leftover).strip(" \t-–—:;,.")

    if not leftover:
        return "untitled"
    if len(leftover) > MAX_TITLE_LEN:
        leftover = leftover[: MAX_TITLE_LEN - 1].rstrip() + "…"
    return leftover


def parse_transaction(content: str) -> Transaction:
    """Ubah teks pesan jadi Transaction, atau lempar ParseError."""
    content = (content or "").strip()
    if not content:
        raise ParseError("pesan kosong")

    match = _pick_amount(content)
    value = _to_decimal(match.group("num"), match.group("suffix"))
    if value <= 0:
        raise ParseError("nominal harus lebih dari 0")

    # Kolom `value` numeric(19,2) -> bulatkan ke 2 desimal di sini supaya
    # error format ketahuan sebelum menyentuh database.
    value = value.quantize(Decimal("0.01"))

    return Transaction(
        title=_build_title(content, match.span()),
        description=content,
        transaction_type=_detect_type(content, match.group("sign")),
        value=value,
    )


if __name__ == "__main__":
    samples = [
        "makan siang 25rb",
        "beli 2 kopi 30.000",
        "gaji bulan ini 5jt",
        "Rp1.250.000 bayar kos",
        "bonus proyek +2.5jt",
        "top-up listrik 100k",
        "jual monitor bekas 750000",
        "halo semuanya",
    ]
    for text in samples:
        try:
            print(f"{text:<32} -> {parse_transaction(text)}")
        except ParseError as err:
            print(f"{text:<32} -> (skip: {err})")
