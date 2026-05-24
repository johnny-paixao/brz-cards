import csv
import time
from pathlib import Path
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
CSV_FILE = DATA_DIR / "faceit_matches_JohnnyPanda_last_270.csv"
PLAYER_ID = "50b900e5-261c-42f1-87ac-51bf6000e0ac"

def main():
    if not CSV_FILE.exists():
        print(f"[ERROR] CSV não encontrado: {CSV_FILE}")
        return

    matches = []
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            matches.append(row["Match ID"])
    
    print(f"[INFO] Loaded {len(matches)} matches from {CSV_FILE}")

    # Configuração do Undetected Chromedriver (Bypass do Cloudflare)
    options = uc.ChromeOptions()
    # Criar um profile local para não afetar o Chrome do usuário nem bugar
    user_data_dir = BASE_DIR / "chrome_profile_uc"
    user_data_dir.mkdir(exist_ok=True)
    options.user_data_dir = str(user_data_dir)
    
    # Inicia o driver
    print("[INFO] Iniciando navegador antibloqueio...")
    driver = uc.Chrome(options=options, use_subprocess=True)
    
    try:
        print("\n" + "=" * 70)
        print("  FACEIT RATING SCRAPER - BYPASS CLOUDFLARE")
        print("=" * 70)
        print("\n  O navegador vai abrir. Faça o login normalmente na sua conta.")
        
        driver.get("https://www.faceit.com/en/cs2")
        
        input("  >>> Pressione ENTER AQUI NO TERMINAL depois de fazer o login na FACEIT... ")
        
        results = []
        for i, match_id in enumerate(matches):
            print(f"\\n[SCRAPER] Extraindo [{i+1}/{len(matches)}]: {match_id}...")
            url = f"https://www.faceit.com/en/cs2/room/{match_id}/scoreboard"
            
            driver.get(url)
            
            rating = "N/A"
            try:
                # Esperar até 15 segundos para a tabela aparecer
                # XPath localiza o <tr> que tem um <a> com o playerId
                xpath_row = f"//tr[descendant::a[contains(@href, '{PLAYER_ID}')]]"
                
                # Aguarda até que a linha do jogador exista
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.XPATH, xpath_row))
                )
                
                # Pega a linha do jogador
                player_row = driver.find_element(By.XPATH, xpath_row)
                
                # Pega todas as colunas
                cells = player_row.find_elements(By.TAG_NAME, "td")
                
                if len(cells) >= 7:
                    # O rating normalmente é a penúltima ou última coluna com dados
                    last_cell = cells[-1]
                    rating = last_cell.text.strip()
                    
                    # Vamos tentar garantir usando RegEx
                    import re
                    spans = player_row.find_elements(By.TAG_NAME, "span")
                    for span in spans:
                        text = span.text.strip()
                        if re.match(r"^\d\.\d{2}$", text):
                            rating = text
                            break
                            
            except Exception as e:
                print(f"[AVISO] Não foi possível encontrar a nota nesta partida. Erro: {type(e).__name__}")
                
            print(f"[RESULTADO] Match {match_id} -> Rating: {rating}")
            results.append({"match_id": match_id, "rating": rating})
            
            # Pausa de 3 segundos pra não sobrecarregar
            time.sleep(3)
            
        print("\\n[SCRAPER] Extração finalizada! Salvando CSV...")
        
        out_csv = DATA_DIR / "faceit_ratings_extra.csv"
        with open(out_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Match ID", "Faceit Rating"])
            for r in results:
                writer.writerow([r["match_id"], r["rating"]])
                
        print(f"[SUCESSO] Ratings salvos em: {out_csv}")
        
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
