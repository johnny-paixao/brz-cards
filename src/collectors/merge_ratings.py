import csv
import sys
from pathlib import Path

# Configuração dos caminhos
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"

ORIGINAL_CSV = DATA_DIR / "faceit_matches_JohnnyPanda_last_270.csv"
DOWNLOADED_CSV = Path(r"C:\Users\johnn\Downloads\faceit_history_ratings (1).csv")
OUTPUT_CSV = DATA_DIR / "faceit_matches_JohnnyPanda_last_270_enriched.csv"

def main():
    if not ORIGINAL_CSV.exists():
        print(f"Erro: Arquivo original não encontrado em {ORIGINAL_CSV}")
        sys.exit(1)
        
    if not DOWNLOADED_CSV.exists():
        print(f"Erro: Arquivo baixado não encontrado em {DOWNLOADED_CSV}")
        sys.exit(1)

    # Passo 1: Ler os ratings sacados
    ratings = {}
    with open(DOWNLOADED_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            match_id = row.get("Match ID")
            rating = row.get("Faceit Rating") or row.get("Rating")
            if match_id and rating:
                ratings[match_id] = rating

    print(f"Lidos {len(ratings)} ratings do ficheiro das transferências.")

    # Passo 2: Juntar com o ficheiro original
    enriched_rows = []
    headers = []
    
    with open(ORIGINAL_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        headers = list(reader.fieldnames)
        
        # Inserir a coluna Rating a seguir ao K/R se possível
        if "Rating" not in headers:
            if "K/R" in headers:
                kr_index = headers.index("K/R")
                headers.insert(kr_index + 1, "Rating")
            else:
                headers.append("Rating")

        for row in reader:
            match_id = row.get("Match ID")
            # Encontrar o rating correspondente (o ID sacado está cortado num caractere)
            matched_rating = "N/A"
            for scraped_id, r in ratings.items():
                if match_id.startswith(scraped_id):
                    matched_rating = r
                    break
            
            row["Rating"] = matched_rating
            enriched_rows.append(row)

    # Passo 3: Guardar o novo CSV
    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(enriched_rows)

    print(f"\n[SUCESSO] Ficheiro gerado: {OUTPUT_CSV}")
    print(f"Total de partidas processadas: {len(enriched_rows)}")
    
    # Contar quantos ficaram com N/A
    missing = sum(1 for r in enriched_rows if r["Rating"] == "N/A")
    if missing > 0:
        print(f"[AVISO] {missing} partidas ficaram sem rating (N/A).")
    else:
        print("[SUCESSO] Todas as partidas receberam rating!")

if __name__ == "__main__":
    main()
