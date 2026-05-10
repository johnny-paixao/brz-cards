import os
from pathlib import Path

import discord
from discord import app_commands
from dotenv import load_dotenv

from cards.card_generator import generate_player_card
from database.bigquery_client import get_latest_player_card


load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID")

if not DISCORD_BOT_TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN is missing. Check your .env file.")

if not DISCORD_GUILD_ID:
    raise ValueError("DISCORD_GUILD_ID is missing. Check your .env file.")


class BRzCardsBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        """
        Sync slash commands directly with the BRz Discord server.
        Guild sync is faster than global sync during development.
        """
        guild = discord.Object(id=int(DISCORD_GUILD_ID))

        self.tree.copy_global_to(guild=guild)
        synced_commands = await self.tree.sync(guild=guild)

        print(
            f"Synced {len(synced_commands)} command(s) "
            f"to guild {DISCORD_GUILD_ID}."
        )


client = BRzCardsBot()


@client.event
async def on_ready() -> None:
    print(f"Bot connected as {client.user}")
    print("BRz Cards is ready.")
    print("Guilds where this bot is installed:")

    for guild in client.guilds:
        print(f"- {guild.name} | Guild ID: {guild.id}")


@client.tree.command(
    name="brzcards",
    description="Gera a carta BRz de um jogador da comunidade.",
)
@app_commands.describe(
    player_name="Nome do jogador. Exemplo: Johnny",
)
async def brzcards(interaction: discord.Interaction, player_name: str) -> None:
    """
    Generate and send a BRz player card.
    """
    await interaction.response.defer(thinking=True)

    card_data = get_latest_player_card(player_name)

    if card_data is None:
        await interaction.followup.send(
            f"Não encontrei uma carta para o player `{player_name}`."
        )
        return

    safe_player_name = card_data["display_name"].lower().replace(" ", "_")
    output_path = Path(f"outputs/cards/{safe_player_name}_card.png")

    generate_player_card(
        card_data=card_data,
        output_path=output_path,
    )

    discord_file = discord.File(
        fp=output_path,
        filename=f"{safe_player_name}_card.png",
    )

    await interaction.followup.send(
        content=(
            f"**BRz Card — {card_data['display_name']}**\n"
            f"Overall BRz: **{card_data['overall_brz']}**\n"
            f"Score version: `{card_data['score_version']}`"
        ),
        file=discord_file,
    )


client.run(DISCORD_BOT_TOKEN)