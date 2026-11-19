import json
import logging
from pathlib import Path

import aiohttp
import discord
from discord.ext import commands, tasks

log = logging.getLogger("PelayanSFC.GitHub")

REPO_OWNER = "rafliarzq"
REPO_NAME = "modern_discord_ai"
BRANCH = "main"

CHANNEL_ID = 1572927150749777951

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
STATE_FILE = DATA_DIR / "github_last_commit.json"

GITHUB_API = (
    f"https://api.github.com/repos/"
    f"{REPO_OWNER}/{REPO_NAME}/commits"
)


class GitHubUpdates(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.session = None

    async def cog_load(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        self.session = aiohttp.ClientSession(
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "PelayanSFC-GitHub-Updates"
            },
            timeout=aiohttp.ClientTimeout(total=20)
        )

        self.check_github.start()

    async def cog_unload(self):
        self.check_github.cancel()

        if self.session and not self.session.closed:
            await self.session.close()

    def load_last_commit(self):
        try:
            if STATE_FILE.exists():
                data = json.loads(
                    STATE_FILE.read_text(encoding="utf-8")
                )
                return data.get("sha")
        except Exception:
            log.exception("Failed reading GitHub state")

        return None

    def save_last_commit(self, sha):
        STATE_FILE.write_text(
            json.dumps({"sha": sha}, indent=2),
            encoding="utf-8"
        )

    async def get_commits(self):
        params = {
            "sha": BRANCH,
            "per_page": 5
        }

        async with self.session.get(
            GITHUB_API,
            params=params
        ) as response:

            if response.status != 200:
                log.error(
                    "GitHub API error: HTTP %s - %s",
                    response.status,
                    await response.text()
                )
                return None

            return await response.json()

    async def send_commit(self, channel, commit):
        commit_data = commit["commit"]

        message = commit_data["message"].split("\n")[0]
        author = (
            commit_data.get("author", {}).get("name")
            or "Unknown"
        )

        sha = commit["sha"]
        short_sha = sha[:7]

        url = commit["html_url"]

        embed = discord.Embed(
            title="🚀 GitHub Repository Updated",
            description=f"**{message}**",
            url=url,
            color=discord.Color.blurple()
        )

        embed.add_field(
            name="Repository",
            value=f"`{REPO_OWNER}/{REPO_NAME}`",
            inline=False
        )

        embed.add_field(
            name="Branch",
            value=f"`{BRANCH}`",
            inline=True
        )

        embed.add_field(
            name="Author",
            value=author,
            inline=True
        )

        embed.add_field(
            name="Commit",
            value=f"`{short_sha}`",
            inline=True
        )

        embed.add_field(
            name="View Changes",
            value=f"[Lihat commit di GitHub]({url})",
            inline=False
        )

        embed.set_footer(
            text="Pelayan SFC • GitHub Update Monitor"
        )

        await channel.send(
            content="📢 **Ada pembaruan baru pada repository!**",
            embed=embed
        )

    @tasks.loop(seconds=60)
    async def check_github(self):
        try:
            commits = await self.get_commits()

            if not commits:
                return

            last_sha = self.load_last_commit()

            # Saat pertama kali berjalan, simpan commit
            # terbaru tanpa mengirim notifikasi lama.
            if last_sha is None:
                self.save_last_commit(commits[0]["sha"])
                log.info(
                    "GitHub monitor initialized: %s",
                    commits[0]["sha"][:7]
                )
                return

            new_commits = []

            for commit in commits:
                if commit["sha"] == last_sha:
                    break

                new_commits.append(commit)

            if not new_commits:
                return

            channel = self.bot.get_channel(CHANNEL_ID)

            if channel is None:
                channel = await self.bot.fetch_channel(CHANNEL_ID)

            for commit in reversed(new_commits):
                await self.send_commit(channel, commit)
                self.save_last_commit(commit["sha"])

                log.info(
                    "GitHub notification sent: %s",
                    commit["sha"][:7]
                )

        except Exception:
            log.exception("GitHub update check failed")

    @check_github.before_loop
    async def before_check_github(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(GitHubUpdates(bot))
