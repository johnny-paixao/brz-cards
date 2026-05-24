"""
FACEIT Stat Rating Scraper v2
=============================
Extrai o "stat rating" (performance rating, ex: 1.25, 0.98) de cada partida
a partir da página de scoreboard do FACEIT.

Usa Selenium com Chrome e perfil separado.
Suporta checkpoint/resume para retomar de onde parou.

Uso:
    python src/collectors/scrape_faceit_rating_v2.py
"""

import csv
import json
import re
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException


# ─── Configuração ──────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
CSV_FILE = DATA_DIR / "faceit_matches_JohnnyPanda_last_270.csv"
OUTPUT_CSV = DATA_DIR / "faceit_ratings_scraped.csv"
CHECKPOINT_FILE = DATA_DIR / "cache" / "scrape_rating_checkpoint.json"

PLAYER_ID = "50b900e5-261c-42f1-87ac-51bf6000e0ac"  # JohnnyPanda

# Tempo de espera para a página carregar (segundos)
PAGE_LOAD_WAIT = 10
# Tempo de espera para elementos aparecerem (segundos)
ELEMENT_WAIT = 15
# Pausa entre partidas (segundos)
DELAY_BETWEEN_MATCHES = 3
# Máximo de retries por partida
MAX_RETRIES = 2

# Regex para detetar um rating válido (ex: 0.98, 1.25, 2.10)
RATING_PATTERN = re.compile(r"^\d\.\d{2}$")


# ─── Funções auxiliares ────────────────────────────────────────────────────────

def load_match_ids() -> list[str]:
    """Carrega os match IDs do CSV das 270 partidas."""
    if not CSV_FILE.exists():
        raise FileNotFoundError(f"CSV não encontrado: {CSV_FILE}")

    matches = []
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            matches.append(row["Match ID"])

    return matches


def load_checkpoint() -> dict[str, str]:
    """Carrega resultados já extraídos (checkpoint)."""
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_checkpoint(results: dict[str, str]) -> None:
    """Salva checkpoint parcial."""
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def save_output_csv(results: dict[str, str], match_ids: list[str]) -> None:
    """Salva o CSV final com todos os resultados na ordem original."""
    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Match ID", "Faceit Rating"])
        for match_id in match_ids:
            rating = results.get(match_id, "N/A")
            writer.writerow([match_id, rating])

    print(f"\n[SUCESSO] Ratings salvos em: {OUTPUT_CSV}")


