"""
upload_brz_cards_to_bq.py
==========================
Carrega os CSVs do projeto brz-cards para o BigQuery.

Tabelas e modos de escrita:
    players_enriched  <- WRITE_TRUNCATE  (estado atual dos players)
    match_ids         <- WRITE_APPEND    (acumula por temporada; deduplica antes de inserir)
    season8_stats     <- WRITE_TRUNCATE  (stats agregadas da Season 8)
    card_scores       <- WRITE_APPEND    (historico de scores; coluna uploaded_at)
    manual_roles      <- WRITE_TRUNCATE  (tabela de referencia)

Uso:
    python src/bigquery/upload_brz_cards_to_bq.py
    python src/bigquery/upload_brz_cards_to_bq.py --season season8

Requer:
    gcloud auth application-default login   (ou GOOGLE_APPLICATION_CREDENTIALS)
    GCP_PROJECT_ID e BQ_DATASET_ID no .env
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from google.api_core.exceptions import NotFound
from google.cloud import bigquery
from google.cloud.bigquery import SchemaField, WriteDisposition

import os

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "brz-esports")
BQ_DATASET_ID = os.getenv("BQ_DATASET_ID", "brz_esports")
BQ_LOCATION = os.getenv("BQ_LOCATION", "US")

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

SCHEMA_PLAYERS_ENRICHED = [
    SchemaField("faceit_nickname_input",          "STRING"),
    SchemaField("faceit_nickname_official",        "STRING"),
    SchemaField("faceit_player_id",               "STRING"),
    SchemaField("country",                        "STRING"),
    SchemaField("steam_id_64",                    "STRING"),   # grande demais para INT64
    SchemaField("steam_nickname",                 "STRING"),
    SchemaField("cs2_skill_level",               "INTEGER"),
    SchemaField("cs2_faceit_elo",                "INTEGER"),
    SchemaField("cs2_game_player_id",            "STRING"),   # grande demais para INT64
    SchemaField("cs2_game_player_name",          "STRING"),
    SchemaField("avatar",                        "STRING"),
    SchemaField("faceit_url",                    "STRING"),
    SchemaField("activated_at",                  "TIMESTAMP"),
    SchemaField("highest_lifetime_faceit_level", "INTEGER"),
    SchemaField("lifetime_faceit_matches",       "INTEGER"),
    SchemaField("highest_lifetime_faceit_elo",   "INTEGER"),
    SchemaField("faceit_tracker_highest_elo",    "INTEGER"),
    SchemaField("peak_elo_source",               "STRING"),
    SchemaField("peak_elo_updated_at",           "TIMESTAMP"),
    SchemaField("peak_elo_url_nickname",         "STRING"),
]

SCHEMA_MATCH_IDS = [
    SchemaField("season",           "STRING"),    # adicionada pelo script
    SchemaField("faceit_nickname",  "STRING"),
    SchemaField("faceit_player_id", "STRING"),
    SchemaField("match_id",         "STRING"),
    SchemaField("game_id",          "STRING"),
    SchemaField("finished_at",      "TIMESTAMP"), # epoch -> convertido
    SchemaField("started_at",       "TIMESTAMP"), # epoch -> convertido
    SchemaField("competition_name", "STRING"),
    SchemaField("match_type",       "STRING"),
    SchemaField("game_mode",        "STRING"),
    SchemaField("max_players",      "INTEGER"),
    SchemaField("teams_size",       "INTEGER"),
]

SCHEMA_SEASON8_STATS = [
    SchemaField("faceit_nickname",                   "STRING"),
    SchemaField("faceit_player_id",                  "STRING"),
    SchemaField("country",                           "STRING"),
    SchemaField("steam_id_64",                       "STRING"),
    SchemaField("cs2_skill_level",                  "FLOAT"),
    SchemaField("cs2_faceit_elo",                   "FLOAT"),
    SchemaField("Average_K_D_Ratio",                "FLOAT"),
    SchemaField("ADR",                              "FLOAT"),
    SchemaField("Average_Headshots",                "FLOAT"),
    SchemaField("Win_Rate",                         "FLOAT"),
    SchemaField("Matches",                          "INTEGER"),
    SchemaField("Total_Matches",                    "INTEGER"),
    SchemaField("Wins",                             "INTEGER"),
    SchemaField("Recent_Results",                   "STRING"),
    SchemaField("Current_Win_Streak",               "INTEGER"),
    SchemaField("Longest_Win_Streak",               "INTEGER"),
    SchemaField("Average_K_R_Ratio",                "FLOAT"),
    SchemaField("Entry_Success_Rate",               "FLOAT"),
    SchemaField("Entry_Rate",                       "FLOAT"),
    SchemaField("Total_Entry_Count",                "INTEGER"),
    SchemaField("Total_Entry_Wins",                 "INTEGER"),
    SchemaField("Utility_Damage_per_Round",         "FLOAT"),
    SchemaField("Utility_Success_Rate",             "FLOAT"),
    SchemaField("Utility_Usage_per_Round",          "FLOAT"),
    SchemaField("Flash_Success_Rate",               "FLOAT"),
    SchemaField("Flashes_per_Round",                "FLOAT"),
    SchemaField("Enemies_Flashed_per_Round",        "FLOAT"),
    SchemaField("Total_Utility_Damage",             "INTEGER"),
    SchemaField("Total_Enemies_Flashed",            "INTEGER"),
    SchemaField("Total_Flash_Successes",            "INTEGER"),
    SchemaField("Total_Flash_Count",                "INTEGER"),
    SchemaField("1v1_Win_Rate",                     "FLOAT"),
    SchemaField("1v2_Win_Rate",                     "FLOAT"),
    SchemaField("Total_1v1_Count",                  "INTEGER"),
    SchemaField("Total_1v1_Wins",                   "INTEGER"),
    SchemaField("Total_1v2_Count",                  "INTEGER"),
    SchemaField("Total_1v2_Wins",                   "INTEGER"),
    SchemaField("Sniper_Kill_Rate",                 "FLOAT"),
    SchemaField("Sniper_Kill_Rate_per_Round",       "FLOAT"),
    SchemaField("Total_Sniper_Kills",               "INTEGER"),
    SchemaField("Total_Damage",                     "INTEGER"),
    SchemaField("Total_Rounds_with_extended_stats", "INTEGER"),
    SchemaField("Total_Kills_with_extended_stats",  "INTEGER"),
]

SCHEMA_CARD_SCORES = [
    SchemaField("uploaded_at",                    "TIMESTAMP"),  # adicionada pelo script
    SchemaField("faceit_nickname",                "STRING"),
    SchemaField("faceit_player_id",              "STRING"),
    SchemaField("status",                        "STRING"),
    SchemaField("role",                          "STRING"),
    SchemaField("season8_matches",               "INTEGER"),
    SchemaField("current_faceit_level",          "INTEGER"),
    SchemaField("current_faceit_elo",            "INTEGER"),
    SchemaField("faceit_tracker_highest_elo",    "INTEGER"),
    SchemaField("known_peak_elo",                "INTEGER"),
    SchemaField("lifetime_faceit_matches",       "INTEGER"),
    SchemaField("AIM",                           "FLOAT"),
    SchemaField("IMP",                           "FLOAT"),
    SchemaField("UTL",                           "FLOAT"),
    SchemaField("CON",                           "FLOAT"),
    SchemaField("INT",                           "FLOAT"),
    SchemaField("EXP",                           "FLOAT"),
    SchemaField("BASE_OVERALL",                  "FLOAT"),
    SchemaField("FACEIT_LEVEL_MULTIPLIER",       "FLOAT"),
    SchemaField("OVERALL",                       "INTEGER"),
    SchemaField("KD_score",                      "FLOAT"),
    SchemaField("KR_score",                      "FLOAT"),
    SchemaField("ADR_score",                     "FLOAT"),
    SchemaField("HS_score",                      "FLOAT"),
    SchemaField("EntryRate_score",               "FLOAT"),
    SchemaField("EntrySuccess_score",            "FLOAT"),
    SchemaField("UtilitySuccess_score",          "FLOAT"),
    SchemaField("UtilityDamageRound_score",      "FLOAT"),
    SchemaField("EnemiesFlashedRound_score",     "FLOAT"),
    SchemaField("FlashSuccess_score",            "FLOAT"),
    SchemaField("UtilityUsageRound_score",       "FLOAT"),
    SchemaField("FlashesRound_score",            "FLOAT"),
    SchemaField("WinRate_score",                 "FLOAT"),
    SchemaField("Season8MatchesVolume_score",    "FLOAT"),
    SchemaField("PerformanceConsistency_score",  "FLOAT"),
    SchemaField("OneVOneWinRate_score",          "FLOAT"),
    SchemaField("OneVTwoWinRate_score",          "FLOAT"),
    SchemaField("ClutchVolume_score",            "FLOAT"),
    SchemaField("ClutchScore",                   "FLOAT"),
    SchemaField("PeakElo_score",                 "FLOAT"),
    SchemaField("LifetimeMatchesVolume_score",   "FLOAT"),
]

SCHEMA_MANUAL_ROLES = [
    SchemaField("faceit_nickname", "STRING"),
    SchemaField("role",            "STRING"),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def ensure_dataset(client: bigquery.Client) -> None:
    """Cria o dataset se nao existir."""
    dataset_ref = bigquery.Dataset(f"{GCP_PROJECT_ID}.{BQ_DATASET_ID}")
    dataset_ref.location = BQ_LOCATION
    try:
        client.get_dataset(dataset_ref)
        print(f"[OK] Dataset ja existe: {BQ_DATASET_ID}")
    except NotFound:
        client.create_dataset(dataset_ref, exists_ok=True)
        print(f"[OK] Dataset criado: {BQ_DATASET_ID}")


def table_ref(table_name: str) -> str:
    return f"{GCP_PROJECT_ID}.{BQ_DATASET_ID}.{table_name}"


def sanitize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Renomeia colunas com espacos/caracteres especiais para usar underscore."""
    df = df.copy()
    df.columns = (
        df.columns
        .str.replace(r"[^\w]", "_", regex=True)
        .str.replace(r"_+", "_", regex=True)
        .str.strip("_")
    )
    return df


