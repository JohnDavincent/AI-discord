"""Tombol konfirmasi di bawah struk: simpan atau minta tafsiran ulang."""

import logging

import discord

from handler import commit, regenerate
from receipt import build_embed

log = logging.getLogger(__name__)

MAX_ATTEMPT = 4     # batas 'catat ulang' supaya tidak boros token


class ConfirmView(discord.ui.View):
    def __init__(self, draft, author_id: int, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.draft = draft
        self.author_id = author_id
        self.message = None     # diisi bot.py, dipakai saat on_timeout

    # --- util -------------------------------------------------------------
    def _lock(self, value: bool):
        for item in self.children:
            item.disabled = value

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Ini catatan punya orang lain 🙂", ephemeral=True
            )
            return False
        return True

    # --- tombol -----------------------------------------------------------
    @discord.ui.button(label="Oke, simpan", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Interaksi wajib dijawab dalam 3 detik; simpan ke DB bisa lebih lama.
        await interaction.response.defer()
        try:
            await commit(self.draft)
        except Exception:
            log.exception("gagal menyimpan transaksi")
            await interaction.followup.send(
                "Gagal disimpan, coba tekan Oke sekali lagi.", ephemeral=True
            )
            return

        self._lock(True)
        await interaction.edit_original_response(
            content=self.draft.reply[:1900],
            embed=build_embed(self.draft, "saved"),
            view=self,
        )
        self.stop()

    @discord.ui.button(label="Catat ulang", style=discord.ButtonStyle.secondary, emoji="🔁")
    async def retry(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.draft.attempt >= MAX_ATTEMPT:
            await interaction.response.send_message(
                "Sudah beberapa kali dicoba dan masih meleset. "
                "Coba kirim ulang pesannya dengan lebih detail ya.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        # Kunci tombol selama AI bekerja supaya klik dobel tidak jalan dua kali.
        self._lock(True)
        await interaction.edit_original_response(
            content="🔁 Sebentar, saya tafsirkan ulang…", view=self
        )

        try:
            self.draft = await regenerate(self.draft)
        except Exception:
            log.exception("gagal generate ulang")
            self._lock(False)
            await interaction.edit_original_response(
                content="Baik, saya buatkan dulu catatan transaksinya 👇", view=self
            )
            await interaction.followup.send(
                "AI-nya lagi ngadat, draft yang lama saya biarkan dulu.", ephemeral=True
            )
            return

        self._lock(False)

        if not self.draft.transactions:
            # Tafsiran baru ternyata bukan transaksi sama sekali.
            self._lock(True)
            await interaction.edit_original_response(
                content=self.draft.reply[:1900], embed=None, view=self
            )
            self.stop()
            return

        await interaction.edit_original_response(
            content="Baik, ini versi barunya 👇",
            embed=build_embed(self.draft, "draft"),
            view=self,
        )

    # --- kedaluwarsa ------------------------------------------------------
    async def on_timeout(self):
        self._lock(True)
        if self.message is None or self.draft.saved:
            return
        try:
            await self.message.edit(
                content=None, embed=build_embed(self.draft, "expired"), view=self
            )
        except discord.HTTPException:
            log.warning("pesan draft sudah hilang saat timeout")
