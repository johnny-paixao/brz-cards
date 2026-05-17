import json
import os
import uuid
from typing import Any

from google.cloud import bigquery
from dotenv import load_dotenv


load_dotenv()

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "brz-esports")
DATASET_ID = os.getenv("BQ_DATASET_ID", "brz_esports")


def get_bigquery_client() -> bigquery.Client:
    """
    Create and return a BigQuery client using local Google Cloud authentication.
    """
    return bigquery.Client(project=PROJECT_ID)


def get_latest_player_card(display_name: str) -> dict | None:
    """
    Get the latest BRz card score for a player by display name.
    """
    client = get_bigquery_client()

    query = f"""
        SELECT
          faceit_player_id AS player_id,
          faceit_nickname AS display_name,
          OVERALL AS overall_brz,
          AIM AS aim,
          IMP AS impact,
          UTL AS utility,
          CON AS consistency,
          INT AS intelligence,
          EXP AS experience,
          role,
          'Unknown' AS tier,
          season8_matches AS matches_analyzed,
          'v2' AS score_version,
          uploaded_at AS calculated_at
        FROM `{PROJECT_ID}.{DATASET_ID}.card_scores`
        WHERE LOWER(faceit_nickname) = LOWER(@display_name)
        ORDER BY uploaded_at DESC
        LIMIT 1
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("display_name", "STRING", display_name)
        ],
        maximum_bytes_billed=20 * 1024 * 1024,
    )

    query_job = client.query(query, job_config=job_config)
    rows = list(query_job.result())

    if not rows:
        return None

    row = rows[0]

    return {
        "player_id": row.player_id,
        "display_name": row.display_name,
        "overall_brz": row.overall_brz,
        "aim": row.aim,
        "impact": row.impact,
        "utility": row.utility,
        "consistency": row.consistency,
        "intelligence": row.intelligence,
        "experience": row.experience,
        "role": row.role,
        "tier": row.tier,
        "matches_analyzed": row.matches_analyzed,
        "score_version": row.score_version,
        "calculated_at": row.calculated_at,
    }


def get_all_card_players() -> list[dict]:
    """
    Get a list of all players and their overall scores from the latest upload.
    """
    client = get_bigquery_client()

    query = f"""
        SELECT
          faceit_nickname,
          status,
          OVERALL as overall
        FROM `{PROJECT_ID}.{DATASET_ID}.card_scores`
        WHERE 1=1
        QUALIFY ROW_NUMBER() OVER (PARTITION BY faceit_nickname ORDER BY uploaded_at DESC) = 1
        ORDER BY
          CASE WHEN status = 'ACTIVE' THEN 0 ELSE 1 END ASC,
          OVERALL DESC,
          LOWER(faceit_nickname) ASC
    """

    job_config = bigquery.QueryJobConfig(
        maximum_bytes_billed=20 * 1024 * 1024,
    )

    query_job = client.query(query, job_config=job_config)
    
    return [
        {
            "faceit_nickname": row.faceit_nickname,
            "status": row.status,
            "overall": row.overall,
        }
        for row in query_job.result()
    ]


def get_ranking_players() -> list[dict]:
    """
    Get a list of all ACTIVE players for the ranking, sorted by overall and matches.
    """
    client = get_bigquery_client()

    query = f"""
        SELECT
          faceit_nickname,
          role,
          OVERALL as overall,
          season8_matches,
          current_faceit_level,
          current_faceit_elo,
          uploaded_at,
          AIM,
          IMP,
          UTL,
          CON,
          INT as intelligence,
          EXP
        FROM `{PROJECT_ID}.{DATASET_ID}.card_scores`
        WHERE status = 'ACTIVE'
        QUALIFY ROW_NUMBER() OVER (PARTITION BY faceit_nickname ORDER BY uploaded_at DESC) = 1
        ORDER BY OVERALL DESC, season8_matches DESC
    """

    job_config = bigquery.QueryJobConfig(
        maximum_bytes_billed=20 * 1024 * 1024,
    )

    query_job = client.query(query, job_config=job_config)
    
    return [dict(row.items()) for row in query_job.result()]


def get_active_players_with_steam64() -> list[dict]:
    """
    Get active players that have a Steam64 ID.
    """
    client = get_bigquery_client()

    query = f"""
        SELECT
          player_id,
          display_name,
          steam64_id,
          leetify_profile_id,
          leetify_name
        FROM `{PROJECT_ID}.{DATASET_ID}.players`
        WHERE active = TRUE
          AND steam64_id IS NOT NULL
    """

    query_job = client.query(
        query,
        job_config=bigquery.QueryJobConfig(
            maximum_bytes_billed=20 * 1024 * 1024,
        ),
    )

    return [dict(row.items()) for row in query_job.result()]


def insert_api_snapshot(
    player_id: str,
    source: str,
    endpoint: str,
    request_url: str,
    payload: dict | None,
    status_code: int | None,
    error_message: str | None,
) -> str:
    """
    Insert a raw API response into api_snapshots and return the snapshot_id.
    """
    client = get_bigquery_client()
    snapshot_id = str(uuid.uuid4())

    payload_json = json.dumps(payload or {}, ensure_ascii=False)

    query = f"""
        INSERT INTO `{PROJECT_ID}.{DATASET_ID}.api_snapshots` (
          snapshot_id,
          player_id,
          source,
          endpoint,
          request_url,
          payload_json,
          status_code,
          error_message,
          collected_at
        )
        VALUES (
          @snapshot_id,
          @player_id,
          @source,
          @endpoint,
          @request_url,
          PARSE_JSON(@payload_json),
          @status_code,
          @error_message,
          CURRENT_TIMESTAMP()
        )
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("snapshot_id", "STRING", snapshot_id),
            bigquery.ScalarQueryParameter("player_id", "STRING", player_id),
            bigquery.ScalarQueryParameter("source", "STRING", source),
            bigquery.ScalarQueryParameter("endpoint", "STRING", endpoint),
            bigquery.ScalarQueryParameter("request_url", "STRING", request_url),
            bigquery.ScalarQueryParameter("payload_json", "STRING", payload_json),
            bigquery.ScalarQueryParameter("status_code", "INT64", status_code),
            bigquery.ScalarQueryParameter("error_message", "STRING", error_message),
        ],
        maximum_bytes_billed=20 * 1024 * 1024,
    )

    client.query(query, job_config=job_config).result()

    return snapshot_id