def upload_table(
    client: bigquery.Client,
    df: pd.DataFrame,
    table_name: str,
    schema: list[SchemaField],
    write_disposition: WriteDisposition,
    label: str,
) -> None:
    """Faz upload de um DataFrame para uma tabela BQ."""
    ref = table_ref(table_name)
    job_config = bigquery.LoadJobConfig(
        schema=schema,
        write_disposition=write_disposition,
        # Timestamp columns: send as ISO string, BQ converte automaticamente
    )

    print(f"\n[{label}] Carregando {len(df)} rows -> {ref}")
    print(f"         Modo: {write_disposition}")

    job = client.load_table_from_dataframe(df, ref, job_config=job_config)
    job.result()  # aguarda conclusao

    table = client.get_table(ref)
    print(f"[OK] [{label}] {table.num_rows} rows no BQ | {table.modified.strftime('%Y-%m-%d %H:%M UTC')}")


def delete_season_from_match_ids(client: bigquery.Client, season: str) -> None:
    """
    Remove linhas existentes da temporada antes do APPEND,
    garantindo que re-executar o script nao duplique dados.
    """
    ref = table_ref("match_ids")

    # Verifica se a tabela existe
    try:
        client.get_table(ref)
    except NotFound:
        return  # tabela ainda nao existe, nada a deletar

    query = f"DELETE FROM `{ref}` WHERE season = @season"
    job_config = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("season", "STRING", season)]
    )
    job = client.query(query, job_config=job_config)
    job.result()
    print(f"[OK] match_ids: registros antigos da season '{season}' removidos antes do APPEND.")


