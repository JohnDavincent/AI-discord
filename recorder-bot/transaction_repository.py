from db import pool

INSERT_SQL = """
    INSERT INTO transactions(
        title, description, transaction_type, category, value,
        raw_message, created_time, updated_time
    )
    VALUES ($1, $2, $3, $4, $5, $6, $7, $7)
    RETURNING id
"""

async def save_transactions(items, raw_message, created_time):
    """can save multiple transaction"""
    if not items:
        return []
    
    async with pool().acquire() as conn:
        async with conn.transaction():
            return[
                await conn.fetchval(
                    INSERT_SQL,
                    trx["title"],
                    trx["description"],
                    trx["transaction_type"],
                    trx["category"],
                    trx["value"],
                    raw_message,
                    created_time,
                )
                for trx in items
            ]