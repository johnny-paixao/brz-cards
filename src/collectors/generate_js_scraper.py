import csv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"

def main():
    csv_file = DATA_DIR / "faceit_matches_JohnnyPanda_last_270.csv"
    if not csv_file.exists():
        print(f"File not found: {csv_file}")
        return

    match_ids = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            match_ids.append(row["Match ID"])

    js_code = f"""
// --- FACEIT RATING SCRAPER ---
// Copie tudo e cole no Console do Chrome na aba da FACEIT.
(async function() {{
    const matchIds = {match_ids};
    const playerId = "50b900e5-261c-42f1-87ac-51bf6000e0ac"; // JohnnyPanda
    const results = [];
    
    console.log("[SCRAPER] Iniciando extração de " + matchIds.length + " partidas usando aba Popup...");
    
    // Tenta abrir uma aba/popup
    let popup = window.open("about:blank", "FaceitScraper", "width=1000,height=800");
    if (!popup || popup.closed || typeof popup.closed == 'undefined') {{
        alert("⚠️ O Chrome bloqueou o Popup! Por favor, olhe na barra de endereços lá em cima (do lado direito), clique no ícone vermelho, escolha 'Sempre permitir pop-ups' e depois rode o script de novo no Console!");
        return;
    }}
    
    const wait = (ms) => new Promise(res => setTimeout(res, ms));
    
    for (let i = 0; i < matchIds.length; i++) {{
        const matchId = matchIds[i];
        console.log(`[SCRAPER] Extraindo [${{i+1}}/${{matchIds.length}}]: ${{matchId}}...`);
        
        popup.location.href = `https://www.faceit.com/en/cs2/room/${{matchId}}/scoreboard`;
        
        // Espera tempo suficiente para a página carregar
        await wait(6000); 
        
        let rating = "N/A";
        try {{
            const popupDoc = popup.document;
            
            // Procura o link do jogador
            const playerLinks = popupDoc.querySelectorAll(`a[href*='${{playerId}}']`);
            if (playerLinks && playerLinks.length > 0) {{
                const tr = playerLinks[0].closest("tr");
                if (tr) {{
                    const tds = tr.querySelectorAll("td");
                    if (tds.length >= 7) {{
                        const ratingEl = tds[tds.length - 1]; // Geralmente é a última ou penúltima coluna
                        rating = ratingEl.innerText.trim();
                        
                        const spans = tr.querySelectorAll("span");
                        for (let s of spans) {{
                            const text = s.innerText.trim();
                            if (/^\\d\\.\\d{{2}}$/.test(text)) {{
                                rating = text;
                                break;
                            }}
                        }}
                    }}
                }}
            }}
        }} catch(e) {{
            console.error("Erro na partida " + matchId, e);
        }}
        
        console.log(`[SCRAPER] Rating encontrado: ${{rating}}`);
        results.push({{ matchId, rating }});
    }}
    
    popup.close();
    console.log("[SCRAPER] Extração finalizada! Gerando CSV...");
    
    // Gerar CSV e baixar
    let csvContent = "data:text/csv;charset=utf-8,Match ID,Faceit Rating\\n";
    results.forEach(row => {{
        csvContent += `${{row.matchId}},${{row.rating}}\\n`;
    }});
    
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "faceit_ratings_extra.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    console.log("[SCRAPER] Download concluído!");
}})();
"""

    out_file = BASE_DIR / "scraper_code.txt"
    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(js_code)
    
    print(f"\\n[SUCESSO] Código Javascript gerado em: {out_file}\\n")
    print("Por favor, abra esse arquivo, copie o texto dele, vá até o seu Chrome na página da FACEIT, aperte F12, cole na aba Console e dê ENTER!")

if __name__ == "__main__":
    main()
