from decimal import Decimal, InvalidOperation

from query_repository import SQL_PERIOD, AGREGAT_SQL

VALID_TYPES = {"income", "expense"}

VALID_CATEGORIES = {
    "makanan", "minuman", "transport", "belanja", "tagihan", "kos",
    "hiburan", "kesehatan", "pendidikan",
    "gaji", "bonus", "freelance", "penjualan", "lainnya",
}

# Satu sumber kebenaran: bentuk & periode ikut apa yang benar-benar bisa dijalankan SQL.
QUERY_SHAPE   = set(AGREGAT_SQL) | {"daftar"}
QUERY_PERIODE = set(SQL_PERIOD)
QUERY_TIPE    = {"expense", "income", "semua"}


class ValidationError(ValueError):
    """Output AI tidak sesuai bentuk yang diharapkan."""


def _validate_query(query):
    """None -> None. Object -> kwargs siap pakai untuk calculate_money().

    Kunci dari AI berbahasa Indonesia (bentuk/periode/tipe/kategori/kata_kunci),
    di sini diterjemahkan ke nama parameter calculate_money().
    """
    if query is None:
        return None
    if not isinstance(query, dict):
        raise ValidationError(f"'query' harus object atau null, dapat {type(query).__name__}")

    shape = query.get("bentuk")
    if shape not in QUERY_SHAPE:
        raise ValidationError(f"'bentuk' = {shape!r} tidak dikenal")

    period = query.get("periode")
    if period not in QUERY_PERIODE:
        raise ValidationError(f"'periode' = {period!r} tidak dikenal")

    tx_type = query.get("tipe") or "semua"
    if tx_type not in QUERY_TIPE:
        raise ValidationError(f"'tipe' = {tx_type!r} tidak dikenal")

    category = query.get("kategori")
    if category is not None and category not in VALID_CATEGORIES:
        raise ValidationError(f"'kategori' = {category!r} tidak ada di daftar kategori")

    keyword = query.get("kata_kunci")
    if keyword is not None and not isinstance(keyword, str):
        raise ValidationError("'kata_kunci' harus string atau null")

    return {
        "shape": shape,
        "period": period,
        "tx_type": tx_type,
        "category": category,
        "keyword": keyword.strip() if isinstance(keyword, str) and keyword.strip() else None,
    }


def validate(data) -> dict:
    if not isinstance(data, dict):
        raise ValidationError(f"root harus object, dapat {type(data).__name__}")

    items = data.get("transactions")
    if items is None:
        raise ValidationError("kunci 'transactions' tidak ada")
    if not isinstance(items, list):
        raise ValidationError("transactions harus array")

    reply = data.get("reply")
    if not isinstance(reply, str) or not reply.strip():
        raise ValidationError("'reply' kosong atau bukan string")

    query = _validate_query(data.get("query"))

    result = []
    for i, obj in enumerate(items):
        if not isinstance(obj, dict):
            raise ValidationError(f"item ke-{i} bukan object")

        title = obj.get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValidationError(f"item ke-{i}: 'title' kosong atau bukan string")

        transaction_type = obj.get("transaction_type")
        if transaction_type not in VALID_TYPES:
            raise ValidationError(
                f"item ke-{i}: 'transaction_type' = {transaction_type!r}, harus 'income' atau 'expense'"
            )

        category = obj.get("category")
        if category not in VALID_CATEGORIES:
            raise ValidationError(
                f"item ke-{i} : category = {category!r}, harus sesuai dengan VALID_CATEGORIES"
            )

        try:
            value = Decimal(str(obj["value"]))
        except (KeyError, InvalidOperation, TypeError):
            raise ValidationError(f"item ke-{i}: 'value' bukan angka yang sah")

        if value < 0:
            raise ValidationError(f"item ke-{i}: 'value' tidak boleh negatif")

        # Kolom value numeric(19,2) -> bulatkan di sini supaya error format
        # ketahuan sebelum menyentuh database.
        value = value.quantize(Decimal("0.01"))

        description = obj.get("description")
        if description is not None and not isinstance(description, str):
            description = str(description)

        result.append({
            "title": title.strip(),
            "transaction_type": transaction_type,
            "value": value,
            "category": category,
            "description": description,
        })

    return {"reply": reply.strip(), "transactions": result, "query": query}