def update_player_leetify_profile(
    player_id: str,
    steam64_id: str | None,
    leetify_profile_id: str | None,
    leetify_name: str | None,
) -> None:
    """
    Update Leetify identity fields in players table.
    """
    client = get_bigquery_client()

    query = f"""
        UPDATE `{PROJECT_ID}.{DATASET_ID}.players`
        SET
          steam64_id = COALESCE(@steam64_id, steam64_id),
          leetify_profile_id = COALESCE(@leetify_profile_id, leetify_profile_id),
          leetify_name = COALESCE(@leetify_name, leetify_name),
          updated_at = CURRENT_TIMESTAMP()
        WHERE player_id = @player_id
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("player_id", "STRING", player_id),
            bigquery.ScalarQueryParameter("steam64_id", "STRING", steam64_id),
            bigquery.ScalarQueryParameter(
                "leetify_profile_id",
                "STRING",
                leetify_profile_id,
            ),
            bigquery.ScalarQueryParameter("leetify_name", "STRING", leetify_name),
        ],
        maximum_bytes_billed=20 * 1024 * 1024,
    )

    client.query(query, job_config=job_config).result()


def upsert_leetify_recent_matches(
    player_id: str,
    matches: list[dict[str, Any]],
    raw_snapshot_id: str,
) -> int:
    """
    Upsert Leetify recent matches into player_match_stats.

    Returns the number of matches processed.
    """
    client = get_bigquery_client()
    processed = 0

    query = f"""
        MERGE `{PROJECT_ID}.{DATASET_ID}.player_match_stats` AS target
        USING (
          SELECT
            @player_id AS player_id,
            @match_id AS match_id,
            'leetify' AS source
        ) AS source_data
        ON target.player_id = source_data.player_id
           AND target.match_id = source_data.match_id
           AND target.source = source_data.source
        WHEN MATCHED THEN
          UPDATE SET
            match_date = SAFE_CAST(@match_date AS TIMESTAMP),
            map_name = @map_name,
            game_mode = @game_mode,
            match_source = @match_source,
            team_result = @team_result,
            leetify_rating = @leetify_rating,
            accuracy_enemy_spotted = @accuracy_enemy_spotted,
            accuracy_head = @accuracy_head,
            preaim = @preaim,
            reaction_time_ms = @reaction_time_ms,
            spray_accuracy = @spray_accuracy,
            rank = @rank,
            rank_type = @rank_type,
            raw_snapshot_id = @raw_snapshot_id,
            created_at = CURRENT_TIMESTAMP()
        WHEN NOT MATCHED THEN
          INSERT (
            player_id,
            match_id,
            source,
            match_date,
            map_name,
            game_mode,
            match_source,
            team_result,
            kills,
            deaths,
            assists,
            kd_ratio,
            adr,
            headshot_percentage,
            leetify_rating,
            aim_score,
            utility_score,
            opening_duel_score,
            clutch_score,
            impact_score,
            raw_snapshot_id,
            created_at,
            accuracy_enemy_spotted,
            accuracy_head,
            preaim,
            reaction_time_ms,
            spray_accuracy,
            rank,
            rank_type
          )
          VALUES (
            @player_id,
            @match_id,
            'leetify',
            SAFE_CAST(@match_date AS TIMESTAMP),
            @map_name,
            @game_mode,
            @match_source,
            @team_result,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL,
            @leetify_rating,
            NULL,
            NULL,
            NULL,
            NULL,
            NULL,
            @raw_snapshot_id,
            CURRENT_TIMESTAMP(),
            @accuracy_enemy_spotted,
            @accuracy_head,
            @preaim,
            @reaction_time_ms,
            @spray_accuracy,
            @rank,
            @rank_type
          )
    """

    for match in matches:
        match_id = match.get("id")

        if not match_id:
            continue

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("player_id", "STRING", player_id),
                bigquery.ScalarQueryParameter("match_id", "STRING", match_id),
                bigquery.ScalarQueryParameter(
                    "match_date",
                    "STRING",
                    match.get("finished_at"),
                ),
                bigquery.ScalarQueryParameter("map_name", "STRING", match.get("map_name")),
                bigquery.ScalarQueryParameter(
                    "game_mode",
                    "STRING",
                    match.get("data_source"),
                ),
                bigquery.ScalarQueryParameter(
                    "match_source",
                    "STRING",
                    match.get("data_source"),
                ),
                bigquery.ScalarQueryParameter(
                    "team_result",
                    "STRING",
                    match.get("outcome"),
                ),
                bigquery.ScalarQueryParameter(
                    "leetify_rating",
                    "FLOAT64",
                    match.get("leetify_rating"),
                ),
                bigquery.ScalarQueryParameter(
                    "accuracy_enemy_spotted",
                    "FLOAT64",
                    match.get("accuracy_enemy_spotted"),
                ),
                bigquery.ScalarQueryParameter(
                    "accuracy_head",
                    "FLOAT64",
                    match.get("accuracy_head"),
                ),
                bigquery.ScalarQueryParameter(
                    "preaim",
                    "FLOAT64",
                    match.get("preaim"),
                ),
                bigquery.ScalarQueryParameter(
                    "reaction_time_ms",
                    "FLOAT64",
                    match.get("reaction_time_ms"),
                ),
                bigquery.ScalarQueryParameter(
                    "spray_accuracy",
                    "FLOAT64",
                    match.get("spray_accuracy"),
                ),
                bigquery.ScalarQueryParameter("rank", "INT64", match.get("rank")),
                bigquery.ScalarQueryParameter("rank_type", "INT64", match.get("rank_type")),
                bigquery.ScalarQueryParameter(
                    "raw_snapshot_id",
                    "STRING",
                    raw_snapshot_id,
                ),
            ],
            maximum_bytes_billed=20 * 1024 * 1024,
        )

        client.query(query, job_config=job_config).result()
        processed += 1




def get_recent_leetify_match_stats(
    player_id: str,
    limit: int = 100,
    match_source: str | None = "faceit",
) -> list[dict]:
    """
    Get recent normalized Leetify match stats for a player.

    By default, we prioritize FACEIT matches.
    """
    client = get_bigquery_client()

    match_source_filter = ""
    query_parameters = [
        bigquery.ScalarQueryParameter("player_id", "STRING", player_id),
        bigquery.ScalarQueryParameter("limit", "INT64", limit),
    ]

    if match_source:
        match_source_filter = "AND match_source = @match_source"
        query_parameters.append(
            bigquery.ScalarQueryParameter("match_source", "STRING", match_source)
        )

    query = f"""
        SELECT
          player_id,
          match_id,
          source,
          match_source,
          match_date,
          map_name,
          team_result,
          leetify_rating,
          accuracy_enemy_spotted,
          accuracy_head,
          preaim,
          reaction_time_ms,
          spray_accuracy,
          rank,
          rank_type
        FROM `{PROJECT_ID}.{DATASET_ID}.player_match_stats`
        WHERE player_id = @player_id
          AND source = 'leetify'
          {match_source_filter}
        ORDER BY match_date DESC
        LIMIT @limit
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=query_parameters,
        maximum_bytes_billed=50 * 1024 * 1024,
    )

    query_job = client.query(query, job_config=job_config)

    return [dict(row.items()) for row in query_job.result()]


