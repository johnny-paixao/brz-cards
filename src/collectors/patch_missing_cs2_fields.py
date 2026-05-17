"""
patch_missing_cs2_fields.py
============================
Para players que estao com NaN nas colunas CS2 (cs2_faceit_elo, cs2_skill_level,
cs2_game_player_id, cs2_game_player_name, country, etc.), re-busca os dados
atuais na FACEIT API e preenche SOMENTE as colunas que estao vazias/NaN.

Colunas ja enriquecidas (faceit_tracker_highest_elo, peak_elo_source,
peak_elo_updated_at, lifetime_faceit_matches, etc.) NAO sao tocadas.

Arquivo lido/gravado: data/brz_faceit_players_enriched.csv
Backup:               data/brz_faceit_players_enriched_backup_before_patch_cs2_<timestamp>.csv
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = PROJECT_ROOT / "data" / "brz_faceit_players_enriched.csv"

FACEIT_API_KEY = os.getenv("FACEIT_API_KEY")
FACEIT_API_BASE = "https://open.faceit.com/data/v4"

# Colunas CS2 que devem ser preenchidas se estiverem vazias
CS2_COLUMNS = [
    "country",
    "steam_id_64",
    "steam_nickname",
    "cs2_skill_level",
    "cs2_faceit_elo",
    "cs2_game_player_id",
    "cs2_game_player_name",
    "avatar",
    "faceit_url",
    "activated_at",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_empty(val) -> bool:
    """True se o valor eh NaN, None, vazio ou string vazia."""
    if val is None:
        return True
    if isinstance(val, float) and pd.isna(val):
        return True
    return str(val).strip() in ("", "nan", "NaN", "None")


def _needs_patch(row: pd.Series) -> bool:
    """True se alguma coluna CS2 essencial estiver vazia."""
    return _is_empty(row.get("cs2_faceit_elo"))


def fetch_player_by_id(player_id: str) -> dict | None:
    """Busca dados do player pelo player_id (mais confiavel que nickname)."""
    url = f"{FACEIT_API_BASE}/players/{player_id}"
    r = requests.get(
        url,
        headers={"Authorization": f"Bearer {FACEIT_API_KEY}"},
        timeout=30,
    )
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        raise RuntimeError(f"FACEIT API error ({r.status_code}): {r.text[:300]}")
    return r.json()


def extract_cs2_fields(player: dict) -> dict:
    """Extrai os campos CS2 e base do payload da API."""
    cs2 = player.get("games", {}).get("cs2", {})
    return {
        "country": player.get("country"),
        "steam_id_64": player.get("steam_id_64"),
        "steam_nickname": player.get("steam_nickname"),
        "cs2_skill_level": cs2.get("skill_level"),
        "cs2_faceit_elo": cs2.get("faceit_elo"),
        "cs2_game_player_id": cs2.get("game_player_id"),
        "cs2_game_player_name": cs2.get("game_player_name"),
        "avatar": player.get("avatar"),
        "faceit_url": player.get("faceit_url"),
        "activated_at": player.get("activated_at"),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    print("=" * 60)
    print("patch_missing_cs2_fields.py")
    print("=" * 60)

    if not FACEIT_API_KEY:
        print("[ERROR] FACEIT_API_KEY nao encontrada no .env", file=sys.stderr)
        sys.exit(1)

    if not DATA_PATH.exists():
        print(f"[ERROR] Arquivo nao encontrado: {DATA_PATH}", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(DATA_PATH, dtype=object)
    print(f"[OK] Arquivo lido: {DATA_PATH} ({len(df)} players)")

    # Identifica quais players precisam de patch
    needs_patch = df[df.apply(_needs_patch, axis=1)]
    print(f"[INFO] Players com cs2_faceit_elo vazio/NaN: {len(needs_patch)}")

    if needs_patch.empty:
        print("[OK] Nenhum player precisa de patch. Encerrando.")
        return

    for idx in needs_patch.index:
        nickname = str(df.at[idx, "faceit_nickname_official"] or df.at[idx, "faceit_nickname_input"] or "").strip()
        player_id = str(df.at[idx, "faceit_player_id"] or "").strip()

        print()
        print(f"  [PATCH] {nickname} (player_id={player_id})")

        if not player_id or _is_empty(player_id):
            print(f"    [SKIP] player_id ausente, impossivel buscar na API.")
            continue

        try:
            player = fetch_player_by_id(player_id)
        except Exception as exc:
            print(f"    [ERROR] Falha na API: {exc}")
            continue

        if player is None:
            print(f"    [WARN] Player nao encontrado na API (404).")
            continue

        fields = extract_cs2_fields(player)

        # Verifica se a API retornou CS2
        if not fields.get("cs2_faceit_elo"):
            print(f"    [WARN] API retornou player sem dados CS2. Sem alteracao.")
            print(f"           games disponiveis: {list(player.get('games', {}).keys())}")
            continue

        # Preenche apenas colunas vazias — NUNCA sobrescreve valores existentes
        updated_fields = []
        for col in CS2_COLUMNS:
            current_val = df.at[idx, col] if col in df.columns else None
            new_val = fields.get(col)
            if _is_empty(current_val) and not _is_empty(new_val):
                df.at[idx, col] = str(new_val) if new_val is not None else ""
                updated_fields.append(f"{col}={new_val}")

        if updated_fields:
            print(f"    [OK] Campos atualizados:")
            for f in updated_fields:
                print(f"         {f}")
        else:
            print(f"    [INFO] Nenhum campo novo para preencher.")

    # Backup
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = DATA_PATH.with_name(
        f"brz_faceit_players_enriched_backup_before_patch_cs2_{ts}.csv"
    )
    # Salva o estado ANTES das alteracoes? Nao — backup eh do estado anterior.
    # Lemos sem alterar, entao o backup aqui reflete o estado pre-patch.
    # Na pratica, o df original foi lido e as alteracoes sao em memoria.
    # Vamos salvar o backup do original antes de escrever o novo.
    original_df = pd.read_csv(DATA_PATH, dtype=object)
    original_df.to_csv(backup_path, index=False, encoding="utf-8-sig")
    print(f"\n[OK] Backup do original salvo em: {backup_path}")

    # Salva
    df.to_csv(DATA_PATH, index=False, encoding="utf-8-sig")
    print(f"[OK] Arquivo atualizado: {DATA_PATH}")

    # Validacao dos players patcheados
    print()
    print("VALIDACAO -- Players patcheados:")
    cols_show = [
        "faceit_nickname_official",
        "cs2_faceit_elo",
        "cs2_skill_level",
        "faceit_tracker_highest_elo",
        "peak_elo_source",
    ]
    available = [c for c in cols_show if c in df.columns]
    patched_nicknames = needs_patch["faceit_nickname_official"].tolist()
    result = df[df["faceit_nickname_official"].isin(patched_nicknames)][available]
    print(result.to_string(index=False))


if __name__ == "__main__":
    main()
