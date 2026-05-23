import logging
import math
import os
from datetime import datetime, timezone
from pathlib import Path

import discord
from discord import app_commands
from dotenv import load_dotenv

from cards.card_generator import GENERATED_DIR, generate_player_card
from database.bigquery_client import get_latest_player_card
from database.cache import BotDataCache

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("brzcards.bot")

# ---------------------------------------------------------------------------
# Cache instance (shared across all commands)
# ---------------------------------------------------------------------------

bot_cache = BotDataCache()

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID")

if not DISCORD_BOT_TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN is missing. Check your .env file.")

if not DISCORD_GUILD_ID:
    raise ValueError("DISCORD_GUILD_ID is missing. Check your .env file.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def normalize_player_identifier(player_name: str) -> str:
    """
    Normalize user input into a player identifier format.
    Example:
    Johnny -> johnny
    brz johnny -> brz_johnny
    """
    normalized = player_name.strip().lower().replace(" ", "_")
    return normalized


def _format_ruler_value(value: float, format_type: str) -> str:
    """Format a ruler value according to its type."""
    if format_type == "pct":
        return f"{value:.0f}%"
    elif format_type == "int":
        return f"{int(value)}"
    else:  # float2
        return f"{value:.2f}"


# ---------------------------------------------------------------------------
# Bot Client
# ---------------------------------------------------------------------------


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


# ===================================================================
# Embed Generators (Single Consolidated Lists)
# ===================================================================


def get_ranking_embed(players: list[dict]) -> discord.Embed:
    embed = discord.Embed(title="🏆 Ranking BRz Cards — Season 8 (players ativos com no mínimo 20 partidas na Season 8)", color=discord.Color.gold())

    desc_lines = []
    for i, p in enumerate(players):
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
    for p in players:
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


def get_stat_ranking_embed(players: list[dict], stat_name: str) -> discord.Embed:
    stat_name_upper = stat_name.upper()
    embed = discord.Embed(
        title=f"🏆 Ranking {stat_name_upper} — BRz Cards Season 8",
        color=discord.Color.gold(),
    )

    desc_lines = []
    for i, p in enumerate(players, start=1):
        stat_val = p.get("stat_value")
        try:
            stat_display = int(round(float(stat_val))) if stat_val is not None else "?"
        except (ValueError, TypeError):
            stat_display = "?"

        overall = p.get("OVERALL", "?")
        try:
            overall = int(round(float(overall))) if overall is not None else "?"
        except (ValueError, TypeError):
            overall = "?"

        role = p.get("role", "?")
        matches = p.get("season8_matches", "?")

        line = (
            f"**{i}.** {p['faceit_nickname']} — "
            f"**{stat_name_upper} {stat_display}** — "
            f"{overall} OVR — {role} — {matches} jogos"
        )
        desc_lines.append(line)

    embed.description = "\n".join(desc_lines)

    # Add latest update timestamp
    latest_update = None
    for p in players:
        up = p.get("uploaded_at")
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


def get_ruler_embed(ruler_data: list[dict]) -> discord.Embed:
    embed = discord.Embed(
        title="🏁 Régua da Comunidade — Season 8",
        color=discord.Color.dark_gold(),
    )

    desc_lines = []
    for i, item in enumerate(ruler_data, start=1):
        formatted_value = _format_ruler_value(item["value"], item["format_type"])
        line = f"**{i}.** {item['label']} — {item['faceit_nickname']} ({formatted_value})"
        desc_lines.append(line)

    embed.description = "\n".join(desc_lines)
    return embed


# ===================================================================
# Command Group
# ===================================================================

brzcards_group = app_commands.Group(name="brzcards", description="Comandos relacionados às Cartas BRz")


# -------------------------------------------------------------------
# /brzcards card
# -------------------------------------------------------------------

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
        players = bot_cache.get_or_fetch_players()
        if not players:
            return []
        
        choices = []
        for p in players:
            name = p.get('faceit_nickname') or ""
            if current.lower() in name.lower():
                choices.append(app_commands.Choice(name=name, value=name))
        
        # Ordenar as opções alfabeticamente para uma navegação muito melhor
        choices.sort(key=lambda c: c.name.lower())
        return choices[:25]
    except Exception as e:
        print(f"Autocomplete error: {e}")
        return []


# -------------------------------------------------------------------
# /brzcards ranking
# -------------------------------------------------------------------

@brzcards_group.command(name="ranking", description="Mostra o ranking oficial da Season 8.")
async def ranking(interaction: discord.Interaction) -> None:
    """
    Mostra o ranking público da Season 8 em lista única.
    """
    await interaction.response.defer(thinking=True)
    try:
        players = bot_cache.get_or_fetch_ranking()
        if not players:
            await interaction.followup.send("Nenhum jogador encontrado no ranking.")
            return

        embed = get_ranking_embed(players)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        print(f"Error fetching ranking: {e}")
        await interaction.followup.send("Ocorreu um erro ao carregar o ranking.")


# -------------------------------------------------------------------
# /brzcards stats <aim|imp|utl|con|int|exp>
# -------------------------------------------------------------------

stats_group = app_commands.Group(
    name="stats",
    description="Rankings por stat individual (AIM, IMP, UTL, CON, INT, EXP)",
    parent=brzcards_group,
)


async def _handle_stat_ranking(interaction: discord.Interaction, stat: str) -> None:
    """Shared handler for all /brzcards stats <stat> subcommands."""
    await interaction.response.defer(thinking=True)
    try:
        players = bot_cache.get_or_fetch_stat_ranking(stat)
        if not players:
            await interaction.followup.send(
                f"Nenhum jogador encontrado no ranking de {stat.upper()}."
            )
            return

        embed = get_stat_ranking_embed(players, stat)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        logger.exception("Error fetching stat ranking for %s", stat)
        await interaction.followup.send(
            f"Ocorreu um erro ao carregar o ranking de {stat.upper()}."
        )


@stats_group.command(name="aim", description="Ranking de AIM — Season 8")
async def stats_aim(interaction: discord.Interaction) -> None:
    await _handle_stat_ranking(interaction, "AIM")


@stats_group.command(name="imp", description="Ranking de IMP (Impact) — Season 8")
async def stats_imp(interaction: discord.Interaction) -> None:
    await _handle_stat_ranking(interaction, "IMP")


@stats_group.command(name="utl", description="Ranking de UTL (Utility) — Season 8")
async def stats_utl(interaction: discord.Interaction) -> None:
    await _handle_stat_ranking(interaction, "UTL")


@stats_group.command(name="con", description="Ranking de CON (Consistency) — Season 8")
async def stats_con(interaction: discord.Interaction) -> None:
    await _handle_stat_ranking(interaction, "CON")


@stats_group.command(name="int", description="Ranking de INT (Intelligence) — Season 8")
async def stats_int(interaction: discord.Interaction) -> None:
    await _handle_stat_ranking(interaction, "INT")


@stats_group.command(name="exp", description="Ranking de EXP (Experience) — Season 8")
async def stats_exp(interaction: discord.Interaction) -> None:
    await _handle_stat_ranking(interaction, "EXP")


# -------------------------------------------------------------------
# /brzcards ruler
# -------------------------------------------------------------------

@brzcards_group.command(name="ruler", description="Régua bruta da comunidade — quem lidera cada variável original.")
async def ruler(interaction: discord.Interaction) -> None:
    """
    Mostra a régua bruta consolidada da comunidade (Season 8).
    """
    await interaction.response.defer(thinking=True)
    try:
        ruler_data = bot_cache.get_or_fetch_ruler()
        if not ruler_data:
            await interaction.followup.send(
                "Nenhum dado encontrado para a régua da comunidade."
            )
            return

        embed = get_ruler_embed(ruler_data)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        logger.exception("Error fetching ruler data")
        await interaction.followup.send(
            "Ocorreu um erro ao carregar a régua da comunidade."
        )


# -------------------------------------------------------------------
# /brzcards refresh-cache  (admin only)
# -------------------------------------------------------------------

@brzcards_group.command(
    name="refresh-cache",
    description="Limpa o cache de dados do bot (admin only).",
)
async def refresh_cache(interaction: discord.Interaction) -> None:
    """
    Admin-only command to clear the in-memory BigQuery data cache.
    """
    perms = interaction.user.guild_permissions
    if not (perms.administrator or perms.manage_guild):
        await interaction.response.send_message(
            "Você não tem permissão para usar este comando.",
            ephemeral=True,
        )
        return

    bot_cache.clear()
    logger.info(
        "Cache cleared by user %s (%s).",
        interaction.user.display_name,
        interaction.user.id,
    )
    await interaction.response.send_message(
        "Cache limpo com sucesso. A próxima consulta buscará dados atualizados no BigQuery.",
        ephemeral=True,
    )


# ===================================================================
# Register & Run
# ===================================================================

client.tree.add_command(brzcards_group)


client.run(DISCORD_BOT_TOKEN)