def get_latest_leetify_profile_payload(player_id: str) -> dict | None:
    """
    Get the latest successful raw Leetify profile payload from api_snapshots.
    """
    client = get_bigquery_client()

    query = f"""
        SELECT
          TO_JSON_STRING(payload_json) AS payload_json_string
        FROM `{PROJECT_ID}.{DATASET_ID}.api_snapshots`
        WHERE player_id = @player_id
          AND source = 'leetify'
          AND endpoint = '/v3/profile'
          AND status_code = 200
        ORDER BY collected_at DESC
        LIMIT 1
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("player_id", "STRING", player_id),
        ],
        maximum_bytes_billed=50 * 1024 * 1024,
    )

    rows = list(client.query(query, job_config=job_config).result())

    if not rows:
        return None

    return json.loads(rows[0].payload_json_string)


def insert_player_card_score(card_score: dict) -> str:
    """
    Insert a calculated BRz card score into player_card_scores.
    """
    client = get_bigquery_client()
    card_score_id = str(uuid.uuid4())

    query = f"""
        INSERT INTO `{PROJECT_ID}.{DATASET_ID}.player_card_scores` (
          card_score_id,
          player_id,
          display_name,
          overall_brz,
          aim,
          impact,
          utility,
          consistency,
          clutch,
          experience,
          role,
          tier,
          matches_analyzed,
          score_version,
          calculated_at
        )
        VALUES (
          @card_score_id,
          @player_id,
          @display_name,
          @overall_brz,
          @aim,
          @impact,
          @utility,
          @consistency,
          @clutch,
          @experience,
          @role,
          @tier,
          @matches_analyzed,
          @score_version,
          CURRENT_TIMESTAMP()
        )
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("card_score_id", "STRING", card_score_id),
            bigquery.ScalarQueryParameter("player_id", "STRING", card_score["player_id"]),
            bigquery.ScalarQueryParameter(
                "display_name",
                "STRING",
                card_score["display_name"],
            ),
            bigquery.ScalarQueryParameter(
                "overall_brz",
                "INT64",
                card_score["overall_brz"],
            ),
            bigquery.ScalarQueryParameter("aim", "INT64", card_score["aim"]),
            bigquery.ScalarQueryParameter("impact", "INT64", card_score["impact"]),
            bigquery.ScalarQueryParameter("utility", "INT64", card_score["utility"]),
            bigquery.ScalarQueryParameter(
                "consistency",
                "INT64",
                card_score["consistency"],
            ),
            bigquery.ScalarQueryParameter("clutch", "INT64", card_score["clutch"]),
            bigquery.ScalarQueryParameter(
                "experience",
                "INT64",
                card_score["experience"],
            ),
            bigquery.ScalarQueryParameter("role", "STRING", card_score["role"]),
            bigquery.ScalarQueryParameter("tier", "STRING", card_score["tier"]),
            bigquery.ScalarQueryParameter(
                "matches_analyzed",
                "INT64",
                card_score["matches_analyzed"],
            ),
            bigquery.ScalarQueryParameter(
                "score_version",
                "STRING",
                card_score["score_version"],
            ),
        ],
        maximum_bytes_billed=20 * 1024 * 1024,
    )

    client.query(query, job_config=job_config).result()


    return card_score_id


