import math
import os
import time

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


class PlayerSelect(discord.ui.Select):
    def __init__(self, players: list[dict], page: int, total_pages: int):
        options = []
        for p in players:
            label = str(p["faceit_nickname"])
            if p["status"] == "ACTIVE":
                desc = f"{p['overall']} OVR"
            else:
                desc = "INACTIVE"
            
            options.append(discord.SelectOption(
                label=label,
                description=desc,
                value=label
            ))
            
        super().__init__(
            placeholder=f"Selecione um jogador (Página {page}/{total_pages})...",
            min_values=1,
            max_values=1,
            options=options,
        )
        
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        player_name = self.values[0]
        
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
            player_identifier = (
                card_data.get("player_id")
                or card_data.get("player_slug")
                or card_data.get("player_code")
                or normalize_player_identifier(player_name)
            )

            display_name = (
                card_data.get("display_name")
                or card_data.get("player_name")
                or player_name
            )
            overall_brz = card_data.get("overall_brz")
            score_version = card_data.get("score_version") or "unknown_version"
            calculated_at = card_data.get("calculated_at")

            if calculated_at:
                # Converte data para string no formato AAAAMMDD
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
                # Gera a carta e salva no caminho esperado
                card_path = generate_player_card(player_identifier, output_path=expected_path)

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


class PlayerPaginationView(discord.ui.View):
    def __init__(self, players: list[dict], page: int = 1):
        super().__init__(timeout=180)
        self.players = players
        self.page = page
        self.per_page = 25
        self.total_pages = math.ceil(len(players) / self.per_page) if players else 1
        self.update_items()

    def update_items(self):
        self.clear_items()
        
        start_idx = (self.page - 1) * self.per_page
        end_idx = start_idx + self.per_page
        page_players = self.players[start_idx:end_idx]
        
        if page_players:
            self.add_item(PlayerSelect(page_players, self.page, self.total_pages))
        
        prev_button = discord.ui.Button(label="Anterior", style=discord.ButtonStyle.secondary, disabled=(self.page == 1))
        prev_button.callback = self.prev_page
        self.add_item(prev_button)
        
        next_button = discord.ui.Button(label="Próxima", style=discord.ButtonStyle.primary, disabled=(self.page >= self.total_pages))
        next_button.callback = self.next_page
        self.add_item(next_button)

        close_button = discord.ui.Button(label="Fechar", style=discord.ButtonStyle.danger)
        close_button.callback = self.close_view
        self.add_item(close_button)

    async def prev_page(self, interaction: discord.Interaction):
        self.page -= 1
        self.update_items()
        await interaction.response.edit_message(view=self)

    async def next_page(self, interaction: discord.Interaction):
        self.page += 1
        self.update_items()
        await interaction.response.edit_message(view=self)

    async def close_view(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="Menu fechado.", view=None)


class RankingPaginationView(discord.ui.View):
    def __init__(self, players: list[dict], page: int = 1):
        super().__init__(timeout=180)
        self.players = players
        self.page = page
        self.per_page = 10
        self.total_pages = math.ceil(len(players) / self.per_page) if players else 1
        self.update_items()

    def get_embed(self) -> discord.Embed:
        embed = discord.Embed(title="🏆 Ranking BRz Cards — Season 8", color=discord.Color.gold())
        start_idx = (self.page - 1) * self.per_page
        end_idx = start_idx + self.per_page
        page_players = self.players[start_idx:end_idx]

        desc_lines = []
        for i, p in enumerate(page_players):
            pos = start_idx + i + 1
            line = f"**{pos}.** {p['faceit_nickname']} — **{p['overall']} OVR** — {p['role']} — lvl {p['current_faceit_level']} — {p['season8_matches']} jogos"
            desc_lines.append(line)
        
        embed.description = "\n".join(desc_lines)
        embed.set_footer(text=f"Página {self.page}/{self.total_pages}")
        return embed

    def update_items(self):
        self.clear_items()
        
        prev_button = discord.ui.Button(label="Anterior", style=discord.ButtonStyle.secondary, disabled=(self.page <= 1))
        prev_button.callback = self.prev_page
        self.add_item(prev_button)
        
        next_button = discord.ui.Button(label="Próxima", style=discord.ButtonStyle.primary, disabled=(self.page >= self.total_pages))
        next_button.callback = self.next_page
        self.add_item(next_button)

        close_button = discord.ui.Button(label="Fechar", style=discord.ButtonStyle.danger)
        close_button.callback = self.close_view
        self.add_item(close_button)

    async def prev_page(self, interaction: discord.Interaction):
        self.page -= 1
        self.update_items()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def next_page(self, interaction: discord.Interaction):
        self.page += 1
        self.update_items()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def close_view(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="Menu de ranking fechado.", embed=None, view=None)


brzcards_group = app_commands.Group(name="brzcards", description="Comandos relacionados às Cartas BRz")

@brzcards_group.command(name="card", description="Mostra um menu interativo para escolher o player e gerar a carta BRz.")
async def card(interaction: discord.Interaction) -> None:
    """
    Mostra um menu interativo para escolher o player e gerar a carta BRz.
    """
    try:
        players = _get_cached_players()
        if not players:
            await interaction.response.send_message("Nenhum jogador encontrado no momento.", ephemeral=True)
            return
            
        view = PlayerPaginationView(players, page=1)
        await interaction.response.send_message("Escolha um player para gerar a carta BRz:", view=view, ephemeral=True)
    except Exception as e:
        print(f"Error fetching player list: {e}")
        await interaction.response.send_message("Ocorreu um erro ao carregar a lista de jogadores.", ephemeral=True)

@brzcards_group.command(name="ranking", description="Mostra o ranking oficial da Season 8.")
async def ranking(interaction: discord.Interaction) -> None:
    """
    Mostra o ranking público da Season 8 com paginação.
    """
    try:
        players = _get_cached_ranking()
        if not players:
            await interaction.response.send_message("Nenhum jogador encontrado no ranking.", ephemeral=True)
            return

        view = RankingPaginationView(players, page=1)
        await interaction.response.send_message(embed=view.get_embed(), view=view)
    except Exception as e:
        print(f"Error fetching ranking: {e}")
        await interaction.response.send_message("Ocorreu um erro ao carregar o ranking.", ephemeral=True)

client.tree.add_command(brzcards_group)


client.run(DISCORD_BOT_TOKEN)