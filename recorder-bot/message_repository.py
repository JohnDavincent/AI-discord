from db import pool

async def save_message(discord_message_id, channel_id, context, created_time):
    async with pool().acquire() as conn:
        return await conn.fetchval(
            """
            INSERT INTO agent_messages(
                channel_id, discord_message_id, context, created_time, updated_time
            )
            VALUES ($1, $2, $3, $4, $4)
            RETURNING id
            """,
            str(channel_id),discord_message_id, context,created_time,
        )