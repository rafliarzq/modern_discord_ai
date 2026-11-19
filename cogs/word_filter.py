
import sqlite3
import logging
import re
from pathlib import Path

import discord
from discord.ext import commands
from discord import app_commands

log = logging.getLogger("PelayanSFC.WordFilter")

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "word_filter.db"


class WordFilter(commands.Cog):

    filter_group = app_commands.Group(
        name="filter",
        description="Pengaturan sensor kata otomatis."
    )

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(DB_PATH) as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS filtered_words (
                    guild_id INTEGER NOT NULL,
                    word TEXT NOT NULL,
                    PRIMARY KEY (guild_id, word)
                )
            """)

            db.execute("""
                CREATE TABLE IF NOT EXISTS filter_settings (
                    guild_id INTEGER PRIMARY KEY,
                    enabled INTEGER NOT NULL DEFAULT 1
                )
            """)

        log.info("Word Filter database initialized")

    def get_settings(self, guild_id):
        with sqlite3.connect(DB_PATH) as db:
            db.execute("""
                INSERT OR IGNORE INTO filter_settings (guild_id)
                VALUES (?)
            """, (guild_id,))

            row = db.execute("""
                SELECT enabled FROM filter_settings
                WHERE guild_id = ?
            """, (guild_id,)).fetchone()

        return bool(row[0])

    def get_words(self, guild_id):
        with sqlite3.connect(DB_PATH) as db:
            rows = db.execute("""
                SELECT word FROM filtered_words
                WHERE guild_id = ?
                ORDER BY word ASC
            """, (guild_id,)).fetchall()

        return [row[0] for row in rows]

    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author.bot or message.guild is None:
            return

        if not message.content:
            return

        if not self.get_settings(message.guild.id):
            return

        words = self.get_words(message.guild.id)

        if not words:
            return

        content = message.content.casefold()

        for word in words:
            pattern = (
                r"(?<!\w)"
                + re.escape(word.casefold())
                + r"(?!\w)"
            )

            if re.search(pattern, content):
                try:
                    await message.delete()

                    log.info(
                        "Deleted filtered message from %s in guild %s",
                        message.author.id,
                        message.guild.id
                    )

                except discord.NotFound:
                    pass

                except discord.Forbidden:
                    log.warning(
                        "Missing Manage Messages permission in guild %s",
                        message.guild.id
                    )

                except discord.HTTPException:
                    log.exception("Failed to delete filtered message")

                return

    # =========================
    # ADD WORD
    # =========================

    @filter_group.command(
        name="add",
        description="Tambahkan kata ke daftar sensor."
    )
    async def filter_add(
        self,
        interaction: discord.Interaction,
        word: app_commands.Range[str, 1, 100]
    ):

        word = word.strip()

        if not word:
            await interaction.response.send_message(
                "Kata tidak boleh kosong.",
                ephemeral=True
            )
            return

        with sqlite3.connect(DB_PATH) as db:
            cursor = db.execute("""
                INSERT OR IGNORE INTO filtered_words
                (guild_id, word)
                VALUES (?, ?)
            """, (interaction.guild_id, word))

        if cursor.rowcount == 0:
            await interaction.response.send_message(
                f"`{word}` sudah ada di daftar sensor.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"✅ Kata `{word}` berhasil ditambahkan ke daftar sensor.",
            ephemeral=True
        )

    # =========================
    # REMOVE WORD
    # =========================

    @filter_group.command(
        name="remove",
        description="Hapus kata dari daftar sensor."
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def filter_remove(
        self,
        interaction: discord.Interaction,
        word: app_commands.Range[str, 1, 100]
    ):

        with sqlite3.connect(DB_PATH) as db:
            cursor = db.execute("""
                DELETE FROM filtered_words
                WHERE guild_id = ? AND word = ?
            """, (interaction.guild_id, word.strip()))

        if cursor.rowcount == 0:
            await interaction.response.send_message(
                f"Kata `{word}` tidak ditemukan.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"✅ Kata `{word}` berhasil dihapus dari daftar sensor.",
            ephemeral=True
        )

    # =========================
    # LIST WORDS
    # =========================

    @filter_group.command(
        name="list",
        description="Lihat semua kata yang disensor."
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def filter_list(
        self,
        interaction: discord.Interaction
    ):

        words = self.get_words(interaction.guild_id)

        if not words:
            await interaction.response.send_message(
                "Daftar sensor masih kosong.",
                ephemeral=True
            )
            return

        description = "\n".join(
            f"**{index}.** `{word}`"
            for index, word in enumerate(words[:50], start=1)
        )

        if len(words) > 50:
            description += f"\n\nDan {len(words) - 50} kata lainnya."

        embed = discord.Embed(
            title="🛡️ Word Filter List",
            description=description,
            color=discord.Color.red()
        )

        embed.set_footer(text=f"Total kata: {len(words)}")

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    # =========================
    # TOGGLE FILTER
    # =========================

    @filter_group.command(
        name="toggle",
        description="Aktifkan atau nonaktifkan sensor kata."
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def filter_toggle(
        self,
        interaction: discord.Interaction,
        enabled: bool
    ):

        with sqlite3.connect(DB_PATH) as db:
            db.execute("""
                INSERT INTO filter_settings (guild_id, enabled)
                VALUES (?, ?)
                ON CONFLICT(guild_id)
                DO UPDATE SET enabled = excluded.enabled
            """, (interaction.guild_id, int(enabled)))

        status = "diaktifkan" if enabled else "dinonaktifkan"

        await interaction.response.send_message(
            f"🛡️ Word Filter berhasil **{status}**.",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(WordFilter(bot))
