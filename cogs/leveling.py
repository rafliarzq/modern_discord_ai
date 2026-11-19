
import sqlite3
import random
import logging
import time
from pathlib import Path

import discord
from discord.ext import commands
from discord import app_commands

log = logging.getLogger("PelayanSFC.Leveling")

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "leveling.db"

XP_COOLDOWN = 60
DEFAULT_XP_MIN = 15
DEFAULT_XP_MAX = 25


def calculate_level(total_xp):
    level = 0
    remaining = total_xp

    while True:
        required = 100 + (level * 50)

        if remaining < required:
            break

        remaining -= required
        level += 1

    return level, remaining, 100 + (level * 50)


class Leveling(commands.Cog):

    level_reward = app_commands.Group(
        name="level-reward",
        description="Atur hadiah role berdasarkan level."
    )

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(DB_PATH) as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS leveling (
                    guild_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    total_xp INTEGER NOT NULL DEFAULT 0,
                    last_xp_at REAL NOT NULL DEFAULT 0,
                    PRIMARY KEY (guild_id, user_id)
                )
            """)

            db.execute("""
                CREATE TABLE IF NOT EXISTS leveling_settings (
                    guild_id INTEGER PRIMARY KEY,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    channel_id INTEGER,
                    xp_min INTEGER NOT NULL DEFAULT 15,
                    xp_max INTEGER NOT NULL DEFAULT 25
                )
            """)

            db.execute("""
                CREATE TABLE IF NOT EXISTS leveling_rewards (
                    guild_id INTEGER NOT NULL,
                    level INTEGER NOT NULL,
                    role_id INTEGER NOT NULL,
                    PRIMARY KEY (guild_id, level)
                )
            """)

        log.info("Leveling database initialized")

    def get_settings(self, guild_id):
        with sqlite3.connect(DB_PATH) as db:
            db.execute("""
                INSERT OR IGNORE INTO leveling_settings (guild_id)
                VALUES (?)
            """, (guild_id,))

            row = db.execute("""
                SELECT enabled, channel_id, xp_min, xp_max
                FROM leveling_settings
                WHERE guild_id = ?
            """, (guild_id,)).fetchone()

        return row

    def add_xp(self, guild_id, user_id):
        now = time.time()
        enabled, channel_id, xp_min, xp_max = self.get_settings(guild_id)

        if not enabled:
            return None

        with sqlite3.connect(DB_PATH) as db:
            db.execute("""
                INSERT OR IGNORE INTO leveling
                (guild_id, user_id, total_xp, last_xp_at)
                VALUES (?, ?, 0, 0)
            """, (guild_id, user_id))

            row = db.execute("""
                SELECT total_xp, last_xp_at
                FROM leveling
                WHERE guild_id = ? AND user_id = ?
            """, (guild_id, user_id)).fetchone()

            old_xp, last_xp = row

            if now - last_xp < XP_COOLDOWN:
                return None

            old_level = calculate_level(old_xp)[0]
            gained = random.randint(xp_min, xp_max)
            new_xp = old_xp + gained
            new_level = calculate_level(new_xp)[0]

            db.execute("""
                UPDATE leveling
                SET total_xp = ?, last_xp_at = ?
                WHERE guild_id = ? AND user_id = ?
            """, (new_xp, now, guild_id, user_id))

        return gained, new_xp, old_level, new_level, channel_id

    def get_stats(self, guild_id, user_id):
        with sqlite3.connect(DB_PATH) as db:
            return db.execute("""
                SELECT total_xp
                FROM leveling
                WHERE guild_id = ? AND user_id = ?
            """, (guild_id, user_id)).fetchone()

    async def give_level_rewards(self, member, old_level, new_level):
        with sqlite3.connect(DB_PATH) as db:
            rows = db.execute("""
                SELECT role_id
                FROM leveling_rewards
                WHERE guild_id = ? AND level > ? AND level <= ?
            """, (member.guild.id, old_level, new_level)).fetchall()

        for (role_id,) in rows:
            role = member.guild.get_role(role_id)

            if role is None:
                continue

            if role in member.roles:
                continue

            try:
                await member.add_roles(
                    role,
                    reason="Level reward - Pelayan SFC"
                )
            except discord.Forbidden:
                log.warning(
                    "Cannot assign reward role %s in guild %s",
                    role_id,
                    member.guild.id
                )
            except discord.HTTPException:
                log.exception("Failed to assign level reward")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.guild is None:
            return

        result = self.add_xp(
            message.guild.id,
            message.author.id
        )

        if result is None:
            return

        gained, total_xp, old_level, new_level, channel_id = result

        if new_level > old_level:
            await self.give_level_rewards(
                message.author,
                old_level,
                new_level
            )

            embed = discord.Embed(
                title="🎉 LEVEL UP!",
                description=(
                    f"Selamat {message.author.mention}!\n"
                    f"Kamu naik ke **Level {new_level}**!"
                ),
                color=discord.Color.gold()
            )

            embed.add_field(
                name="XP Diperoleh",
                value=f"+{gained} XP",
                inline=True
            )

            embed.add_field(
                name="Total XP",
                value=f"{total_xp:,} XP",
                inline=True
            )

            embed.set_thumbnail(
                url=message.author.display_avatar.url
            )

            channel = (
                message.guild.get_channel(channel_id)
                if channel_id else None
            )

            if channel is None:
                channel = message.channel

            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                log.warning("Cannot send level-up announcement")

        log.debug(
            "%s gained %s XP in guild %s",
            message.author.id,
            gained,
            message.guild.id
        )

    # =========================
    # RANK
    # =========================

    @app_commands.command(
        name="rank",
        description="Lihat level dan XP member."
    )
    @app_commands.describe(
        member="Member yang ingin diperiksa."
    )
    @app_commands.guild_only()
    async def rank(
        self,
        interaction: discord.Interaction,
        member: discord.Member = None
    ):
        member = member or interaction.user

        stats = self.get_stats(
            interaction.guild_id,
            member.id
        )

        total_xp = stats[0] if stats else 0
        level, current_xp, required_xp = calculate_level(total_xp)
        progress = int(current_xp / required_xp * 100)

        embed = discord.Embed(
            title=f"🏆 Rank - {member.display_name}",
            color=discord.Color.blurple()
        )

        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Level", value=f"**{level}**", inline=True)
        embed.add_field(name="Total XP", value=f"**{total_xp:,}**", inline=True)
        embed.add_field(
            name="Progress",
            value=f"`{current_xp}/{required_xp} XP`\n**{progress}%**",
            inline=False
        )
        embed.set_footer(text="Pelayan SFC Leveling System")

        await interaction.response.send_message(embed=embed)

    # =========================
    # LEADERBOARD
    # =========================

    @app_commands.command(
        name="leaderboard",
        description="Lihat 10 member dengan XP tertinggi."
    )
    @app_commands.guild_only()
    async def leaderboard(self, interaction: discord.Interaction):
        with sqlite3.connect(DB_PATH) as db:
            rows = db.execute("""
                SELECT user_id, total_xp
                FROM leveling
                WHERE guild_id = ?
                ORDER BY total_xp DESC, user_id ASC
                LIMIT 10
            """, (interaction.guild_id,)).fetchall()

        if not rows:
            await interaction.response.send_message(
                "Belum ada data XP di server ini.",
                ephemeral=True
            )
            return

        lines = []

        for position, (user_id, total_xp) in enumerate(rows, start=1):
            level = calculate_level(total_xp)[0]
            lines.append(
                f"**{position}.** <@{user_id}> — "
                f"Level **{level}** · {total_xp:,} XP"
            )

        embed = discord.Embed(
            title="🏆 Server Leaderboard",
            description="\n".join(lines),
            color=discord.Color.gold()
        )

        embed.set_footer(text="Pelayan SFC Leveling System")
        await interaction.response.send_message(embed=embed)

    # =========================
    # LEVEL CHANNEL
    # =========================

    @app_commands.command(
        name="level-channel",
        description="Atur channel pengumuman level-up."
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def level_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):
        with sqlite3.connect(DB_PATH) as db:
            db.execute("""
                UPDATE leveling_settings
                SET channel_id = ?
                WHERE guild_id = ?
            """, (channel.id, interaction.guild_id))

        await interaction.response.send_message(
            f"Pengumuman level-up sekarang dikirim ke {channel.mention}.",
            ephemeral=True
        )

    # =========================
    # LEVEL TOGGLE
    # =========================

    @app_commands.command(
        name="level-toggle",
        description="Aktifkan atau nonaktifkan sistem XP."
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def level_toggle(
        self,
        interaction: discord.Interaction,
        enabled: bool
    ):
        with sqlite3.connect(DB_PATH) as db:
            db.execute("""
                UPDATE leveling_settings
                SET enabled = ?
                WHERE guild_id = ?
            """, (int(enabled), interaction.guild_id))

        status = "diaktifkan" if enabled else "dinonaktifkan"

        await interaction.response.send_message(
            f"Sistem leveling berhasil **{status}**.",
            ephemeral=True
        )

    # =========================
    # XP CONFIGURATION
    # =========================

    @app_commands.command(
        name="level-xp",
        description="Atur jumlah XP yang diperoleh setiap pesan."
    )
    @app_commands.guild_only()
    @app_commands.checks.has_permissions(manage_guild=True)
    async def level_xp(
        self,
        interaction: discord.Interaction,
        minimum: app_commands.Range[int, 1, 500],
        maximum: app_commands.Range[int, 1, 500]
    ):
        if minimum > maximum:
            await interaction.response.send_message(
                "XP minimum tidak boleh lebih besar dari XP maksimum.",
                ephemeral=True
            )
            return

        with sqlite3.connect(DB_PATH) as db:
            db.execute("""
                UPDATE leveling_settings
                SET xp_min = ?, xp_max = ?
                WHERE guild_id = ?
            """, (minimum, maximum, interaction.guild_id))

        await interaction.response.send_message(
            f"Pengaturan XP diperbarui: **{minimum}–{maximum} XP** per pesan.",
            ephemeral=True
        )

    # =========================
    # LEVEL REWARD ADD
    # =========================

    @level_reward.command(
        name="add",
        description="Tambahkan hadiah role pada level tertentu."
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def reward_add(
        self,
        interaction: discord.Interaction,
        level: app_commands.Range[int, 1, 1000],
        role: discord.Role
    ):
        if role.is_default() or role.managed:
            await interaction.response.send_message(
                "Role tersebut tidak bisa digunakan sebagai hadiah.",
                ephemeral=True
            )
            return

        if role >= interaction.guild.me.top_role:
            await interaction.response.send_message(
                "Posisi role hadiah harus berada di bawah role tertinggi bot.",
                ephemeral=True
            )
            return

        with sqlite3.connect(DB_PATH) as db:
            db.execute("""
                INSERT INTO leveling_rewards (guild_id, level, role_id)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id, level)
                DO UPDATE SET role_id = excluded.role_id
            """, (interaction.guild_id, level, role.id))

        await interaction.response.send_message(
            f"Hadiah level **{level}** diatur menjadi {role.mention}.",
            ephemeral=True
        )

    # =========================
    # LEVEL REWARD REMOVE
    # =========================

    @level_reward.command(
        name="remove",
        description="Hapus hadiah role dari level tertentu."
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def reward_remove(
        self,
        interaction: discord.Interaction,
        level: app_commands.Range[int, 1, 1000]
    ):
        with sqlite3.connect(DB_PATH) as db:
            cursor = db.execute("""
                DELETE FROM leveling_rewards
                WHERE guild_id = ? AND level = ?
            """, (interaction.guild_id, level))

        if cursor.rowcount == 0:
            await interaction.response.send_message(
                f"Tidak ada hadiah untuk level {level}.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"Hadiah level **{level}** berhasil dihapus.",
            ephemeral=True
        )

    # =========================
    # LEVEL REWARD LIST
    # =========================

    @level_reward.command(
        name="list",
        description="Lihat semua hadiah role leveling."
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def reward_list(self, interaction: discord.Interaction):
        with sqlite3.connect(DB_PATH) as db:
            rows = db.execute("""
                SELECT level, role_id
                FROM leveling_rewards
                WHERE guild_id = ?
                ORDER BY level ASC
            """, (interaction.guild_id,)).fetchall()

        if not rows:
            await interaction.response.send_message(
                "Belum ada hadiah role yang diatur.",
                ephemeral=True
            )
            return

        lines = []

        for level, role_id in rows:
            role = interaction.guild.get_role(role_id)
            role_text = role.mention if role else f"Role terhapus ({role_id})"
            lines.append(f"Level **{level}** → {role_text}")

        embed = discord.Embed(
            title="🎁 Level Rewards",
            description="\n".join(lines),
            color=discord.Color.gold()
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Leveling(bot))