def update_player_steam_profile(
    player_id: str,
    steam_avatar_url: str | None,
    steam_country_code: str | None,
) -> None:
    """
    Update Steam avatar and raw Steam country fields in players table.

    Important:
    - country_code is the BRz card display country.
    - steam_country_code is the country returned by Steam, when available.
    """
    client = get_bigquery_client()

    query = f"""
        UPDATE `{PROJECT_ID}.{DATASET_ID}.players`
        SET
          steam_avatar_url = COALESCE(@steam_avatar_url, steam_avatar_url),
          steam_country_code = COALESCE(@steam_country_code, steam_country_code),
          updated_at = CURRENT_TIMESTAMP()
        WHERE player_id = @player_id
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("player_id", "STRING", player_id),
            bigquery.ScalarQueryParameter(
                "steam_avatar_url",
                "STRING",
                steam_avatar_url,
            ),
            bigquery.ScalarQueryParameter(
                "steam_country_code",
                "STRING",
                steam_country_code,
            ),
        ],
        maximum_bytes_billed=20 * 1024 * 1024,
    )

    client.query(query, job_config=job_config).result()


def get_player_profile(player_id: str) -> dict | None:
    """
    Get player profile fields needed to render the BRz card.
    Falls back to players_enriched if not found in players table.
    """
    client = get_bigquery_client()

    # Try main players table first
    query = f"""
        SELECT
          player_id,
          display_name,
          country_code,
          photo_path,
          faceit_avatar_url,
          steam_avatar_url,
          faceit_level
        FROM `{PROJECT_ID}.{DATASET_ID}.players`
        WHERE player_id = @player_id OR faceit_player_id = @player_id
        LIMIT 1
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("player_id", "STRING", player_id),
        ],
        maximum_bytes_billed=20 * 1024 * 1024,
    )

    rows = list(client.query(query, job_config=job_config).result())

    if rows:
        row = rows[0]
        return {
            "player_id": row["player_id"],
            "display_name": row["display_name"],
            "country_code": row["country_code"],
            "photo_path": row["photo_path"],
            "faceit_avatar_url": row["faceit_avatar_url"],
            "steam_avatar_url": row["steam_avatar_url"],
            "faceit_level": row["faceit_level"],
        }

    # Fallback to players_enriched table
    query_enriched = f"""
        SELECT
          faceit_nickname_official AS player_id,
          faceit_nickname_official AS display_name,
          country AS country_code,
          CAST(NULL AS STRING) AS photo_path,
          avatar AS faceit_avatar_url,
          CAST(NULL AS STRING) AS steam_avatar_url,
          cs2_skill_level AS faceit_level
        FROM `{PROJECT_ID}.{DATASET_ID}.players_enriched`
        WHERE faceit_player_id = @player_id OR LOWER(faceit_nickname_official) = LOWER(@player_id)
        LIMIT 1
    """

    rows_enriched = list(client.query(query_enriched, job_config=job_config).result())

    if not rows_enriched:
        return None

    row = rows_enriched[0]
    return {
        "player_id": row["player_id"],
        "display_name": row["display_name"],
        "country_code": row["country_code"],
        "photo_path": row["photo_path"],
        "faceit_avatar_url": row["faceit_avatar_url"],
        "steam_avatar_url": row["steam_avatar_url"],
        "faceit_level": row["faceit_level"],
    }

