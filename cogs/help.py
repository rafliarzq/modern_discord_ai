import discord
from discord.ext import commands
from discord import app_commands


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_command_lines(self, command):
        lines = []

        description = command.description or "Tidak ada deskripsi."
        lines.append(
            f"**`/{command.qualified_name}`**\n"
            f"{description}"
        )

        if isinstance(command, app_commands.Group):
            for child in command.commands:
                lines.extend(self.get_command_lines(child))

        return lines

    @app_commands.command(
        name="help",
        description="Menampilkan daftar perintah bot."
    )
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📖 Pusat Bantuan",
            description=(
                "Berikut daftar perintah yang tersedia.\n"
                "Gunakan slash command `/` untuk menjalankannya."
            ),
            color=discord.Color.blurple()
        )

        commands_list = self.bot.tree.get_commands()

        for command in commands_list:
            if command.name == "help":
                continue

            lines = self.get_command_lines(command)
            content = "\n\n".join(lines)

            # Discord membatasi nilai field embed hingga 1024 karakter.
            chunks = []
            current = ""

            for line in content.split("\n\n"):
                addition = line if not current else "\n\n" + line

                if len(current) + len(addition) > 1000:
                    chunks.append(current)
                    current = line
                else:
                    current += addition

            if current:
                chunks.append(current)

            for index, chunk in enumerate(chunks):
                field_name = command.name

                if index > 0:
                    field_name += f" (lanjutan {index + 1})"

                if len(embed.fields) < 25:
                    embed.add_field(
                        name=f"⚙️ {field_name}",
                        value=chunk,
                        inline=False
                    )

        embed.set_footer(
            text=f"Diminta oleh {interaction.user.display_name}"
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Help(bot))
