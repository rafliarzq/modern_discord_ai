
import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
import random
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "fishing.db"

COOLDOWN = 30


FISH = [
    ("Sarden", "Common", 5, 10),
    ("Lele", "Common", 10, 15),
    ("Nila", "Common", 20, 25),
    ("Mas", "Common", 30, 35),
    ("Mujair", "Common", 40, 45),
    ("Gabus", "Common", 50, 55),

    ("Gurame", "Uncommon", 70, 75),
    ("Patin", "Uncommon", 80, 85),
    ("Bawal", "Uncommon", 90, 95),
    ("Kakap", "Uncommon", 100, 105),
    ("Tongkol", "Uncommon", 110, 115),
    ("Baronang", "Uncommon", 125, 125),

    ("Salmon", "Rare", 150, 165),
    ("Tuna", "Rare", 90, 185),
    ("Marlin", "Rare", 100, 205),
    ("Belut Listrik", "Rare", 120, 220),
    ("Ikan Pedang", "Rare", 130, 250),
    ("Lobster", "Rare", 140, 270),

    ("Hiu", "Epic", 250, 400),
    ("Pari Raksasa", "Epic", 300, 500),
    ("Cumi Kolosal", "Epic", 350, 550),
    ("Kepiting Raja", "Epic", 350, 600),
    ("Nautilus", "Epic", 400, 650),

    ("Paus Biru", "Legendary", 700, 1000),
    ("Megalodon", "Legendary", 800, 1200),
    ("Leviathan", "Legendary", 1000, 1500),

    ("Naga Laut", "Mythical", 2000, 3500),
    ("Phoenix Fish", "Mythical", 2500, 4000),
    ("Celestial Koi", "Mythical", 3000, 5000),

    ("???", "Secret", 10000, 20000),
]


RODS = {
    "wood": {
        "name": "Wooden Rod",
        "price": 0,
        "luck": 0
    },
    "iron": {
        "name": "Iron Rod",
        "price": 500,
        "luck": 10
    },
    "gold": {
        "name": "Golden Rod",
        "price": 2000,
        "luck": 25
    },
    "diamond": {
        "name": "Diamond Rod",
        "price": 7500,
        "luck": 45
    }
}


RARITY_EMOJI = {
    "Common": "⚪",
    "Uncommon": "🟢",
    "Rare": "🔵",
    "Epic": "🟣",
    "Legendary": "🟠",
    "Mythical": "🔴",
"Secret": "🌈",
}


