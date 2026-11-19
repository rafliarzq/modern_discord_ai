
from __future__ import annotations


import json
import logging
import os
from pathlib import Path

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SENT_FILE = DATA_DIR / "free_games.json"

API_URL = "https://www.gamerpower.net/api/giveaways"


class FreeGames(commands.Cog):
    games = app_commands.Group(
        name="games",
        description="Informasi game gratis Epic Games dan Steam",
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.channel_id = int(
            os.getenv("GAME_ALERT_CHANNEL_ID", "0")
        )
        self.check_interval = max(
            60,
            int(os.getenv("GAME_CHECK_INTERVAL", "21600"))
        )

        self.session: aiohttp.ClientSession | None = None
        self.sent_ids: set[str] = set()

    async def cog_load(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        try:
            if SENT_FILE.exists():
                data = json.loads(SENT_FILE.read_text(encoding="utf-8"))
                self.sent_ids = set(map(str, data))
        except (OSError, ValueError):
            log.exception("Gagal membaca database game gratis")
            self.sent_ids = set()

        timeout = aiohttp.ClientTimeout(total=45)
        self.session = aiohttp.ClientSession(timeout=timeout)

        self.check_games.change_interval(
            seconds=self.check_interval
        )
        self.check_games.start()

    async def cog_unload(self):
        self.check_games.cancel()

        if self.session and not self.session.closed:
            await self.session.close()

    def save_sent_ids(self):
        SENT_FILE.write_text(
            json.dumps(sorted(self.sent_ids), indent=2),
            encoding="utf-8",
        )

    async def fetch_games(self):
        if self.session is None or self.session.closed:
            return []

        params = {
            "platform": "steam",
            "type": "game",
        }

        results = []

        for platform in ("steam", "epic-games-store"):
            params["platform"] = platform

            try:
                async with self.session.get(
                    API_URL,
                    params=params,
                ) as response:
                    if response.status != 200:
                        log.warning(
                            "GamerPower HTTP %s untuk %s",
                            response.status,
                            platform,
                        )
                        continue

                    data = await response.json(content_type=None)

                    if isinstance(data, list):
                        results.extend(data)
                    elif isinstance(data, dict):
                        results.extend(data.get("giveaways", []))

            except (aiohttp.ClientError, ValueError):
                log.exception(
                    "Gagal mengambil giveaway %s",
                    platform,
                )

        return results

    @staticmethod
    def is_target_game(game: dict) -> bool:
        if str(game.get("type", "")).lower() != "game":
            return False

        if str(game.get("status", "active")).lower() != "active":
            return False

        platforms = str(game.get("platforms", "")).lower()

        return (
            "steam" in platforms
            or "epic games" in platforms
            or "epic-games-store" in platforms
        )

    async def send_game(self, game: dict):
        channel = self.bot.get_channel(self.channel_id)

        if channel is None:
            try:
                channel = await self.bot.fetch_channel(
                    self.channel_id
                )
            except discord.HTTPException:
                log.exception("Channel game gratis tidak ditemukan")
                return False

        title = str(game.get("title", "Game Gratis"))[:250]
        description = str(
            game.get("description", "Game gratis tersedia sekarang.")
        )[:1000]

        platforms = str(game.get("platforms", "PC"))
        end_date = str(game.get("end_date", "Tidak diketahui"))

        claim_url = (
            game.get("open_giveaway_url")
            or game.get("open_giveaway")
            or game.get("gamerpower_url")
        )

        if not claim_url:
            return False

        embed = discord.Embed(
            title=f"🎮 {title}",
            description=description,
            url=claim_url,
            color=discord.Color.green(),
        )

        embed.add_field(
            name="Platform",
            value=platforms[:200],
            inline=True,
        )
        embed.add_field(
            name="Berakhir",
            value=end_date[:100],
            inline=True,
        )

        image_url = game.get("image") or game.get("thumbnail")

        if image_url:
            embed.set_image(url=image_url)

        embed.set_footer(
            text="Sumber: GamerPower | Periksa ketersediaan sebelum klaim"
        )

        try:
            await channel.send(
                embed=embed,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return True

        except discord.HTTPException:
            log.exception("Gagal mengirim pengumuman game")
            return False

    @games.command(
        name="cek",
        description="Periksa game gratis Epic Games dan Steam sekarang",
    )
    async def games_cek(self, interaction: discord.Interaction):
        if not self.channel_id:
            await interaction.response.send_message(
                "GAME_ALERT_CHANNEL_ID belum diatur di .env.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        games = await self.fetch_games()
        posted = 0

        for game in games:
            if not self.is_target_game(game):
                continue

            game_id = str(game.get("id", "")).strip()

            if not game_id or game_id in self.sent_ids:
                continue

            success = await self.send_game(game)

            if success:
                self.sent_ids.add(game_id)
                posted += 1

                try:
                    self.save_sent_ids()
                except OSError:
                    log.exception("Gagal menyimpan database game")

        if posted:
            message = (
                f"Berhasil mengumumkan **{posted} game gratis baru** "
                "ke channel pengumuman."
            )
        else:
            message = (
                "Belum ada game gratis baru yang ditemukan. "
                "Game yang sudah diumumkan tidak akan dikirim ulang."
            )

        await interaction.followup.send(message, ephemeral=True)

    @tasks.loop(hours=6)
    async def check_games(self):
        if not self.channel_id:
            log.warning("GAME_ALERT_CHANNEL_ID belum diatur")
            return

        games = await self.fetch_games()

        for game in games:
            if not self.is_target_game(game):
                continue

            game_id = str(game.get("id", "")).strip()

            if not game_id or game_id in self.sent_ids:
                continue

            success = await self.send_game(game)

            if success:
                self.sent_ids.add(game_id)

                try:
                    self.save_sent_ids()
                except OSError:
                    log.exception("Gagal menyimpan database game")

    @check_games.before_loop
    async def before_check_games(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(FreeGames(bot))
