
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

import discord
from discord.ext import commands
from discord import app_commands

log = logging.getLogger("PelayanSFC.AuditLogger")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CONFIG_FILE = DATA_DIR / "audit_log.json"


class AuditLogger(commands.Cog):
    auditlog = app_commands.Group(
        name="auditlog",
        description="Pengaturan server audit logger"
    )

    def __init__(self, bot):
        self.bot = bot
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        if CONFIG_FILE.exists():
            try:
                self.config = json.loads(
                    CONFIG_FILE.read_text(encoding="utf-8")
                )
            except (json.JSONDecodeError, OSError):
                self.config = {}
        else:
            self.config = {}

    def save_config(self):
        CONFIG_FILE.write_text(
            json.dumps(self.config, indent=4),
            encoding="utf-8"
        )

    def get_channel(self, guild):
        channel_id = self.config.get(str(guild.id))
        if not channel_id:
            return None

        return guild.get_channel(int(channel_id))

    async def find_audit_entry(self, guild, actions, target_id):
        try:
            now = datetime.now(timezone.utc)

            for action in actions:
                async for entry in guild.audit_logs(
                    limit=10, action=action
                ):
                    target = getattr(entry.target, "id", None)

                    if target != target_id:
                        continue

                    age = (now - entry.created_at).total_seconds()

                    if 0 <= age <= 30:
                        return entry

        except discord.Forbidden:
            log.warning("Bot tidak memiliki izin View Audit Log")
        except discord.HTTPException:
            log.exception("Gagal membaca audit log")

        return None

    async def send_log(self, guild, title, target, actions):
        channel = self.get_channel(guild)

        if channel is None:
            return

        entry = await self.find_audit_entry(
            guild, actions, target.id
        )

        actor = (
            entry.user.mention
            if entry and entry.user
            else "Tidak diketahui"
        )

        embed = discord.Embed(
            title=f"📋 {title}",
            color=discord.Color.orange(),
            timestamp=datetime.now(timezone.utc)
        )

        embed.add_field(
            name="Pelaku",
            value=actor,
            inline=True
        )

        embed.add_field(
            name="Target",
            value=f"{target} (`{target.id}`)",
            inline=True
        )

        if entry and entry.reason:
            embed.add_field(
                name="Alasan",
                value=entry.reason[:1024],
                inline=False
            )

        if entry:
            changes = []

            for change in entry.changes:
                before = str(change.before)
                after = str(change.after)

                changes.append(
                    f"**{change.attribute}**\n"
                    f"Sebelum: `{before[:200]}`\n"
                    f"Sesudah: `{after[:200]}`"
                )

            if changes:
                embed.add_field(
                    name="Detail Perubahan",
                    value="\n\n".join(changes)[:1024],
                    inline=False
                )

        embed.set_footer(text=f"Server: {guild.name}")

        try:
            await channel.send(
                embed=embed,
                allowed_mentions=discord.AllowedMentions.none()
            )
        except discord.HTTPException:
            log.exception("Gagal mengirim audit log")

    # =========================
    # CONFIGURATION
    # =========================

    @auditlog.command(
        name="set",
        description="Atur channel untuk audit log"
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(channel="Channel tujuan laporan")
    async def set_log(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):
        self.config[str(interaction.guild_id)] = channel.id
        self.save_config()

        await interaction.response.send_message(
            f"✅ Audit log berhasil diaktifkan di {channel.mention}",
            ephemeral=True
        )

    @auditlog.command(
        name="off",
        description="Nonaktifkan audit log"
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def disable_log(self, interaction: discord.Interaction):
        self.config.pop(str(interaction.guild_id), None)
        self.save_config()

        await interaction.response.send_message(
            "✅ Audit log berhasil dinonaktifkan.",
            ephemeral=True
        )

    # =========================
    # CHANNEL EVENTS
    # =========================

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        await self.send_log(
            channel.guild, "Channel Dibuat", channel,
            [discord.AuditLogAction.channel_create]
        )

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        await self.send_log(
            channel.guild, "Channel Dihapus", channel,
            [discord.AuditLogAction.channel_delete]
        )

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        await self.send_log(
            after.guild, "Channel Diperbarui", after,
            [discord.AuditLogAction.channel_update]
        )

    # =========================
    # ROLE EVENTS
    # =========================

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        await self.send_log(
            role.guild, "Role Dibuat", role,
            [discord.AuditLogAction.role_create]
        )

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        await self.send_log(
            role.guild, "Role Dihapus", role,
            [discord.AuditLogAction.role_delete]
        )

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        await self.send_log(
            after.guild, "Role Diperbarui", after,
            [discord.AuditLogAction.role_update]
        )

    # =========================
    # SERVER EVENTS
    # =========================

    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        await self.send_log(
            after, "Pengaturan Server Diperbarui", after,
            [discord.AuditLogAction.guild_update]
        )

    # =========================
    # MEMBER EVENTS
    # =========================

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        await self.send_log(
            after.guild, "Anggota Diperbarui", after,
            [
                discord.AuditLogAction.member_role_update,
                discord.AuditLogAction.member_update
            ]
        )

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        await self.send_log(
            guild, "Anggota Di-ban", user,
            [discord.AuditLogAction.ban]
        )

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        await self.send_log(
            guild, "Anggota Di-unban", user,
            [discord.AuditLogAction.unban]
        )


async def setup(bot):
    await bot.add_cog(AuditLogger(bot))
