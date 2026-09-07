
import logging
from message_repository import save_message
from deepseek_client import parse_message, ParseFailed, answer_with_data
from transaction_repository import save_transactions
from query_repository import calculate_money


log = logging.getLogger(__name__)

async def handle(text, message_id, channel_id, created_at):
    await save_message(message_id, channel_id,text,created_at)

    try:
        result = await parse_message(text)
        if result.get("query"):
            try:
                rslt = await calculate_money(**result["query"])
                
            except Exception:
                log.exception("query gagal")
                rslt = "QUERY GAGAL"
                result = await answer_with_data(text, result, rslt)
                
    except ParseFailed:
        return ("Maaf, saya belum bisa membaca pesan itu. "
                "Coba tulis lebih terstruktur, contoh: `makan siang 25rb`")
        
    except Exception:
        log.exception("gagal memanggil AI")
        return "Sedang ada gangguan, coba lagi sebentar lagi."
    
    try:
        await save_transactions(result["transactions"],text, created_at)
    except Exception:
        log.exception("gagal menyimpan transaksi")
        return "Transaksinya gagal disimpan, coba lagi sebentar lagi."

    return result["reply"][:1900]


    
