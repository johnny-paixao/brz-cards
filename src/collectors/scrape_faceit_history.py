"""
FACEIT History Scraper
======================
Faz scraping da página de Histórico do jogador para extrair o Rating
de forma muito mais rápida, num único carregamento de página!
"""

import csv
import json
import re
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ─── Configuração ──────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
CSV_FILE = DATA_DIR / "faceit_matches_JohnnyPanda_last_270.csv"
OUTPUT_CSV = DATA_DIR / "faceit_ratings_scraped.csv"

# Regex para Match ID (ex: 1-7f80f707-0b6a-4ef8-ac51-c731c6a7b8ba)
MATCH_ID_PATTERN = re.compile(r"(1-[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})")

def load_match_ids() -> list[str]:
    if not CSV_FILE.exists():
        raise FileNotFoundError(f"CSV não encontrado: {CSV_FILE}")
    matches = []
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            matches.append(row["Match ID"])
    return matches

def create_driver() -> webdriver.Chrome:
    chrome_options = Options()
    user_data_dir = BASE_DIR / "chrome_profile"
    user_data_dir.mkdir(exist_ok=True)
    chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
    chrome_options.add_argument("--window-size=1280,900")
    
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def main():
    target_match_ids = load_match_ids()
    target_set = set(target_match_ids)
    print(f"[INFO] Temos {len(target_set)} partidas alvo para encontrar o rating.")

    driver = create_driver()
    try:
        print("\n" + "=" * 70)
        print("  FACEIT HISTORY SCRAPER")
        print("=" * 70)
        
        # O URL de histórico do utilizador
        driver.get("https://www.faceit.com/pt/players/JohnnyPanda/cs2/history")
        
        print("\n  1. Verifica se a página de histórico carregou e tem os dados.")
        print("  2. Se precisar de fazer login, faça-o agora e volte a abrir o histórico.")
        input("  >>> Pressione ENTER no terminal quando estiver a ver a tabela de histórico... ")
        print()

        # Agora vamos fazer scroll e extrair
        results = {}
        last_height = driver.execute_script("return document.body.scrollHeight")
        
        # Vamos fazer scroll várias vezes para carregar o máximo possível
        # Como o CSV tem 270 partidas, precisamos de umas 10-15 iterações de scroll
        max_scrolls = 20
        for i in range(max_scrolls):
            print(f"[SCROLL] A descer a página ({i+1}/{max_scrolls}) para carregar mais partidas...")
            
            # Fazer scroll até ao fim
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)  # Esperar que o FACEIT carregue os novos dados
            
            # Extrair todas as tags <a> que contêm um link de match
            links = driver.find_elements(By.XPATH, "//a[contains(@href, '/room/1-')]")
            
            for link in links:
                href = link.get_attribute("href")
                if not href: continue
                
                match_match = MATCH_ID_PATTERN.search(href)
                if match_match:
                    match_id = match_match.group(1)
                    
                    # Apenas processar se for um dos IDs que queremos e ainda não tivermos
                    if match_id in target_set and match_id not in results:
                        text_content = link.text.strip()
                        
                        # O texto da linha contém várias coisas, o Rating costuma ter formato X.XX e K/D Y.YY
                        # Exemplo: "20 / 16 / 7" (kills), "1.25" (KD), "90.3" (ADR), "1.29" (Rating)
                        # Podemos identificar o Rating e o K/D
                        # O FACEIT tem colunas. Podemos tentar extrair usando JS puro das colunas
                        
                        # Uma maneira fácil é extrair todo o texto interno do link, separado por colunas
                        js_extract = """
                        var elem = arguments[0];
                        var texts = [];
                        var walker = document.createTreeWalker(elem, NodeFilter.SHOW_TEXT, null, false);
                        var node;
                        while(node = walker.nextNode()) {
                            var t = node.nodeValue.trim();
                            if(t.length > 0) texts.push(t);
                        }
                        return texts;
                        """
                        pieces = driver.execute_script(js_extract, link)
                        
                        # Agora, procuramos pelos padrões de Rating
                        # A ordem típica (conforme screenshot) é:
                        # [Data, W/L, 13:8, Elo, Delta, Rating, Kills/Deaths/Assists, KD, ADR, Map]
                        # Precisamos procurar o primeiro valor que é no formato float (Rating) antes do K/D/A
                        
                        rating = "N/A"
                        # Procurar a string que tem o K/D/A (ex: "20 / 16 / 7" ou "20/16/7")
                        kda_index = -1
                        for idx, p in enumerate(pieces):
                            if "/" in p and len(p.split("/")) == 3:
                                kda_index = idx
                                break
                        
                        if kda_index > 0:
                            # O rating normalmente está na posição antes do KDA
                            # Vamos procurar de kda_index para trás o primeiro número no formato X.XX
                            for p in reversed(pieces[:kda_index]):
                                if re.match(r"^\d\.\d{2}$", p):
                                    rating = p
                                    break
                                
                        if rating == "N/A":
                            # Fallback: tentar apanhar o K/D/A do nosso CSV para bater certo
                            # Se não conseguirmos encontrar pelo texto, deixamos "N/A"
                            pass
                        
                        results[match_id] = rating
            
            print(f"  -> Encontrados até agora: {len(results)}/{len(target_set)} ratings.")
            
            if len(results) >= len(target_set):
                print("[INFO] Todos os ratings foram encontrados!")
                break
                
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                print("[INFO] Não há mais espaço para scroll.")
                # Tentar encontrar um botão "Load more" por precaução
                try:
                    btns = driver.find_elements(By.TAG_NAME, "button")
                    clicked = False
                    for b in btns:
                        if "load more" in b.text.lower() or "mostrar mais" in b.text.lower():
                            b.click()
                            time.sleep(2)
                            clicked = True
                            break
                    if not clicked:
                        break
                except:
                    break
            last_height = new_height

        # Guardar resultados
        with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Match ID", "Faceit Rating"])
            for match_id in target_match_ids:
                r = results.get(match_id, "N/A")
                writer.writerow([match_id, r])

        print(f"\n[SUCESSO] Guardámos {len(results)} ratings no ficheiro: {OUTPUT_CSV}")

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
