from google.cloud import bigquery


PROJECT_ID = "brz-esports"
DATASET_ID = "brz_esports"


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
        FROM `{PROJECT_ID}.{DATASET_ID}.player_card_scores`
        WHERE LOWER(display_name) = LOWER(@display_name)
        ORDER BY calculated_at DESC
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
        "clutch": row.clutch,
        "experience": row.experience,
        "role": row.role,
        "tier": row.tier,
        "matches_analyzed": row.matches_analyzed,
        "score_version": row.score_version,
        "calculated_at": row.calculated_at,
    }