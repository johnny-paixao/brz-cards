import os

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


def normalize_player_identifier(player_name: str) -> str:
    """
    Normalize user input into a player identifier format.
    Example:
    Johnny -> johnny
    brz johnny -> brz_johnny
    """
    normalized = player_name.strip().lower().replace(" ", "_")
    return normalized


class BRzCardsBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        """
        Sync slash commands directly with the BRz Discord server
        and remove old global commands to avoid duplicates.
        """
        guild = discord.Object(id=int(DISCORD_GUILD_ID))

        # Copy global commands to the target guild
        self.tree.copy_global_to(guild=guild)

        # Sync only to the guild for faster development/testing
        synced_guild_commands = await self.tree.sync(guild=guild)

        # Clear old global commands if they exist
        self.tree.clear_commands(guild=None)
        synced_global_commands = await self.tree.sync()

        print(
            f"Synced {len(synced_guild_commands)} command(s) "
            f"to guild {DISCORD_GUILD_ID}."
        )
        print(
            f"Cleared global commands. "
            f"Global command count: {len(synced_global_commands)}."
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

    try:
        # Busca dados da carta no BigQuery apenas para validar o player
        # e montar a mensagem de resposta.
        card_data = get_latest_player_card(player_name)

        if card_data is None:
            await interaction.followup.send(
                f"Não encontrei uma carta para o player `{player_name}`."
            )
            return

        # Tenta resolver o identificador correto do player para o card generator.
        # Preferência: usar um ID/slug vindo do BigQuery, se existir.
        player_identifier = (
            card_data.get("player_id")
            or card_data.get("player_slug")
            or card_data.get("player_code")
            or normalize_player_identifier(player_name)
        )

        # Gera a carta usando o fluxo atual do card_generator.
        # A expectativa é que essa função retorne o caminho final da imagem gerada.
        card_path = generate_player_card(player_identifier)

        display_name = (
            card_data.get("display_name")
            or card_data.get("player_name")
            or player_name
        )
        overall_brz = card_data.get("overall_brz")
        score_version = card_data.get("score_version")

        content_lines = [f"**BRz Card — {display_name}**"]

        if overall_brz is not None:
            content_lines.append(f"Overall BRz: **{overall_brz}**")

        if score_version:
            content_lines.append(f"Score version: `{score_version}`")

        await interaction.followup.send(
            content="\n".join(content_lines),
            file=discord.File(card_path),
        )

    except Exception as e:
        print(f"Error generating BRz card for '{player_name}': {e}")

        await interaction.followup.send(
            "Não consegui gerar a carta agora. Ocorreu um erro no processo de geração."
        )


client.run(DISCORD_BOT_TOKEN)