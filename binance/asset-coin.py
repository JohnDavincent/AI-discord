import os
import time
import hmac
import hashlib
import requests
from urllib.parse import urlencode
from dotenv import load_dotenv
load_dotenv() # baca .env

# api.binance.com diblokir dari Indonesia, jadi domainnya dibuat bisa diganti.
BASE_URL = os.getenv("BINANCE_BASE_URL", "https://testnet.binance.vision")

# load_dotenv() hanya mengisi os.environ, jadi nilainya masih perlu diambil.
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")

if not BINANCE_API_KEY or not BINANCE_SECRET_KEY:
    raise RuntimeError("BINANCE_API_KEY / BINANCE_SECRET_KEY belum diisi di .env")

def get_account_info():
    endpoint = "/api/v3/account"

    params = {
        "timestamp" : int(time.time() * 1000)
    }

    #Query String dari parameter
    query_string = urlencode(params)
    signature = hmac.new(
        BINANCE_SECRET_KEY.encode("utf-8"),
        query_string.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    params["signature"] = signature

    #Header
    headers = {
        "X-MBX-APIKEY": BINANCE_API_KEY
    }

    #Kirim get request ke binance
    try:
        response = requests.get(BASE_URL + endpoint, headers=headers, params=params, timeout=10)
    except requests.exceptions.ConnectionError:
        print(f"Tidak bisa menyambung ke {BASE_URL} - kemungkinan domainnya diblokir.")
        return None

    if response.status_code == 200:
        print("Success get data account")
        return response.json()

    else:
        print(f"Gagal {response.status_code} : ", response.text)
        return None


if __name__ == "__main__":
    data = get_account_info()
    if data:
        # Tampilkan hanya aset yang saldonya tidak nol.
        for balance in data["balances"]:
            if float(balance["free"]) > 0 or float(balance["locked"]) > 0:
                print(balance["asset"], balance["free"], balance["locked"])
