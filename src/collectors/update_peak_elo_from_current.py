"""
update_peak_elo_from_current.py
================================
Compara cs2_faceit_elo com faceit_tracker_highest_elo e atualiza o peak ELO
automaticamente quando o ELO atual supera o pico registrado.

Regras:
    - Se cs2_faceit_elo > faceit_tracker_highest_elo  -> atualiza peak + source + timestamp
    - Se cs2_faceit_elo <= faceit_tracker_highest_elo -> mantem tudo como esta
    - Se faceit_tracker_highest_elo for vazio / 0 / NaN e cs2_faceit_elo for valido
      -> usa cs2_faceit_elo como valor inicial do peak

Seguranca:
    - Cria backup do CSV antes de salvar
    - Nao zera nem sobrescreve peaks confirmados maiores
    - Lida com NaN, vazio, 0 de forma segura
    - Nao altera scoring nem pesos

Arquivo lido/gravado: data/brz_faceit_players_enriched.csv
Backup:               data/brz_faceit_players_enriched_backup_before_peak_elo_auto_update_<timestamp>.csv
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = PROJECT_ROOT / "data" / "brz_faceit_players_enriched.csv"

SOURCE_LABEL = "AUTO_UPDATED_CURRENT_ELO"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_float_safe(value) -> float | None:
    """Convert value to float, returning None for invalid/empty/NaN values."""
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    try:
        s = str(value).replace(",", "").strip()
        if not s:
            return None
        result = float(s)
        return result if result > 0 else None
    except (ValueError, TypeError):
        return None


def _peak_is_valid(val) -> bool:
    """True when the existing peak is a positive, non-NaN number."""
    f = _to_float_safe(val)
    return f is not None and f > 0


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def update_peak_elo(df: pd.DataFrame, now_utc: str) -> pd.DataFrame:
    """
    Applies the peak-ELO auto-update rule row by row.

    Returns the modified DataFrame.
    """
    required = ["faceit_nickname_official", "cs2_faceit_elo", "faceit_tracker_highest_elo"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise RuntimeError(f"[ERROR] Colunas obrigatorias ausentes: {missing}")

    # Ensure optional columns exist
    for col in ["peak_elo_source", "peak_elo_updated_at"]:
        if col not in df.columns:
            df[col] = ""
            print(f"[INFO] Coluna '{col}' criada (nao existia).")

    updated_players: list[str] = []
    initialized_players: list[str] = []
    unchanged_players: list[str] = []
    skipped_players: list[str] = []

    for idx, row in df.iterrows():
        nickname = str(row.get("faceit_nickname_official") or row.get("faceit_nickname_input") or "").strip()
        label = f"[{idx + 1}/{len(df)}] {nickname or '(sem nickname)'}"

        current_elo = _to_float_safe(row.get("cs2_faceit_elo"))
        peak_elo = _to_float_safe(row.get("faceit_tracker_highest_elo"))

        # --- cs2_faceit_elo invalido -> skip ---
        if current_elo is None:
            print(f"  [SKIP] {label} | cs2_faceit_elo invalido/NaN -> nenhuma alteracao.")
            skipped_players.append(nickname)
            continue

        # --- Peak nao existe ou e 0 -> inicializar com current_elo ---
        if not _peak_is_valid(row.get("faceit_tracker_highest_elo")):
            df.at[idx, "faceit_tracker_highest_elo"] = int(current_elo)
            df.at[idx, "peak_elo_source"] = SOURCE_LABEL
            df.at[idx, "peak_elo_updated_at"] = now_utc
            print(
                f"  [INIT] {label} | peak vazio/0 -> inicializado com "
                f"cs2_faceit_elo={int(current_elo)}"
            )
            initialized_players.append(nickname)
            continue

        # --- Peak valido: comparar ---
        if current_elo > peak_elo:
            old_peak = int(peak_elo)
            df.at[idx, "faceit_tracker_highest_elo"] = int(current_elo)
            df.at[idx, "peak_elo_source"] = SOURCE_LABEL
            df.at[idx, "peak_elo_updated_at"] = now_utc
            print(
                f"  [UPDATE] {label} | NOVO PEAK: {int(current_elo)} "
                f"(era {old_peak}) <- cs2_faceit_elo superou o pico anterior"
            )
            updated_players.append(nickname)
        else:
            print(
                f"  [OK] {label} | peak mantido: {int(peak_elo)} "
                f"(cs2_faceit_elo={int(current_elo)} <= peak)"
            )
            unchanged_players.append(nickname)

    # ---------------------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------------------
    print()
    print("=" * 60)
    print("RESUMO DA EXECUCAO")
    print("=" * 60)
    print(f"  Players com peak ATUALIZADO  : {len(updated_players)}")
    if updated_players:
        for n in updated_players:
            print(f"    -> {n}")
    print(f"  Players com peak INICIALIZADO: {len(initialized_players)}")
    if initialized_players:
        for n in initialized_players:
            print(f"    -> {n}")
    print(f"  Players sem alteracao        : {len(unchanged_players)}")
    print(f"  Players ignorados (ELO N/A)  : {len(skipped_players)}")
    if skipped_players:
        for n in skipped_players:
            print(f"    -> {n}")
    print("=" * 60)

    return df


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    print("=" * 60)
    print("update_peak_elo_from_current.py")
    print("=" * 60)

    if not DATA_PATH.exists():
        print(f"[ERROR] Arquivo nao encontrado: {DATA_PATH}", file=sys.stderr)
        sys.exit(1)

    # Read (dtype=str evita conversoes implicitas)
    df = pd.read_csv(DATA_PATH, dtype=str)
    print(f"[OK] Arquivo lido: {DATA_PATH} ({len(df)} players)")

    now_utc = datetime.now(timezone.utc).isoformat()

    # Backup antes de qualquer alteracao
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = DATA_PATH.with_name(
        f"brz_faceit_players_enriched_backup_before_peak_elo_auto_update_{ts}.csv"
    )
    df.to_csv(backup_path, index=False, encoding="utf-8-sig")
    print(f"[OK] Backup salvo em: {backup_path}")
    print()

    # Apply logic
    print("Processando players...")
    print()
    df = update_peak_elo(df, now_utc)

    # Normalize types before saving
    df["faceit_tracker_highest_elo"] = (
        pd.to_numeric(df["faceit_tracker_highest_elo"], errors="coerce")
        .fillna(0)
        .astype(int)
    )
    df["peak_elo_source"] = df["peak_elo_source"].fillna("").astype(str)
    df["peak_elo_updated_at"] = df["peak_elo_updated_at"].fillna("").astype(str)

    # Save
    df.to_csv(DATA_PATH, index=False, encoding="utf-8-sig")
    print(f"\n[OK] Arquivo salvo: {DATA_PATH}")

    # Validation snapshot
    cols_to_show = [
        "faceit_nickname_official",
        "cs2_faceit_elo",
        "faceit_tracker_highest_elo",
        "peak_elo_source",
        "peak_elo_updated_at",
    ]
    available = [c for c in cols_to_show if c in df.columns]
    print()
    print("VALIDACAO -- Estado final:")
    print(df[available].to_string(index=False))


if __name__ == "__main__":
    main()
