
import os
import json
from cogs.permissions import PermissionTree
import logging
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv


# ==========================================
# CONFIGURATION
# ==========================================

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

TOKEN = os.getenv("DISCORD_TOKEN")
BOT_PREFIX = os.getenv("BOT_PREFIX", "!")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Server tempat slash command akan disinkronkan
GUILD_ID = 901500690709508118

PREFIX_FILE = BASE_DIR / "data" / "prefixes.json"
COGS_DIR = BASE_DIR / "cogs"


# ==========================================
# LOGGING
# ==========================================

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

log = logging.getLogger("PelayanSFC")


# ==========================================
# PREFIX HANDLER
# ==========================================

async def get_prefix(bot, message):

    prefixes = [BOT_PREFIX]

    if message.guild:
        try:
            if PREFIX_FILE.exists():
                with PREFIX_FILE.open("r", encoding="utf-8") as file:
                    data = json.load(file)

                guild_data = data.get("guilds", data)
                custom = guild_data.get(str(message.guild.id))

                if isinstance(custom, str):
                    prefixes.append(custom)

                elif isinstance(custom, dict):
                    custom_prefix = custom.get("prefix")

                    if isinstance(custom_prefix, str):
                        prefixes.append(custom_prefix)

        except Exception:
            log.exception("Failed reading custom prefixes")

    prefixes = list(dict.fromkeys(prefixes))

    return commands.when_mentioned_or(*prefixes)(bot, message)


# ==========================================
# BOT CLASS
# ==========================================

class PelayanBot(commands.Bot):

    def __init__(self):

        intents = discord.Intents.default()

        intents.guilds = True
        intents.messages = True
        intents.message_content = True
        intents.members = True
        intents.presences = True
        intents.voice_states = True

        super().__init__(
            command_prefix=get_prefix,
            intents=intents,
            help_command=None,
tree_cls=PermissionTree
        )

    # ======================================
    # LOAD COGS AND SYNC COMMANDS
    # ======================================

    async def setup_hook(self):

        log.info("Starting bot setup...")

        loaded = 0
        failed = 0

        # ==================================
        # AUTO LOAD COGS
        # ==================================

        if not COGS_DIR.exists():
            log.error("Cogs directory not found: %s", COGS_DIR)
        else:

            for path in sorted(COGS_DIR.rglob("*.py")):

                if path.name.startswith("_"):
                    continue

                module = ".".join(
                    path.relative_to(BASE_DIR)
                    .with_suffix("")
                    .parts
                )

                try:
                    await self.load_extension(module)

                    loaded += 1
                    log.info("Loaded extension: %s", module)

                except Exception:
                    failed += 1
                    log.exception("Failed loading extension: %s", module)

        log.info(
            "Cog loading complete: %s loaded, %s failed",
            loaded,
            failed
        )

        # ==================================
        # INSPECT APPLICATION COMMANDS
        # ==================================

        commands_before = self.tree.get_commands()

        log.info(
            "Commands before sync: %s",
            [command.name for command in commands_before]
        )

        music_group = self.tree.get_command("music")

        if music_group:
            log.info(
                "Music subcommands: %s",
                [command.name for command in music_group.commands]
            )
        else:
            log.warning("Music command group was not registered!")

        # ==================================
        # GUILD SLASH COMMAND SYNC
        # ==================================

        try:
            guild = discord.Object(id=GUILD_ID)

            # Hapus definisi command lama khusus server ini
            self.tree.clear_commands(guild=guild)

            # Salin command terbaru dari local tree
            self.tree.copy_global_to(guild=guild)

            # Sinkronkan ke Discord
            synced = await self.tree.sync(guild=guild)

            log.info(
                "Guild sync successful: %s commands",
                len(synced)
            )

            # Periksa command yang tersimpan di Discord
            remote_commands = await self.tree.fetch_commands(
                guild=guild
            )

            log.info(
                "Remote commands: %s",
                [command.name for command in remote_commands]
            )

        except Exception:
            log.exception("Guild command sync failed")
    # ======================================
    # BOT READY
    # ======================================

    async def on_ready(self):

        log.info(
            "Connected to %s servers",
            len(self.guilds)
        )

        log.info(
            "Ready as %s",
            self.user
        )

    # ======================================
    # PREFIX COMMAND ERROR
    # ======================================

    async def on_command_error(self, ctx, error):

        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, commands.MissingRequiredArgument):

            await ctx.send("⚠️ Argumen command belum lengkap.")
            return

        if isinstance(error, commands.BadArgument):

            await ctx.send("⚠️ Format argumen tidak valid.")
            return

        if isinstance(error, commands.CommandOnCooldown):

            await ctx.send(
                f"⏳ Tunggu {error.retry_after:.1f} detik sebelum mencoba lagi."
            )
            return

        if isinstance(error, commands.MissingPermissions):

            await ctx.send("⛔ Kamu tidak memiliki izin untuk command ini.")
            return

        if isinstance(error, commands.CheckFailure):

            await ctx.send("⛔ Kamu tidak memenuhi persyaratan command ini.")
            return

        if isinstance(error, commands.CommandInvokeError):

            log.error(
                "Command execution failed: %s",
                ctx.command,
                exc_info=(
                    type(error.original),
                    error.original,
                    error.original.__traceback__
                )
            )

            await ctx.send("❌ Terjadi kesalahan saat menjalankan command.")
            return

        log.exception("Unhandled command error", exc_info=error)


# ==========================================
# START BOT
# ==========================================

def main():

    if not TOKEN:
        raise RuntimeError(
            "DISCORD_TOKEN tidak ditemukan di file .env"
        )

    bot = PelayanBot()

    try:
        bot.run(TOKEN, log_handler=None)

    except KeyboardInterrupt:
        log.info("Bot stopped by user")


if __name__ == "__main__":
    main()
