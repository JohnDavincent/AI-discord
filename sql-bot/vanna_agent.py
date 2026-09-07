"""Agent Vanna untuk menjawab pertanyaan tentang database keuangan.

Dipakai oleh bot.py. Sengaja TIDAK memakai VannaFastAPIServer - Discord
sudah jadi UI-nya, jadi kita panggil agent.send_message() langsung.
"""

import os

from dotenv import load_dotenv

load_dotenv()

from vanna import Agent, AgentConfig, ToolRegistry
from vanna.core.user import RequestContext, User, UserResolver
from vanna.integrations.local.agent_memory import DemoAgentMemory
from vanna.integrations.local.file_system_conversation_store import (
    FileSystemConversationStore,
)
from vanna.integrations.openai import OpenAILlmService
from vanna.integrations.postgres import PostgresRunner
from vanna.tools import RunSqlTool

# Grup ini harus cocok dengan access_groups di register_local_tool().
GRUP = "analysts"


class DiscordUserResolver(UserResolver):
    """Ganti CookieEmailUserResolver - identitas datang dari Discord, bukan cookie.

    bot.py menaruh info Discord di RequestContext.metadata.
    """

    async def resolve_user(self, request_context: RequestContext) -> User:
        meta = request_context.metadata
        return User(
            id=str(meta.get("discord_user_id", "unknown")),
            username=meta.get("discord_username", "unknown"),
            group_memberships=[GRUP],
        )


def konteks_discord(user_id, username) -> RequestContext:
    """Bentuk RequestContext dari sebuah pesan Discord."""
    return RequestContext(
        metadata={"discord_user_id": str(user_id), "discord_username": str(username)}
    )


def build_agent() -> Agent:
    tools = ToolRegistry()
    tools.register_local_tool(
        RunSqlTool(
            sql_runner=PostgresRunner(
                host=os.getenv("PGHOST"),
                port=int(os.getenv("PGPORT", "5432")),
                database=os.getenv("PGDATABASE"),
                # HANYA role read-only. Postgres yang menolak operasi tulis,
                # bukan kode kita - ini batas keamanan yang sebenarnya.
                user=os.getenv("PGUSER_RO"),
                password=os.getenv("PGPASSWORD_RO"),
            )
        ),
        access_groups=[GRUP],
    )

    return Agent(
        llm_service=OpenAILlmService(
            # DeepSeek kompatibel-OpenAI, jadi cukup ganti base_url.
            model="deepseek-v4-pro",
            api_key=os.getenv("DEEPSEEK_API"),
            base_url="https://api.deepseek.com",
        ),
        tool_registry=tools,
        user_resolver=DiscordUserResolver(),
        # Tool Memory: belajar dari SQL yang berhasil. Sayangnya versi lokal
        # ini di memori saja - hilang saat bot restart.
        agent_memory=DemoAgentMemory(max_items=10000),
        # Histori percakapan disimpan ke disk supaya tidak hilang saat restart.
        conversation_store=FileSystemConversationStore(base_dir="conversations"),
        # temperature 0 - untuk SQL kita mau patuh, bukan kreatif.
        # Default AgentConfig adalah 0.7, terlalu tinggi untuk ini.
        config=AgentConfig(temperature=0),
    )
