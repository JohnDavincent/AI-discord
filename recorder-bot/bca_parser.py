"""Email 'Internet Transaction Journal' dari BCA -> BankTx.

Email BCA berbentuk tabel 'Label : Nilai' berbahasa Inggris. Parser ini
membacanya sebagai pasangan kunci-nilai, bukan lewat posisi, supaya urutan
baris boleh berubah tanpa merusak apa pun.

Dites tanpa jaringan:  python bca_parser.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

WIB = ZoneInfo("Asia/Jakarta")

# Bulan ditulis manual: strptime("%b") ikut locale sistem, dan di mesin
# berlokal Indonesia "Sep" bisa gagal dibaca.
_BULAN = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    # jaga-jaga kalau BCA mengirim versi bahasa Indonesia
    "mei": 5, "agu": 8, "okt": 10, "des": 12,
}

# Kata pada 'Transfer Type' / isi email yang menandakan uang MASUK.
_MASUK = ("transfer from", "incoming", "received", "credit", "transfer masuk", "dana masuk")

# Status yang dianggap transaksi benar-benar terjadi.
_SUKSES = ("successful", "success", "berhasil", "sukses")


@dataclass
class BankTx:
    gmail_id: str          # dipakai sebagai source_ref (unik per baris)
    at: datetime           # waktu transaksi, WIB
    amount: Decimal
    direction: str         # 'in' | 'out'
    counterparty: str
    kind: str              # 'transfer' | 'qris' | 'pembayaran' | 'biaya' | 'lainnya'
    raw: str
    self_transfer: bool = False    # kirim ke rekening sendiri
    note: str = ""                 # purpose / remarks, bahan untuk AI
    fields: dict = field(default_factory=dict)


class UnknownFormat(Exception):
    """Email terlihat seperti transaksi tapi bentuknya tidak dikenali."""


# --------------------------------------------------------------------------
# pembacaan teks
# --------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Rapikan hasil konversi HTML.

    Kalau tabel HTML dipecah per sel, nilainya bisa jatuh ke baris sendiri
    (' : Successful'). Baris seperti itu disambung ke baris sebelumnya.
    """
    text = text.replace("\xa0", " ")
    keluar: list[str] = []
    for baris in text.splitlines():
        baris = baris.rstrip()
        if baris.lstrip().startswith(":") and keluar:
            keluar[-1] = f"{keluar[-1].rstrip()} {baris.lstrip()}"
        else:
            keluar.append(baris)
    return "\n".join(keluar)


def fields(text: str) -> dict[str, str]:
    """Semua pasangan 'Label : Nilai'. Kunci dibuat huruf kecil tanpa titik."""
    hasil: dict[str, str] = {}
    for baris in _normalize(text).splitlines():
        if ":" not in baris:
            continue
        label, _, nilai = baris.partition(":")     # colon PERTAMA = pemisah
        label = " ".join(label.split()).lower().rstrip(".")
        nilai = nilai.strip()
        # label wajar: 2-40 huruf, bukan kalimat panjang
        if label and nilai and len(label) <= 40 and re.fullmatch(r"[a-z][a-z .'/-]*", label):
            hasil.setdefault(label, nilai)
    return hasil


def to_decimal(teks: str) -> Decimal | None:
    """'IDR 20,000.00' -> 20000.00 ; 'Rp2.500,00' -> 2500.00

    Aturannya satu: kalau pemisah TERAKHIR diikuti tepat 2 digit, dia pemisah
    desimal; selain itu semua pemisah adalah pemisah ribuan. Ini menangani
    format Inggris maupun Indonesia tanpa perlu tahu mana yang dipakai.
    """
    m = re.search(r"(\d[\d.,]*\d|\d)", teks or "")
    if not m:
        return None
    angka = m.group(1)

    akhir = max(angka.rfind("."), angka.rfind(","))
    if akhir != -1 and len(angka) - akhir - 1 == 2:
        utuh = re.sub(r"[.,]", "", angka[:akhir])
        return Decimal(f"{utuh or 0}.{angka[akhir + 1:]}")
    return Decimal(re.sub(r"[.,]", "", angka))


