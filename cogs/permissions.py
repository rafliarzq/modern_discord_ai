
import sqlite3
from pathlib import Path

import discord
from discord.ext import commands
from discord import app_commands

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "permissions.db"


# Command yang secara default boleh digunakan semua member.
DEFAULT_USER_COMMANDS = {
    "help",
    "ai chat",
    "rank",
    "leaderboard",
    "level-reward list",
    "play",
    "pause",
    "resume",
    "skip",
    "queue",
    "stop",
}

DEFAULT_USER_ROOTS = {"games"}


def initialize_database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS access_settings (
                guild_id INTEGER PRIMARY KEY,
                admin_role_id INTEGER,
                user_role_id INTEGER
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS command_permissions (
                guild_id INTEGER NOT NULL,
                command_path TEXT NOT NULL,
                access TEXT NOT NULL,
                PRIMARY KEY (guild_id, command_path)
            )
        """)


def get_roles(guild_id):
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute("""
            SELECT admin_role_id, user_role_id
            FROM access_settings
            WHERE guild_id = ?
        """, (guild_id,)).fetchone()

    return row if row else (None, None)


def get_command_access(guild_id, command_path):
    with sqlite3.connect(DB_PATH) as db:
        row = db.execute("""
            SELECT access
            FROM command_permissions
            WHERE guild_id = ? AND command_path = ?
        """, (guild_id, command_path)).fetchone()

    if row:
        return row[0]

    if command_path in DEFAULT_USER_COMMANDS:
        return "user"

    root = command_path.split()[0]

    if root in DEFAULT_USER_ROOTS:
        return "user"

    # Command yang belum dikategorikan otomatis Admin.
    return "admin"


def has_admin_access(member, guild):
    if member.id == guild.owner_id:
        return True

    if (
        member.guild_permissions.administrator
        or member.guild_permissions.manage_guild
    ):
        return True

    admin_role_id, _ = get_roles(guild.id)

    if admin_role_id:
        return any(
            role.id == admin_role_id
            for role in member.roles
        )

    return False


def command_path_from_interaction(interaction):
    data = interaction.data

    if not isinstance(data, dict):
        return ""

    parts = []
    name = data.get("name")

    if name:
        parts.append(name)

    options = data.get("options", [])

    # Ambil nama subcommand, bukan parameter command.
    while isinstance(options, list):
        subcommand = next(
            (
                option for option in options
                if option.get("type") in (1, 2)
            ),
            None
        )

        if subcommand is None:
            break

        parts.append(subcommand["name"])
        options = subcommand.get("options", [])

    return " ".join(parts)


async def is_server_manager(interaction):
    if not interaction.guild or not isinstance(
        interaction.user, discord.Member
    ):
        return False

    member = interaction.user

    allowed = (
        member.id == interaction.guild.owner_id
        or member.guild_permissions.administrator
        or member.guild_permissions.manage_guild
    )

    if not allowed:
        await interaction.response.send_message(
            "❌ Hanya pemilik server atau pemegang izin Manage Server "
            "yang dapat mengubah pengaturan akses.",
            ephemeral=True
        )

    return allowed


class PermissionTree(app_commands.CommandTree):

    async def interaction_check(self, interaction):
        if interaction.guild is None:
            return False

        path = command_path_from_interaction(interaction)

        # Command pengaturan akses mempunyai pemeriksaan sendiri.
        if path == "access" or path.startswith("access "):
            return True

        if not isinstance(interaction.user, discord.Member):
            return False

        member = interaction.user
        guild = interaction.guild

        # Admin boleh menggunakan seluruh command.
        if has_admin_access(member, guild):
            return True

        access = get_command_access(guild.id, path)

        if access == "admin":
            await interaction.response.send_message(
                "⛔ Command ini khusus Admin.",
                ephemeral=True
            )
            return False

        # Jika role user sudah ditentukan, member harus memilikinya.
        _, user_role_id = get_roles(guild.id)

        if user_role_id:
            has_user_role = any(
                role.id == user_role_id
                for role in member.roles
            )

            if not has_user_role:
                await interaction.response.send_message(
                    "⛔ Kamu belum memiliki role User untuk menggunakan "
                    "command ini.",
                    ephemeral=True
                )
                return False

        return True


class Permissions(commands.Cog):

    access = app_commands.Group(
        name="access",
        description="Pengaturan akses command bot."
    )

    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        initialize_database()

    def save_role(self, guild_id, column, role_id):
        if column not in ("admin_role_id", "user_role_id"):
            raise ValueError("Invalid role column")

        with sqlite3.connect(DB_PATH) as db:
            db.execute("""
                INSERT OR IGNORE INTO access_settings (guild_id)
                VALUES (?)
            """, (guild_id,))

            db.execute(
                f"UPDATE access_settings SET {column} = ? "
                "WHERE guild_id = ?",
                (role_id, guild_id)
            )

    def save_command_access(self, guild_id, path, access):
        with sqlite3.connect(DB_PATH) as db:
            db.execute("""
                INSERT INTO command_permissions
                (guild_id, command_path, access)
                VALUES (?, ?, ?)
                ON CONFLICT(guild_id, command_path)
                DO UPDATE SET access = excluded.access
            """, (guild_id, path, access))

    def delete_command_access(self, guild_id, path):
        with sqlite3.connect(DB_PATH) as db:
            db.execute("""
                DELETE FROM command_permissions
                WHERE guild_id = ? AND command_path = ?
            """, (guild_id, path))

    @access.command(
        name="admin-role",
        description="Atur role khusus admin."
    )
    @app_commands.guild_only()
    @app_commands.check(is_server_manager)
    async def admin_role(
        self,
        interaction: discord.Interaction,
        role: discord.Role
    ):
        self.save_role(
            interaction.guild_id,
            "admin_role_id",
            role.id
        )

        await interaction.response.send_message(
            f"✅ Role Admin diatur ke {role.mention}.",
            ephemeral=True
        )

    @access.command(
        name="user-role",
        description="Atur role khusus user."
    )
    @app_commands.guild_only()
    @app_commands.check(is_server_manager)
    async def user_role(
        self,
        interaction: discord.Interaction,
        role: discord.Role
    ):
        self.save_role(
            interaction.guild_id,
            "user_role_id",
            role.id
        )

        await interaction.response.send_message(
            f"✅ Role User diatur ke {role.mention}.",
            ephemeral=True
        )

    @access.command(
        name="set",
        description="Atur akses sebuah command."
    )
    @app_commands.guild_only()
    @app_commands.check(is_server_manager)
    @app_commands.choices(access=[
        app_commands.Choice(name="Admin", value="admin"),
        app_commands.Choice(name="User", value="user"),
    ])
    async def set_access(
        self,
        interaction: discord.Interaction,
        command: str,
        access: app_commands.Choice[str]
    ):
        path = " ".join(command.strip().lower().split())

        if not path or path.startswith("access "):
            await interaction.response.send_message(
                "❌ Nama command tidak valid.",
                ephemeral=True
            )
            return

        parts = path.split()
        current = self.bot.tree.get_command(parts[0])

        if current is None:
            await interaction.response.send_message(
                "❌ Command tersebut tidak ditemukan.",
                ephemeral=True
            )
            return

        for part in parts[1:]:
            if not isinstance(current, app_commands.Group):
                current = None
                break

            current = current.get_command(part)

            if current is None:
                break

        if current is None:
            await interaction.response.send_message(
                "❌ Subcommand tersebut tidak ditemukan.",
                ephemeral=True
            )
            return

        self.save_command_access(
            interaction.guild_id,
            path,
            access.value
        )

        await interaction.response.send_message(
            f"✅ Akses `/{path}` sekarang: **{access.name}**.",
            ephemeral=True
        )

    @access.command(
        name="list",
        description="Lihat daftar pengaturan akses command."
    )
    @app_commands.guild_only()
    @app_commands.check(is_server_manager)
    async def list_access(self, interaction: discord.Interaction):
        with sqlite3.connect(DB_PATH) as db:
            rows = db.execute("""
                SELECT command_path, access
                FROM command_permissions
                WHERE guild_id = ?
                ORDER BY command_path
            """, (interaction.guild_id,)).fetchall()

        embed = discord.Embed(
            title="🔐 Command Access Settings",
            description=(
                "Command yang belum diatur secara khusus "
                "menggunakan akses default."
            ),
            color=discord.Color.blurple()
        )

        if rows:
            lines = [
                f"`/{path}` → **{access.upper()}**"
                for path, access in rows
            ]

            description = "\n".join(lines)

            for start in range(0, len(description), 4000):
                embed.add_field(
                    name="Pengaturan khusus",
                    value=description[start:start + 4000],
                    inline=False
                )
        else:
            embed.add_field(
                name="Pengaturan khusus",
                value="Belum ada perubahan akses command.",
                inline=False
            )

        admin_id, user_id = get_roles(interaction.guild_id)

        admin_role = interaction.guild.get_role(admin_id) if admin_id else None
        user_role = interaction.guild.get_role(user_id) if user_id else None

        embed.add_field(
            name="Admin Role",
            value=admin_role.mention if admin_role else "Belum diatur",
            inline=True
        )

        embed.add_field(
            name="User Role",
            value=user_role.mention if user_role else "Belum diatur",
            inline=True
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    @access.command(
        name="reset-command",
        description="Hapus pengaturan khusus sebuah command."
    )
    @app_commands.guild_only()
    @app_commands.check(is_server_manager)
    async def reset_command(
        self,
        interaction: discord.Interaction,
        command: str
    ):
        path = " ".join(command.strip().lower().split())

        self.delete_command_access(interaction.guild_id, path)

        await interaction.response.send_message(
            f"✅ Pengaturan `/{path}` dikembalikan ke akses default.",
            ephemeral=True
        )

    @access.command(
        name="show",
        description="Lihat pengaturan role akses."
    )
    @app_commands.guild_only()
    @app_commands.check(is_server_manager)
    async def show(self, interaction: discord.Interaction):
        admin_id, user_id = get_roles(interaction.guild_id)

        admin_role = interaction.guild.get_role(admin_id) if admin_id else None
        user_role = interaction.guild.get_role(user_id) if user_id else None

        embed = discord.Embed(
            title="🔐 Pengaturan Akses Pelayan SFC",
            color=discord.Color.blurple()
        )

        embed.add_field(
            name="Admin Role",
            value=admin_role.mention if admin_role else "Belum diatur",
            inline=False
        )

        embed.add_field(
            name="User Role",
            value=user_role.mention if user_role else "Belum diatur",
            inline=False
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )

    @access.command(
        name="reset",
        description="Reset pengaturan role akses."
    )
    @app_commands.guild_only()
    @app_commands.check(is_server_manager)
    async def reset(self, interaction: discord.Interaction):
        with sqlite3.connect(DB_PATH) as db:
            db.execute(
                "DELETE FROM access_settings WHERE guild_id = ?",
                (interaction.guild_id,)
            )

        await interaction.response.send_message(
            "✅ Pengaturan role akses berhasil direset.",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Permissions(bot))
