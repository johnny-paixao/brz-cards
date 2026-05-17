import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import discord
from discord import app_commands
from dotenv import load_dotenv

from cards.card_generator import GENERATED_DIR, generate_player_card
from database.bigquery_client import get_all_card_players, get_latest_player_card, get_ranking_players

PLAYERS_CACHE = []
RANKING_CACHE = {"timestamp": 0, "data": []}

def _get_cached_players() -> list[dict]:
    global PLAYERS_CACHE
    if not PLAYERS_CACHE:
        PLAYERS_CACHE = get_all_card_players()
    return PLAYERS_CACHE

def _get_cached_ranking() -> list[dict]:
    global RANKING_CACHE
    now = time.time()
    if now - RANKING_CACHE["timestamp"] > 300 or not RANKING_CACHE["data"]:
        RANKING_CACHE["data"] = get_ranking_players()
        RANKING_CACHE["timestamp"] = now
    return RANKING_CACHE["data"]


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

    # Set the bot's avatar profile picture to brz_logo.png safely
    try:
        logo_path = Path("assets/logos/brz_logo.png")
        if logo_path.exists():
            with open(logo_path, "rb") as f:
                avatar_bytes = f.read()
            await client.user.edit(avatar=avatar_bytes)
            print("Bot avatar updated successfully to brz_logo.png.")
        else:
            print("brz_logo.png not found in assets/logos.")
    except Exception as e:
        print(f"Could not update bot avatar (it might be rate-limited by Discord): {e}")


class RankingView(discord.ui.View):
    def __init__(self, players: list[dict]):
        super().__init__(timeout=180)
        self.players = players
        self.update_items()

    def get_embed(self) -> discord.Embed:
        embed = discord.Embed(title="🏆 Ranking BRz Cards — Season 8", color=discord.Color.gold())

        desc_lines = []
        for i, p in enumerate(self.players):
            pos = i + 1
            
            lvl = p.get('current_faceit_level')
            try:
                lvl_val = int(float(lvl)) if lvl is not None else 0
                lvl_str = f"lvl {lvl_val}" if lvl_val > 0 else "Unranked"
            except (ValueError, TypeError):
                lvl_str = "Unranked"

            elo = p.get('current_faceit_elo')
            try:
                elo_val = int(float(elo)) if elo is not None else 0
                elo_str = f" ({elo_val} ELO)" if elo_val > 0 else ""
            except (ValueError, TypeError):
                elo_str = ""
                
            line = f"**{pos}.** {p['faceit_nickname']} — **{p['overall']} OVR** — {p['role']} — {lvl_str}{elo_str} — {p['season8_matches']} jogos"
            desc_lines.append(line)
        
        embed.description = "\n".join(desc_lines)

        # Get latest update timestamp from the players data
        latest_update = None
        for p in self.players:
            up = p.get('uploaded_at')
            if up:
                if latest_update is None or up > latest_update:
                    latest_update = up
                    
        if latest_update:
            from zoneinfo import ZoneInfo
            lisbon_tz = ZoneInfo("Europe/Lisbon")
            if latest_update.tzinfo is None:
                latest_update = latest_update.replace(tzinfo=timezone.utc)
            calc_pt = latest_update.astimezone(lisbon_tz)
            dt_str = calc_pt.strftime("%d/%m/%Y às %H:%M (Horário de Portugal)")
            embed.set_footer(text=f"Última atualização: {dt_str}")

        return embed

    def update_items(self):
        self.clear_items()
        close_button = discord.ui.Button(label="Fechar", style=discord.ButtonStyle.danger)
        close_button.callback = self.close_view
        self.add_item(close_button)

    async def close_view(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="Menu de ranking fechado.", embed=None, view=None)


brzcards_group = app_commands.Group(name="brzcards", description="Comandos relacionados às Cartas BRz")

@brzcards_group.command(name="card", description="Gera e mostra a carta BRz de um jogador específico.")
@app_commands.describe(player="Nome do jogador (com autocomplete)")
async def card(interaction: discord.Interaction, player: str) -> None:
    """
    Gera e mostra a carta BRz de um jogador específico (com autocomplete).
    """
    await interaction.response.defer(thinking=True)
    try:
        card_data = get_latest_player_card(player)
        if card_data is None:
            await interaction.followup.send(
                f"Não encontrei uma carta para o player `{player}`."
            )
            return

        player_identifier = (
            card_data.get("player_id")
            or card_data.get("player_slug")
            or card_data.get("player_code")
            or normalize_player_identifier(player)
        )

        display_name = (
            card_data.get("display_name")
            or player
        )
        overall_brz = card_data.get("overall_brz")
        score_version = card_data.get("score_version") or "unknown_version"
        calculated_at = card_data.get("calculated_at")

        if calculated_at:
            date_str = calculated_at.strftime("%Y%m%d") if hasattr(calculated_at, "strftime") else str(calculated_at)[:10].replace("-", "")
            expected_filename = f"{player_identifier}_season8_{score_version}_{date_str}.png"
        else:
            expected_filename = f"{player_identifier}_season8_{score_version}.png"

        expected_path = GENERATED_DIR / expected_filename

        if expected_path.exists():
            print(f"[{player_identifier}] Cache HIT! Enviando imagem já gerada: {expected_path}")
            card_path = str(expected_path)
        else:
            print(f"[{player_identifier}] Cache MISS. Gerando nova carta e salvando em: {expected_path}")
            card_path = generate_player_card(player_identifier, output_path=expected_path)

        content_lines = [f"**BRz Card — {display_name}**"]
        if overall_brz is not None:
            content_lines.append(f"Overall BRz: **{overall_brz}**")

        if calculated_at:
            from zoneinfo import ZoneInfo
            lisbon_tz = ZoneInfo("Europe/Lisbon")
            if calculated_at.tzinfo is None:
                calculated_at = calculated_at.replace(tzinfo=timezone.utc)
            calc_pt = calculated_at.astimezone(lisbon_tz)
            dt_str = calc_pt.strftime("%d/%m/%Y às %H:%M (Horário de Portugal)")
            content_lines.append(f"Última atualização dos stats: {dt_str}")

        await interaction.followup.send(
            content="\n".join(content_lines),
            file=discord.File(card_path),
        )

    except Exception as e:
        print(f"Error generating BRz card for '{player}': {e}")
        await interaction.followup.send(
            "Não consegui gerar a carta agora. Ocorreu um erro no processo de geração."
        )

@card.autocomplete("player")
async def card_player_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    try:
        players = _get_cached_players()
        if not players:
            return []
        
        choices = []
        for p in players:
            name = p.get('faceit_nickname') or ""
            if current.lower() in name.lower():
                choices.append(app_commands.Choice(name=name, value=name))
        return choices[:25]
    except Exception as e:
        print(f"Autocomplete error: {e}")
        return []

@brzcards_group.command(name="ranking", description="Mostra o ranking oficial da Season 8.")
async def ranking(interaction: discord.Interaction) -> None:
    """
    Mostra o ranking público da Season 8 em lista única.
    """
    try:
        players = _get_cached_ranking()
        if not players:
            await interaction.response.send_message("Nenhum jogador encontrado no ranking.", ephemeral=True)
            return

        view = RankingView(players)
        await interaction.response.send_message(embed=view.get_embed(), view=view)
    except Exception as e:
        print(f"Error fetching ranking: {e}")
        await interaction.response.send_message("Ocorreu um erro ao carregar o ranking.", ephemeral=True)

client.tree.add_command(brzcards_group)


client.run(DISCORD_BOT_TOKEN)