def to_datetime(teks: str) -> datetime | None:
    """'10 Sep 2026 13:14:06' -> datetime berzona WIB."""
    m = re.search(
        r"(\d{1,2})\s+([A-Za-z]{3,})\s+(\d{4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?",
        teks or "",
    )
    if not m:
        return None
    bulan = _BULAN.get(m.group(2)[:3].lower())
    if not bulan:
        return None
    return datetime(
        int(m.group(3)), bulan, int(m.group(1)),
        int(m.group(4) or 0), int(m.group(5) or 0), int(m.group(6) or 0),
        tzinfo=WIB,
    )


# --------------------------------------------------------------------------
# penafsiran
# --------------------------------------------------------------------------

def _owner(text: str) -> str:
    """Nama pemilik rekening, dari sapaan 'Hello JOHN DAVINCENT,'."""
    m = re.search(r"^\s*(?:hello|halo|dear|hi)\s+(.+?)\s*,", text, re.I | re.M)
    return " ".join(m.group(1).split()).upper() if m else ""


def _direction(f: dict, text: str) -> str:
    petunjuk = f"{f.get('transfer type', '')} {f.get('transaction type', '')}".lower()
    if any(k in petunjuk for k in _MASUK):
        return "in"
    if any(k in text.lower() for k in _MASUK):
        return "in"
    if "beneficiary name" in f or "beneficiary account no" in f:
        return "out"          # ada penerima -> uang keluar
    return "out"


def _kind(f: dict, text: str) -> str:
    petunjuk = " ".join([
        f.get("transfer type", ""), f.get("transaction type", ""),
        f.get("transfer method", ""), text[:400],
    ]).lower()
    for kata, nilai in (
        ("qris", "qris"), ("virtual account", "pembayaran"),
        ("payment", "pembayaran"), ("pembayaran", "pembayaran"),
        ("top up", "topup"), ("purchase", "pembelian"),
        ("transfer", "transfer"),
    ):
        if kata in petunjuk:
            return nilai
    return "lainnya"


# Nama lawan transaksi bisa muncul dengan banyak label berbeda tergantung
# jenis transaksinya (transfer, QRIS, pembayaran tagihan, top up).
_NAMA_FIELD = ("beneficiary name", "merchant name", "merchant", "payee name",
               "biller name", "product name", "sender name", "remitter name")
_BANK_FIELD = ("beneficiary bank", "sender bank", "merchant location", "biller")


def _counterparty(f: dict, sendiri: bool) -> str:
    nama = next((f[k] for k in _NAMA_FIELD if f.get(k)), "")
    bank = next((f[k] for k in _BANK_FIELD if f.get(k)), "")
    tujuan = f.get("transfer type") or f.get("transaction type") or ""

    if sendiri and bank:
        return f"{bank} (rekening sendiri)"
    if nama and bank and nama.upper() != bank.upper():
        return f"{nama} - {bank}"
    kandidat = nama or bank or re.sub(r"^transfer\s+to\s+", "", tujuan, flags=re.I)
    return " ".join(kandidat.split())[:120] or "transaksi bank"