def delete_card_scores_for_today(client: bigquery.Client, today_prefix: str) -> None:
    """
    Remove entradas de card_scores com o mesmo prefixo de data (YYYY-MM-DD),
    garantindo que re-executar no mesmo dia nao duplique.
    """
    ref = table_ref("card_scores")
    try:
        client.get_table(ref)
    except NotFound:
        return

    query = f"""
        DELETE FROM `{ref}`
        WHERE DATE(uploaded_at) = DATE('{today_prefix}')
    """
    job = client.query(query)
    job.result()
    print(f"[OK] card_scores: entradas de {today_prefix} removidas antes do APPEND.")


# ---------------------------------------------------------------------------
# Preparacao dos DataFrames
# ---------------------------------------------------------------------------


def prepare_players_enriched() -> pd.DataFrame:
    path = DATA_DIR / "brz_faceit_players_enriched.csv"
    df = pd.read_csv(path, dtype=str)

    # Colunas numericas
    for col in ["cs2_skill_level", "cs2_faceit_elo", "highest_lifetime_faceit_level",
                "lifetime_faceit_matches", "highest_lifetime_faceit_elo", "faceit_tracker_highest_elo"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    # Timestamps
    for col in ["activated_at", "peak_elo_updated_at"]:
        df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)

    return df


