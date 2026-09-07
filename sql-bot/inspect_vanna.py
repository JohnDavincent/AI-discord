"""Baca API Vanna dari paket yang BENAR-BENAR terpasang.

Dokumentasi web sering tertinggal dari paketnya. Daripada menebak nama method
lalu menghabiskan waktu pada AttributeError, kita baca langsung sumbernya.

Jalankan:  .\.venv\Scripts\python.exe inspect_vanna.py
"""

import inspect
import pkgutil


def judul(teks):
    print(f"\n{'=' * 70}\n{teks}\n{'=' * 70}")


def aman(label, fn):
    """Jalankan satu pemeriksaan; kegagalan satu bagian tidak menghentikan sisanya."""
    try:
        fn()
    except Exception as e:
        print(f"  [{label}] GAGAL: {type(e).__name__}: {e}")


# ---------------------------------------------------------------- versi
judul("1. VERSI")


def _versi():
    import vanna
    print("  vanna     :", getattr(vanna, "__version__", "(tidak ada __version__)"))
    print("  lokasi    :", vanna.__file__)
    print("  isi paket :", [n for n in dir(vanna) if not n.startswith("_")])


aman("versi", _versi)


# ------------------------------------------------------- entry point agent
judul("2. Agent.send_message  <- cara memanggil tanpa server")


def _agent():
    from vanna import Agent
    print("  send_message:", inspect.signature(Agent.send_message))
    print()
    print("  method publik Agent:")
    for nama, _ in inspect.getmembers(Agent, inspect.isfunction):
        if not nama.startswith("_"):
            print(f"    - {nama}{inspect.signature(getattr(Agent, nama))}")
    print()
    print("  __init__:", inspect.signature(Agent.__init__))


aman("agent", _agent)


# ------------------------------------------------------------ integrasi LLM
judul("3. INTEGRASI  <- cari yang bisa dipakai untuk DeepSeek")


def _integrasi():
    import vanna.integrations
    modul = sorted(m.name for m in pkgutil.iter_modules(vanna.integrations.__path__))
    print("  tersedia:", modul)
    print()
    for kandidat in ("openai", "deepseek", "ollama", "anthropic"):
        if kandidat in modul:
            print(f"  --- vanna.integrations.{kandidat} ---")
            mod = __import__(f"vanna.integrations.{kandidat}", fromlist=["*"])
            for nama in dir(mod):
                if nama.startswith("_"):
                    continue
                obj = getattr(mod, nama)
                if inspect.isclass(obj):
                    try:
                        print(f"    {nama}{inspect.signature(obj.__init__)}")
                    except (TypeError, ValueError):
                        print(f"    {nama}")


aman("integrasi", _integrasi)


# --------------------------------------------------------- RequestContext
judul("4. RequestContext + User  <- yang harus diisi saat memanggil")


def _konteks():
    from vanna.core import user as mod_user
    for nama in ("RequestContext", "User", "UserResolver"):
        obj = getattr(mod_user, nama, None)
        if obj is None:
            continue
        print(f"  --- {nama} ---")
        try:
            print(inspect.getsource(obj))
        except OSError:
            print("   ", inspect.signature(obj))


aman("konteks", _konteks)


# ------------------------------------------------------------ UiComponent
judul("5. UiComponent  <- bentuk yang di-yield send_message")


def _ui():
    import importlib
    for jalur in ("vanna.core.ui", "vanna.core.components", "vanna.core.types"):
        try:
            mod = importlib.import_module(jalur)
        except ImportError:
            continue
        print(f"  --- {jalur} ---")
        for nama in dir(mod):
            if not nama.startswith("_") and inspect.isclass(getattr(mod, nama)):
                print("   ", nama)


aman("ui", _ui)


# ----------------------------------------------------------------- tools
judul("6. TOOLS + MEMORY")


def _tools():
    import vanna.tools
    print("  vanna.tools:", [n for n in dir(vanna.tools) if not n.startswith("_")])

    from vanna.tools import RunSqlTool
    print("  RunSqlTool.__init__:", inspect.signature(RunSqlTool.__init__))

    from vanna.integrations.postgres import PostgresRunner
    print("  PostgresRunner.__init__:", inspect.signature(PostgresRunner.__init__))

    import vanna.integrations.local as lokal
    print("  integrations.local:", sorted(m.name for m in pkgutil.iter_modules(lokal.__path__)))


aman("tools", _tools)

print("\nSelesai.\n")
