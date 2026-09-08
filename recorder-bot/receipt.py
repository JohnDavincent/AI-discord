"""Membentuk 'struk' transaksi untuk ditampilkan di Discord."""

from decimal import Decimal

import discord

NAME_W = 16     # lebar kolom judul
AMT_W = 13      # lebar kolom nominal
WIDTH = NAME_W + AMT_W + 4
MAX_ROWS = 10   # sisanya diringkas jadi satu baris

STYLE = {
    "draft":   ("🧾 Draft Catatan", discord.Color.blurple()),
    "saved":   ("✅ Tersimpan",      discord.Color.green()),
    "expired": ("⌛ Kedaluwarsa",    discord.Color.light_grey()),
}


def rupiah(nilai) -> str:
    """25000 -> 'Rp25.000'"""
    return f"Rp{Decimal(nilai):,.0f}".replace(",", ".")


def _potong(teks: str, lebar: int) -> str:
    teks = " ".join(teks.split())
    return teks if len(teks) <= lebar else teks[: lebar - 1] + "…"


def build_lines(transactions) -> list[str]:
    """Isi struk sebagai list baris teks (tanpa dependensi Discord)."""
    baris = []
    total = Decimal(0)

    for i, t in enumerate(transactions, 1):
        income = t["transaction_type"] == "income"
        total += t["value"] if income else -t["value"]

        if i > MAX_ROWS:
            continue

        nama = _potong(t["title"], NAME_W)
        nominal = ("+" if income else "-") + rupiah(t["value"])
        baris.append(f"{i:>2}. {nama:<{NAME_W}} {nominal:>{AMT_W}}")
        if t.get("category"):
            baris.append(f"    {t['category']}")

    sisa = len(transactions) - MAX_ROWS
    if sisa > 0:
        baris.append(f"    … dan {sisa} transaksi lain")

    baris.append("-" * WIDTH)
    tanda = "+" if total >= 0 else "-"
    baris.append(f"{'TOTAL':<{NAME_W + 4}}{tanda + rupiah(abs(total)):>{AMT_W}}")
    return baris


def build_embed(draft, state: str = "draft") -> discord.Embed:
    judul, warna = STYLE[state]
    isi = "\n".join(build_lines(draft.transactions))

    embed = discord.Embed(
        title=judul,
        description=f"```\n{isi}\n```",
        color=warna,
    )

    if state == "draft":
        embed.set_footer(text=f"Tafsiran ke-{draft.attempt} · belum disimpan")
    elif state == "saved":
        embed.set_footer(text=f"{len(draft.transactions)} transaksi masuk database")
    else:
        embed.set_footer(text="Tidak jadi disimpan · kirim ulang pesannya kalau masih perlu")

    return embed