def parse(email) -> list[BankTx]:
    """Satu email -> nol, satu, atau dua BankTx (transaksi + biaya admin).

    Mengembalikan [] kalau email ini bukan transaksi atau transaksinya gagal.
    """
    text = getattr(email, "text", "") or ""
    f = fields(text)

    nominal = to_decimal(f.get("amount") or f.get("nominal") or "")
    if nominal is None or nominal <= 0:
        return []                                  # bukan email transaksi

    status = (f.get("status") or "").lower()
    if status and not any(s in status for s in _SUKSES):
        return []                                  # gagal/pending -> jangan dicatat

    waktu = (to_datetime(f.get("transaction date") or f.get("tanggal transaksi") or "")
             or email.received_at.astimezone(WIB))

    owner = _owner(text)
    penerima = (f.get("beneficiary name") or "").upper()
    sendiri = bool(owner and penerima and owner == penerima)

    arah = _direction(f, text)
    jenis = _kind(f, text)
    catatan = " ".join(x for x in (
        f.get("transaction purpose", ""),
        f.get("remarks", "") if f.get("remarks", "-") not in ("-", "") else "",
    ) if x).strip()

    utama = BankTx(
        gmail_id=email.id,
        at=waktu,
        amount=nominal,
        direction=arah,
        counterparty=_counterparty(f, sendiri),
        kind=jenis,
        raw=text[:2000],
        self_transfer=sendiri,
        note=catatan,
        fields=f,
    )
    hasil = [utama]

    # Biaya admin dicatat terpisah supaya total yang keluar dari rekening tetap
    # utuh, tanpa mengotori nominal transaksi aslinya.
    biaya = to_decimal(f.get("fee") or f.get("biaya") or "")
    if biaya and biaya > 0:
        hasil.append(BankTx(
            gmail_id=f"{email.id}:fee",            # source_ref harus unik
            at=waktu,
            amount=biaya,
            direction="out",
            counterparty=f"Biaya {jenis} {f.get('transfer method', '')}".strip(),
            kind="biaya",
            raw=text[:2000],
            note="biaya admin",
            fields=f,
        ))
    return hasil


def to_message(txs: list[BankTx]) -> str:
    """Teks untuk parse_message(). AI hanya diminta judul & kategori."""
    baris = []
    for i, t in enumerate(txs, 1):
        potongan = [
            f"{i}. {t.at:%d/%m %H:%M}",
            "masuk" if t.direction == "in" else "keluar",
            t.kind,
            t.counterparty,
            f"Rp{t.amount:,.0f}".replace(",", "."),
        ]
        if t.note:
            potongan.append(f"({t.note})")
        if t.self_transfer:
            potongan.append("[transfer ke rekening sendiri]")
        baris.append(" | ".join(potongan))

    return (
        "Catat transaksi dari notifikasi bank berikut. Nominal dan arah sudah "
        "pasti benar, jangan diubah. Beri judul singkat dan kategori untuk tiap "
        "baris, urutan dan jumlah baris harus sama persis:\n" + "\n".join(baris)
    )


# --------------------------------------------------------------------------
if __name__ == "__main__":
    from datetime import timezone
    from types import SimpleNamespace

    CONTOH = """Hello JOHN DAVINCENT,
You just made a transaction through myBCA.
Here are the details of your transaction :

Status : Successful
Transaction Date : 10 Sep 2026 13:14:06
Transfer Type : Transfer to BANK JAGO
Source of Fund : 8550xxxx81
Beneficiary Account
Beneficiary Name : JOHN DAVINCENT
Beneficiary Bank : BANK JAGO
Beneficiary Account No. : 100879999795
Amount : IDR 20,000.00
Fee : IDR 2,500.00
Transfer Method : BI FAST
Remarks : -
Transaction Purpose : Investment
Reference No. : 20260910CENAIDJA51044704458
The funds will be effective in the destination account after the transfer of
funds has been successfully forwarded by Bank Indonesia (BI) to the beneficiary
bank."""

    email = SimpleNamespace(
        id="abc123",
        subject="Internet Transaction Journal",
        received_at=datetime(2026, 9, 10, 6, 27, tzinfo=timezone.utc),
        text=CONTOH,
    )

    for t in parse(email):
        print(f"{t.gmail_id:<12} {t.at:%d/%m %H:%M} {t.direction:<4} "
              f"Rp{t.amount:>12,.2f}  {t.kind:<10} {t.counterparty}"
              + ("  [rek sendiri]" if t.self_transfer else ""))
    print()
    print(to_message(parse(email)))