class Fishing(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = sqlite3.connect(DB_PATH)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS fishing_users (
                user_id INTEGER PRIMARY KEY,
                coins INTEGER DEFAULT 0,
                last_fish REAL DEFAULT 0
            )
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS fishing_inventory (
                user_id INTEGER,
                fish_name TEXT,
                rarity TEXT,
                quantity INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, fish_name)
            )
        """)

        self.db.execute("""
            CREATE TABLE IF NOT EXISTS fishing_rods (
                user_id INTEGER PRIMARY KEY,
                rod TEXT DEFAULT 'wood'
            )
        """)


        self.db.execute("""
            CREATE TABLE IF NOT EXISTS fishing_quests (
                user_id INTEGER,
                quest_date TEXT,
                catches INTEGER DEFAULT 0,
                claimed INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, quest_date)
            )
        """)
        self.db.commit()


    def get_user(self, user_id):
        self.db.execute(
            "INSERT OR IGNORE INTO fishing_users (user_id) VALUES (?)",
            (user_id,)
        )
        self.db.commit()
        return self.db.execute(
            "SELECT coins, last_fish FROM fishing_users WHERE user_id = ?",
            (user_id,)
        ).fetchone()

    fishing = app_commands.Group(
        name="fish",
        description="Sistem memancing Pelayan SFC"
    )

    @fishing.command(name="catch", description="Mulai memancing!")
    async def catch(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        coins, last_fish = self.get_user(user_id)

        remaining = COOLDOWN - (time.time() - last_fish)

        if remaining > 0:
            await interaction.response.send_message(
                f"🎣 Tunggu **{int(remaining)} detik** sebelum memancing lagi.",
                ephemeral=True
            )
            return

        name, rarity, minimum, maximum = random.choice(FISH)
        value = random.randint(minimum, maximum)

        self.db.execute("""
            INSERT INTO fishing_inventory
            (user_id, fish_name, rarity, quantity)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(user_id, fish_name)
            DO UPDATE SET quantity = quantity + 1
        """, (user_id, name, rarity))

        self.db.execute(
            "UPDATE fishing_users SET last_fish = ? WHERE user_id = ?",
            (time.time(), user_id)
        )

        today = time.strftime("%Y-%m-%d", time.gmtime())

        self.db.execute("""
            INSERT INTO fishing_quests
            (user_id, quest_date, catches)
            VALUES (?, ?, 1)
            ON CONFLICT(user_id, quest_date)
            DO UPDATE SET catches = catches + 1
        """, (user_id, today))

        self.db.commit()

        embed = discord.Embed(
            title="🎣 Hasil Memancing!",
            description=(
                f"Selamat! Kamu mendapatkan **{name}**!\n\n"
                f"Rarity: {RARITY_EMOJI[rarity]} **{rarity}**\n"
                f"Harga jual: 🪙 **{value} koin**"
            ),
            color=discord.Color.blue()
        )
        embed.set_footer(text="Pelayan SFC Fishing System")

        await interaction.response.send_message(embed=embed)

    @fishing.command(name="inventory", description="Lihat koleksi ikanmu")
    async def inventory(self, interaction: discord.Interaction):
        rows = self.db.execute("""
            SELECT fish_name, rarity, quantity
            FROM fishing_inventory
            WHERE user_id = ? AND quantity > 0
            ORDER BY quantity DESC
        """, (interaction.user.id,)).fetchall()

        if not rows:
            await interaction.response.send_message(
                "🎣 Inventory kamu masih kosong!",
                ephemeral=True
            )
            return

        description = "\n".join(
            f"{RARITY_EMOJI[rarity]} **{name}** × {quantity}"
            for name, rarity, quantity in rows
        )

        embed = discord.Embed(
            title=f"🎒 Koleksi Ikan {interaction.user.display_name}",
            description=description,
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)


    @fishing.command(name="shop", description="Lihat toko alat pancing")
    async def shop(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎣 Fishing Rod Shop",
            description="Pilih alat pancing terbaikmu!",
            color=discord.Color.gold()
        )

        for key, rod in RODS.items():
            embed.add_field(
                name=rod["name"],
                value=(
                    f"Harga: 🪙 {rod['price']:,}\n"
                    f"Bonus luck: +{rod['luck']}%"
                ),
                inline=False
            )

        await interaction.response.send_message(embed=embed)

    @fishing.command(name="upgrade", description="Beli alat pancing")
    @app_commands.describe(rod="Pilih alat pancing")
    @app_commands.choices(rod=[
        app_commands.Choice(name="Iron Rod", value="iron"),
        app_commands.Choice(name="Golden Rod", value="gold"),
        app_commands.Choice(name="Diamond Rod", value="diamond")
    ])
    async def upgrade(
        self,
        interaction: discord.Interaction,
        rod: app_commands.Choice[str]
    ):
        user_id = interaction.user.id
        coins, _ = self.get_user(user_id)

        current = self.db.execute(
            "SELECT rod FROM fishing_rods WHERE user_id = ?",
            (user_id,)
        ).fetchone()

        current_rod = current[0] if current else "wood"

        order = ["wood", "iron", "gold", "diamond"]

        if order.index(rod.value) <= order.index(current_rod):
            await interaction.response.send_message(
                "❌ Alat pancing kamu sudah setara atau lebih bagus!",
                ephemeral=True
            )
            return

        price = RODS[rod.value]["price"]

        if coins < price:
            await interaction.response.send_message(
                f"❌ Koin tidak cukup! Kamu membutuhkan {price:,} koin.",
                ephemeral=True
            )
            return

        self.db.execute("""
            INSERT INTO fishing_rods (user_id, rod)
            VALUES (?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET rod = excluded.rod
        """, (user_id, rod.value))

        self.db.execute(
            "UPDATE fishing_users SET coins = coins - ? WHERE user_id = ?",
            (price, user_id)
        )
        self.db.commit()

        await interaction.response.send_message(
            f"🎉 Berhasil membeli **{RODS[rod.value]['name']}**!"
        )


    @fishing.command(name="balance", description="Cek saldo koin fishing")
    async def balance(self, interaction: discord.Interaction):
        coins, _ = self.get_user(interaction.user.id)

        await interaction.response.send_message(
            f"🪙 Saldo Fishing kamu: **{coins} koin**"
        )

    @fishing.command(name="sell", description="Jual semua ikan dalam inventory")
    async def sell(self, interaction: discord.Interaction):
        user_id = interaction.user.id

        rows = self.db.execute("""
            SELECT fish_name, quantity
            FROM fishing_inventory
            WHERE user_id = ? AND quantity > 0
        """, (user_id,)).fetchall()

        if not rows:
            await interaction.response.send_message(
                "❌ Kamu tidak punya ikan untuk dijual!",
                ephemeral=True
            )
            return

        total = 0

        for name, quantity in rows:
            fish = next(f for f in FISH if f[0] == name)
            price = random.randint(fish[2], fish[3])
            total += price * quantity

        self.db.execute(
            "UPDATE fishing_users SET coins = coins + ? WHERE user_id = ?",
            (total, user_id)
        )
        self.db.execute(
            "DELETE FROM fishing_inventory WHERE user_id = ?",
            (user_id,)
        )
        self.db.commit()

        await interaction.response.send_message(
            f"💰 Berhasil menjual semua ikan!\n"
            f"Kamu mendapatkan **{total:,} koin**!"
        )

    async def cog_unload(self):
        self.db.close()


async def setup(bot):
    await bot.add_cog(Fishing(bot))