def get_latest_player_card_by_player_id(player_id: str) -> dict | None:
    """
    Get the latest BRz card score for a player by player_id.
    """
    client = get_bigquery_client()

    query = f"""
        SELECT
          faceit_player_id AS player_id,
          faceit_nickname AS display_name,
          OVERALL AS overall_brz,
          AIM AS aim,
          IMP AS impact,
          UTL AS utility,
          CON AS consistency,
          INT AS intelligence,
          EXP AS experience,
          role,
          'Unknown' AS tier,
          season8_matches AS matches_analyzed,
          'v2' AS score_version,
          uploaded_at AS calculated_at
        FROM `{PROJECT_ID}.{DATASET_ID}.card_scores`
        WHERE faceit_player_id = @player_id
        ORDER BY uploaded_at DESC
        LIMIT 1
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("player_id", "STRING", player_id),
        ],
        maximum_bytes_billed=20 * 1024 * 1024,
    )

    rows = list(client.query(query, job_config=job_config).result())

    if not rows:
        return None

    row = rows[0]

    return {
        "player_id": row["player_id"],
        "display_name": row["display_name"],
        "overall_brz": row["overall_brz"],
        "aim": row["aim"],
        "impact": row["impact"],
        "utility": row["utility"],
        "consistency": row["consistency"],
        "intelligence": row["intelligence"],
        "experience": row["experience"],
        "role": row["role"],
        "tier": row["tier"],
        "matches_analyzed": row["matches_analyzed"],
        "score_version": row["score_version"],
        "calculated_at": row["calculated_at"],
    }


def update_player_faceit_level_from_leetify_matches(player_id: str) -> int | None:
    """
    Update players.faceit_level using the latest FACEIT rank found in
    player_match_stats collected from Leetify.

    This does not call the FACEIT API.
    It uses Leetify match data already stored in BigQuery.

    Logic:
    - source must be 'leetify'
    - match_source must be 'faceit'
    - rank must be between 1 and 10
    - latest match_date wins
    """
    client = get_bigquery_client()

    query = f"""
        UPDATE `{PROJECT_ID}.{DATASET_ID}.players` AS p
        SET
          faceit_level = latest_faceit.faceit_level,
          updated_at = CURRENT_TIMESTAMP()
        FROM (
          SELECT
            player_id,
            rank AS faceit_level
          FROM `{PROJECT_ID}.{DATASET_ID}.player_match_stats`
          WHERE player_id = @player_id
            AND source = 'leetify'
            AND match_source = 'faceit'
            AND rank BETWEEN 1 AND 10
          QUALIFY ROW_NUMBER() OVER (
            PARTITION BY player_id
            ORDER BY match_date DESC
          ) = 1
        ) AS latest_faceit
        WHERE p.player_id = latest_faceit.player_id
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("player_id", "STRING", player_id),
        ],
        maximum_bytes_billed=20 * 1024 * 1024,
    )

    client.query(query, job_config=job_config).result()

    validation_query = f"""
        SELECT
          faceit_level
        FROM `{PROJECT_ID}.{DATASET_ID}.players`
        WHERE player_id = @player_id
        LIMIT 1
    """

    validation_job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("player_id", "STRING", player_id),
        ],
        maximum_bytes_billed=20 * 1024 * 1024,
    )

    rows = list(client.query(validation_query, job_config=validation_job_config).result())

    if not rows:
        return None

    return rows[0]["faceit_level"]