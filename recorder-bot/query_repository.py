from db import pool

SQL_PERIOD = {
    "hari_ini":   "created_time >= current_date",
    "kemarin":    "created_time >= current_date - interval '1 day' AND created_time < current_date",
    "7_hari":     "created_time >= current_date - interval '7 days'",
    "30_hari":    "created_time >= current_date - interval '30 days'",
    "bulan_ini":  "date_trunc('month', created_time) = date_trunc('month', current_date)",
    "bulan_lalu": "date_trunc('month', created_time) = date_trunc('month', current_date - interval '1 month')",
    "tahun_ini":  "date_trunc('year', created_time) = date_trunc('year', current_date)",
    "semua":      "TRUE",
}

AGREGAT_SQL = {
    "total":            "COALESCE(sum(value), 0)",
    "rata_rata":        "COALESCE(avg(value), 0)",
    "jumlah_transaksi": "count(*)",
}


async def calculate_money(shape, period, type ="semua", category=None, key=None):
    where = [SQL_PERIOD["period"]]
    params = []
    
    if type != "semua":
        params.append(type)
        where.append(f"transaction_type = ${len(params)}")
    
    if category:
        params.append(category)
        where.append(f"category = ${len(params)}")
    
    if key:
        params.append(f"%{key}")
        (f"(title ILIKE ${len(params)} OR raw_message ILIKE ${len(params)})")
        
    clausa = " AND ".join(where)
    
    async with pool().acquire() as conn:
        if shape == "daftar":
            rows = await conn.fetch(
                f"SELECT title, category, transaction_type, value, created_time "
                f"FROM transactions WHERE {clausa} "
                f"ORDER BY created_time DESC LIMIT 20",
                *params,
            )
            return [dict(r) for r in rows]

        return await conn.fetchval(
            f"SELECT {AGREGAT_SQL[shape]} FROM transactions WHERE {clausa}",
            *params,
        )