def create_driver() -> webdriver.Chrome:
    """Cria e retorna o Chrome driver com perfil separado."""
    chrome_options = Options()

    # Usar um perfil separado para não interferir com o Chrome do utilizador
    user_data_dir = BASE_DIR / "chrome_profile"
    user_data_dir.mkdir(exist_ok=True)
    chrome_options.add_argument(f"--user-data-dir={user_data_dir}")

    # Configurações para parecer mais humano
    chrome_options.add_argument("--window-size=1280,900")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    print("[INFO] Iniciando Chrome...")
    driver = webdriver.Chrome(options=chrome_options)

    # Remover a flag de automação do navigator
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            """
        },
    )

    return driver


def extract_rating_from_page(driver, match_id: str) -> str:
    """
    Tenta extrair o rating do jogador da página de scoreboard.
    Usa múltiplas estratégias de seleção para ser resiliente a mudanças de UI.
    """
    url = f"https://www.faceit.com/en/cs2/room/{match_id}/scoreboard"
    driver.get(url)

    # Espera inicial para a página carregar completamente (SPA React)
    time.sleep(PAGE_LOAD_WAIT)

    # ─── Estratégia 1: Procurar pela row do jogador via link com player_id ─────
    try:
        xpath_row = f"//tr[descendant::a[contains(@href, '{PLAYER_ID}')]]"
        WebDriverWait(driver, ELEMENT_WAIT).until(
            EC.presence_of_element_located((By.XPATH, xpath_row))
        )
        player_row = driver.find_element(By.XPATH, xpath_row)

        # Procurar spans com formato de rating (X.XX)
        spans = player_row.find_elements(By.TAG_NAME, "span")
        for span in spans:
            text = span.text.strip()
            if RATING_PATTERN.match(text):
                return text

        # Se não encontrou em spans, procurar em leaf elements
        all_text_elements = player_row.find_elements(By.XPATH, ".//*[not(*)]")
        for elem in all_text_elements:
            text = elem.text.strip()
            if RATING_PATTERN.match(text):
                return text

        # Último recurso: procurar nas TDs (últimas colunas)
        cells = player_row.find_elements(By.TAG_NAME, "td")
        if cells:
            for cell in reversed(cells[-3:]):
                text = cell.text.strip()
                if RATING_PATTERN.match(text):
                    return text

    except TimeoutException:
        pass
    except Exception as e:
        print(f"    [AVISO] Estratégia 1 falhou: {type(e).__name__}: {e}")

    # ─── Estratégia 2: Procurar pelo nickname "JohnnyPanda" no texto ───────────
    try:
        xpath_nick = "//tr[descendant::*[contains(text(), 'JohnnyPanda')]]"
        rows = driver.find_elements(By.XPATH, xpath_nick)
        for row in rows:
            spans = row.find_elements(By.TAG_NAME, "span")
            for span in spans:
                text = span.text.strip()
                if RATING_PATTERN.match(text):
                    return text
    except Exception as e:
        print(f"    [AVISO] Estratégia 2 falhou: {type(e).__name__}: {e}")

    # ─── Estratégia 3: Procurar via JavaScript direto no DOM ───────────────────
    try:
        js_script = f"""
        const rows = document.querySelectorAll('tr');
        for (const row of rows) {{
            const links = row.querySelectorAll('a[href*="{PLAYER_ID}"]');
            if (links.length > 0) {{
                // Procura todos os elementos de texto leaf
                const allElems = row.querySelectorAll('*');
                for (const elem of allElems) {{
                    if (elem.children.length === 0) {{
                        const text = elem.textContent.trim();
                        if (/^\\d\\.\\d{{2}}$/.test(text)) {{
                            return text;
                        }}
                    }}
                }}
            }}
        }}
        // Fallback: procurar pelo nick
        for (const row of rows) {{
            if (row.textContent.includes('JohnnyPanda')) {{
                const allElems = row.querySelectorAll('*');
                for (const elem of allElems) {{
                    if (elem.children.length === 0) {{
                        const text = elem.textContent.trim();
                        if (/^\\d\\.\\d{{2}}$/.test(text)) {{
                            return text;
                        }}
                    }}
                }}
            }}
        }}
        return null;
        """
        result = driver.execute_script(js_script)
        if result:
            return result
    except Exception as e:
        print(f"    [AVISO] Estratégia 3 (JS) falhou: {type(e).__name__}: {e}")

    return "N/A"


# ─── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    match_ids = load_match_ids()
    print(f"[INFO] Carregadas {len(match_ids)} partidas do CSV")

    # Carregar checkpoint (para retomar se parou no meio)
    results = load_checkpoint()
    already_done = len(results)
    if already_done > 0:
        print(f"[INFO] Checkpoint encontrado: {already_done} partidas já extraídas")

    # Filtrar partidas que ainda faltam
    remaining = [m for m in match_ids if m not in results]
    if not remaining:
        print("[INFO] Todas as partidas já foram extraídas!")
        save_output_csv(results, match_ids)
        return

    print(f"[INFO] Faltam {len(remaining)} partidas para extrair")

    driver = create_driver()

    try:
        print("\n" + "=" * 70)
        print("  FACEIT STAT RATING SCRAPER v2")
        print("=" * 70)
        print("\n  O navegador vai abrir. Faça o login normalmente na sua conta FACEIT.")
        print("  Depois de fazer login, volte aqui e pressione ENTER.\n")

        driver.get("https://www.faceit.com/en/cs2")

        input("  >>> Pressione ENTER depois de fazer login na FACEIT... ")
        print()

        success_count = 0
        fail_count = 0

        for i, match_id in enumerate(remaining):
            idx = already_done + i + 1
            total = len(match_ids)
            print(f"[{idx}/{total}] Extraindo: {match_id}...")

            rating = "N/A"
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    rating = extract_rating_from_page(driver, match_id)
                    if rating != "N/A":
                        break
                    if attempt < MAX_RETRIES:
                        print(f"    [RETRY] Tentativa {attempt} falhou, tentando novamente...")
                        time.sleep(3)
                except WebDriverException as e:
                    print(f"    [ERROR] WebDriver error: {e}")
                    if attempt < MAX_RETRIES:
                        time.sleep(5)

            if rating != "N/A":
                success_count += 1
            else:
                fail_count += 1

            print(f"    -> Rating: {rating}")
            results[match_id] = rating

            # Salvar checkpoint a cada 10 partidas
            if (i + 1) % 10 == 0:
                save_checkpoint(results)
                pct = (idx / total) * 100
                print(f"\n    [CHECKPOINT] Progresso: {idx}/{total} ({pct:.0f}%) | "
                      f"OK: {success_count} | Falhas: {fail_count}\n")

            time.sleep(DELAY_BETWEEN_MATCHES)

        # Salvar checkpoint final
        save_checkpoint(results)

        print("\n" + "=" * 70)
        print(f"  EXTRAÇÃO CONCLUÍDA!")
        print(f"  Total: {len(match_ids)} | OK: {success_count + already_done} | "
              f"Falhas: {fail_count}")
        print("=" * 70)

    finally:
        driver.quit()

    # Gerar CSV final
    save_output_csv(results, match_ids)

    # Estatísticas finais
    total_ok = sum(1 for v in results.values() if v != "N/A")
    total_fail = sum(1 for v in results.values() if v == "N/A")
    print(f"\n[STATS] Ratings extraídos: {total_ok}/{len(results)}")
    if total_fail > 0:
        print(f"[STATS] Partidas sem rating: {total_fail}")
        failed_ids = [k for k, v in results.items() if v == "N/A"]
        print(f"[STATS] IDs falhados: {failed_ids[:5]}{'...' if total_fail > 5 else ''}")


if __name__ == "__main__":
    main()
