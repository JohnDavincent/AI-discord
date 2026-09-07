from decimal import Decimal, InvalidOperation
from query_repository import SQL_PERIOD
VALID_TYPES = {"income","expense"}

VALID_CATEGORIES = {
    "makanan", "minuman", "transport", "belanja", "tagihan", "kos",
    "hiburan", "kesehatan", "pendidikan",
    "gaji", "bonus", "freelance", "penjualan", "lainnya",
}

QUERY_SHAPE = {"total","rata-rata","jumlah_transaksi","daftar"}
QUERY_PERIODE = set(SQL_PERIOD)      # impor dari query_repository — satu sumber kebenaran
QUERY_TIPE    = {"expense", "income", "semua"}


class ValidationError(ValueError):
    """Output AI tidak sesuai bentuk yang diharapkan."""

def validate(data) -> dict:
    if not isinstance(data,dict):
        raise ValidationError(f"root harus object, dapat {type(data).__name__}")

    items = data.get("transactions")
    if items is None :
        raise ValidationError("kunci 'transactions' tidak ada")
    if not isinstance(items, list):
        raise ValidationError("transactions harus array")
    
    reply = data.get("reply")
    if not isinstance(reply, str) or not reply.strip():
        raise ValidationError("'reply' kosong atau bukan string")
    
    query = data.get("query")
    if not isinstance(query,dict):
        raise ValidationError("'query' must be an object")
    
    if query.get("bentuk") not in QUERY_SHAPE:
            raise ValidationError(f"'bentuk' = {query.get('bentuk')!r} tidak dikenal")
    if query.get("periode") not in QUERY_PERIODE:
            raise ValidationError(f"'periode' = {query.get('periode')!r} tidak dikenal")
        

    result = []
    for i, obj in enumerate(items):
        if not isinstance(obj, dict):
            raise ValidationError(f"item ke-{i} bukan object")

        title = obj.get("title")
        if not isinstance(title,str) or not title.strip():
            raise ValidationError(f"item ke-{i}: 'title' kosong atau bukan string")

        transaction_type = obj.get("transaction_type")
        if transaction_type not in VALID_TYPES :
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
        except (KeyError, InvalidOperation):
            raise ValidationError(f"item ke-{i}: 'value' bukan angka yang sah")

        if value < 0:
            raise ValidationError(f"item ke-{i}: 'value' tidak boleh negatif")


        result.append({
            "title" : title.strip(),
            "transaction_type": transaction_type,
            "value": value,
            "category" : category,
            "description": obj.get("description")
        })

    return {"reply": reply.strip(), "transactions": result}