def prepare_match_ids(season: str) -> pd.DataFrame:
    path = DATA_DIR / "brz_faceit_season8_match_ids.csv"
    df = pd.read_csv(path, dtype=str)

    # Adiciona coluna season
    df.insert(0, "season", season)

    # Epoch -> Timestamp
    for col in ["finished_at", "started_at"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df[col] = pd.to_datetime(df[col], unit="s", errors="coerce", utc=True)

    # Numericos
    for col in ["max_players", "teams_size"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    return df


def prepare_season8_stats() -> pd.DataFrame:
    path = DATA_DIR / "brz_faceit_season8_stats.csv"
    df = pd.read_csv(path)
    df = sanitize_columns(df)

    # steam_id_64 como STRING
    df["steam_id_64"] = df["steam_id_64"].apply(
        lambda x: str(int(x)) if pd.notna(x) else None
    )

    # Colunas inteiras
    int_cols = [
        "Matches", "Total_Matches", "Wins", "Current_Win_Streak", "Longest_Win_Streak",
        "Total_Entry_Count", "Total_Entry_Wins", "Total_Utility_Damage",
        "Total_Enemies_Flashed", "Total_Flash_Successes", "Total_Flash_Count",
        "Total_1v1_Count", "Total_1v1_Wins", "Total_1v2_Count", "Total_1v2_Wins",
        "Total_Sniper_Kills", "Total_Damage", "Total_Rounds_extended_stats",
        "Total_Kills_extended_stats",
    ]
    for col in int_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    # Garante que Recent_Results seja string
    if "Recent_Results" in df.columns:
        df["Recent_Results"] = df["Recent_Results"].astype(str)

    return df


def prepare_card_scores(uploaded_at: datetime) -> pd.DataFrame:
    path = DATA_DIR / "brz_card_scores_v2.csv"
    df = pd.read_csv(path)

    # Adiciona timestamp do upload
    df.insert(0, "uploaded_at", uploaded_at)

    # Colunas inteiras
    int_cols = [
        "season8_matches", "current_faceit_level", "current_faceit_elo",
        "faceit_tracker_highest_elo", "known_peak_elo", "lifetime_faceit_matches", "OVERALL",
    ]
    for col in int_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    return df


def prepare_manual_roles() -> pd.DataFrame:
    path = DATA_DIR / "brz_manual_roles.csv"
    return pd.read_csv(path, dtype=str)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload brz-cards CSVs to BigQuery")
    parser.add_argument(
        "--season",
        default="season8",
        help="Identificador da temporada para a tabela match_ids (default: season8)",
    )
    args = parser.parse_args()
    season = args.season

    now_utc = datetime.now(timezone.utc)
    today_str = now_utc.strftime("%Y-%m-%d")

    print("=" * 60)
    print("upload_brz_cards_to_bq.py")
    print("=" * 60)
    print(f"Project  : {GCP_PROJECT_ID}")
    print(f"Dataset  : {BQ_DATASET_ID}")
    print(f"Location : {BQ_LOCATION}")
    print(f"Season   : {season}")
    print(f"Run time : {now_utc.isoformat()}")
    print("=" * 60)

    client = bigquery.Client(project=GCP_PROJECT_ID)
    ensure_dataset(client)

    errors: list[str] = []

    # ------------------------------------------------------------------
    # 1. players_enriched  (WRITE_TRUNCATE)
    # ------------------------------------------------------------------
    try:
        df = prepare_players_enriched()
        upload_table(
            client, df,
            table_name="players_enriched",
            schema=SCHEMA_PLAYERS_ENRICHED,
            write_disposition=WriteDisposition.WRITE_TRUNCATE,
            label="1/5 players_enriched",
        )
    except Exception as exc:
        print(f"[ERROR] players_enriched: {exc}")
        errors.append(f"players_enriched: {exc}")

    # ------------------------------------------------------------------
    # 2. match_ids  (WRITE_APPEND com dedup por season)
    # ------------------------------------------------------------------
    try:
        delete_season_from_match_ids(client, season)
        df = prepare_match_ids(season)
        upload_table(
            client, df,
            table_name="match_ids",
            schema=SCHEMA_MATCH_IDS,
            write_disposition=WriteDisposition.WRITE_APPEND,
            label="2/5 match_ids",
        )
    except Exception as exc:
        print(f"[ERROR] match_ids: {exc}")
        errors.append(f"match_ids: {exc}")

    # ------------------------------------------------------------------
    # 3. season8_stats  (WRITE_TRUNCATE)
    # ------------------------------------------------------------------
    try:
        df = prepare_season8_stats()
        upload_table(
            client, df,
            table_name="season8_stats",
            schema=SCHEMA_SEASON8_STATS,
            write_disposition=WriteDisposition.WRITE_TRUNCATE,
            label="3/5 season8_stats",
        )
    except Exception as exc:
        print(f"[ERROR] season8_stats: {exc}")
        errors.append(f"season8_stats: {exc}")

    # ------------------------------------------------------------------
    # 4. card_scores  (WRITE_APPEND com dedup por data)
    # ------------------------------------------------------------------
    try:
        delete_card_scores_for_today(client, today_str)
        df = prepare_card_scores(now_utc)
        upload_table(
            client, df,
            table_name="card_scores",
            schema=SCHEMA_CARD_SCORES,
            write_disposition=WriteDisposition.WRITE_APPEND,
            label="4/5 card_scores",
        )
    except Exception as exc:
        print(f"[ERROR] card_scores: {exc}")
        errors.append(f"card_scores: {exc}")

    # ------------------------------------------------------------------
    # 5. manual_roles  (WRITE_TRUNCATE)
    # ------------------------------------------------------------------
    try:
        df = prepare_manual_roles()
        upload_table(
            client, df,
            table_name="manual_roles",
            schema=SCHEMA_MANUAL_ROLES,
            write_disposition=WriteDisposition.WRITE_TRUNCATE,
            label="5/5 manual_roles",
        )
    except Exception as exc:
        print(f"[ERROR] manual_roles: {exc}")
        errors.append(f"manual_roles: {exc}")

    # ------------------------------------------------------------------
    # Resumo
    # ------------------------------------------------------------------
    print()
    print("=" * 60)
    print("RESUMO")
    print("=" * 60)
    total = 5
    ok = total - len(errors)
    print(f"  Tabelas enviadas com sucesso : {ok}/{total}")
    if errors:
        print(f"  Erros ({len(errors)}):")
        for e in errors:
            print(f"    -> {e}")
    else:
        print("  Todos os uploads concluidos sem erros.")
    print("=" * 60)

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
