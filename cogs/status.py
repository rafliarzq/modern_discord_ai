
import discord
from discord.ext import commands, tasks


class Status(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.index = 0

        self.activities = [
            discord.Game(name="AI Assistant"),
            discord.Activity(
                type=discord.ActivityType.watching,
                name="Made by  : @Rafliarzq"
            ),
            discord.Activity(
                type=discord.ActivityType.listening,
                name="AI Commands : /help"
            ),
            discord.Game(name="Artificial Intelligence"),
            discord.Activity(
                type=discord.ActivityType.watching,
                name="Our Community Since 2025"
            ),
        ]

        self.rotate_status.start()

    @tasks.loop(seconds=30)
    async def rotate_status(self):
        activity = self.activities[self.index]

        await self.bot.change_presence(
            status=discord.Status.online,
            activity=activity
        )

        self.index = (self.index + 1) % len(self.activities)

    @rotate_status.before_loop
    async def before_rotate_status(self):
        await self.bot.wait_until_ready()

    def cog_unload(self):
        self.rotate_status.cancel()


async def setup(bot):
    await bot.add_cog(Status(bot))
