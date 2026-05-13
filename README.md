# 🃏 BRz Cards — FACEIT CS2 Game Cards

![Status](https://img.shields.io/badge/status-em%20desenvolvimento-yellow)
![Python](https://img.shields.io/badge/python-3.x-blue)
![FACEIT API](https://img.shields.io/badge/data-FACEIT%20API-orange)
![CS2](https://img.shields.io/badge/game-Counter--Strike%202-black)
![BRz](https://img.shields.io/badge/community-BRz%20eSports-red)

---

## 🎮 Sobre o projeto

**BRz Cards** é um projeto da comunidade **BRz eSports** que transforma dados competitivos de players de **Counter-Strike 2** na **FACEIT** em cartas estilo **game card**.

O objetivo é gerar cartas visuais para os players da comunidade, com atributos calculados a partir de dados reais de performance.

O projeto combina:

- 📊 Coleta de dados via **FACEIT API**
- 🧮 Cálculo de atributos personalizados
- 🃏 Geração visual automática das cartas
- 🏆 Ranking interno da comunidade BRz
- 🎯 Metodologia própria baseada na **FACEIT Season 8**

---

## 🧠 Objetivo

O objetivo do BRz Cards não é apenas gerar imagens bonitas.

A proposta é criar uma forma visual, divertida e competitiva de representar a performance dos players da comunidade BRz usando dados reais da FACEIT.

Cada carta representa uma leitura estatística do momento atual do player dentro da comunidade.

---

## 🕹️ Fonte dos dados

A principal fonte de dados do projeto é a **FACEIT API**.

Entre os dados utilizados estão:

- 🎯 `K/D Ratio`
- 🔫 `K/R Ratio`
- 💥 `ADR`
- 🧠 `Entry Success Rate`
- ⚔️ `Entry Rate`
- 💣 `Utility Success Rate`
- 🔥 `Utility Damage per Round`
- 👁️ `Enemies Flashed per Round`
- 💡 `Flash Success Rate`
- 🏆 `Win Rate`
- 🧊 `1v1Count`
- 🧊 `1v1Wins`
- 🧊 `1v2Count`
- 🧊 `1v2Wins`
- 📈 `FACEIT Level`
- 🎮 Partidas jogadas na Season 8
- 🧬 Partidas lifetime na FACEIT
- 🧬 Maior level FACEIT atingido em lifetime

---

## 📅 Corte oficial: FACEIT Season 8

A metodologia atual do BRz Cards utiliza como base principal a **Season 8 da FACEIT**, iniciada em:

```text
22/04/2026
```

Essa decisão foi tomada para evitar distorções causadas por estatísticas lifetime.

### ❌ Por que não usar lifetime stats para tudo?

Porque lifetime mistura toda a história do player:

- Fases antigas
- Evolução individual
- Partidas de quando o player ainda era iniciante
- Mudanças de nível
- Estilos de jogo diferentes ao longo do tempo
- Momentos bons e ruins acumulados no mesmo número

Por isso, os atributos principais da carta são baseados apenas nas partidas jogadas desde o início da Season 8.

A única exceção é o atributo **EXP**, que usa dados lifetime porque representa experiência acumulada.

---

## ✅ Regra mínima de elegibilidade

Para receber uma carta ativa, o player precisa ter:

```text
Mínimo de 20 partidas na Season 8
```

Players com menos de 20 partidas ficam como:

```text
INACTIVE
```

Nesse caso:

```text
AIM = 0
IMP = 0
UTL = 0
CON = 0
INT = 0
EXP = 0
OVERALL = 0
```

Além disso, players inativos:

- ❌ Não entram no ranking principal
- ❌ Não participam da normalização dos atributos
- ❌ Não são usados como referência máxima da pool
- ❌ Não recebem cálculo competitivo de carta

Essa regra existe para evitar que players com poucas partidas tenham números artificialmente altos.

Exemplo:

Um player com apenas 3 partidas pode ter um HS%, clutch rate ou ADR muito alto por acaso. Isso não representa uma amostra confiável.

Por isso, a carta competitiva só é calculada a partir de 20 partidas na Season 8.

---

## 🧮 Metodologia de normalização

O BRz Cards usa uma lógica de normalização baseada na própria comunidade.

Em vez de usar uma régua externa ou valores arbitrários, o sistema compara os players ativos entre si.

A regra geral é:

```text
score_da_variavel = valor_do_player / maior_valor_da_pool * 100
```

Ou seja:

> 🏆 O melhor player da comunidade em cada variável recebe 100.  
> 📉 Os demais recebem nota proporcional a esse melhor valor.

Exemplo:

```text
Maior HS% da pool = 70%
HS% do player = 35%

HS_score = 35 / 70 * 100
HS_score = 50
```

Com isso, a carta passa a responder:

```text
Quem é o melhor da comunidade BRz nesse fundamento?
```

---

## 📦 Normalização de volume

Para variáveis de volume, como quantidade de partidas, usamos uma curva diferente:

```text
volume_score = (valor_do_player / maior_valor_da_pool) ^ 0.65 * 100
```

Isso evita que o volume seja excessivamente punitivo.

Exemplo:

```text
Player com mais partidas = 180
Player analisado = 70

volume_score = (70 / 180) ^ 0.65 * 100
volume_score ≈ 54
```

Essa lógica valoriza quem joga mais, mas sem destruir completamente quem tem um volume menor, porém ainda relevante.

---

## 🃏 Atributos da carta

Cada carta possui 6 atributos principais:

| Stat | Nome | Significado |
|---|---|---|
| 🎯 AIM | Aim | Mira e eficiência individual |
| 💥 IMP | Impact | Impacto ofensivo |
| 💣 UTL | Utility | Uso de utilitários |
| 📊 CON | Consistency | Consistência na Season 8 |
| 🧠 INT | Intelligence | Clutch, decisão e leitura |
| 🧬 EXP | Experience | Experiência FACEIT |

---

## 🎯 AIM — Mira e eficiência individual

O atributo **AIM** mede a eficiência mecânica do player.

Ele responde perguntas como:

- O player mata bem?
- O player causa dano?
- O player tem boa eficiência individual?
- O player mantém boa relação entre kill, morte e dano?

### Variáveis usadas

```text
K/D Ratio
K/R Ratio
ADR
Headshots %
```

### Fórmula

```text
AIM =
35% K/D Ratio
25% K/R Ratio
25% ADR
15% Headshots %
```

### Motivação

**K/D Ratio** mede eficiência entre kills e mortes.

**K/R Ratio** mede frequência de kills por round.

**ADR** mede dano médio por round.

**Headshots %** mede precisão, mas não domina a nota.

HS% tem peso menor porque um player pode ter muito headshot, mas pouco impacto real no jogo.

---

## 💥 IMP — Impacto ofensivo

O atributo **IMP** mede o quanto o player influencia diretamente o round.

Ele responde perguntas como:

- O player cria vantagem?
- O player causa dano relevante?
- O player participa bem de entradas?
- O player gera impacto ofensivo?

### Variáveis usadas

```text
ADR
K/R Ratio
Entry Success Rate
Entry Rate
Clutch Impact
```

### Fórmula

```text
IMP =
30% ADR
25% K/R Ratio
20% Entry Success Rate
15% Entry Rate
10% Clutch Impact
```

### Motivação

**ADR** mede dano.

**K/R Ratio** mede kill por round.

**Entry Success Rate** mede sucesso em situações de abertura.

**Entry Rate** mede envolvimento em tentativas de entrada.

**Clutch Impact** entra com peso menor porque clutch também muda rounds, mas seu peso principal fica em INT.

---

## 💣 UTL — Utilitários

O atributo **UTL** mede a contribuição do player com utilitários.

Ele responde perguntas como:

- O player usa bem granadas?
- O player consegue flashar inimigos?
- O player gera dano com utilitários?
- O player ajuda o time taticamente?

### Variáveis usadas

```text
Utility Success Rate
Utility Damage per Round
Enemies Flashed per Round
Flash Success Rate
Utility Usage per Round
Flashes per Round
```

### Fórmula

```text
UTL =
25% Utility Success Rate
20% Utility Damage per Round
20% Enemies Flashed per Round
15% Flash Success Rate
10% Utility Usage per Round
10% Flashes per Round
```

### Motivação

**Utility Success Rate** mede eficiência geral dos utilitários.

**Utility Damage per Round** mede dano causado por granadas.

**Enemies Flashed per Round** mede impacto das flashes.

**Flash Success Rate** mede qualidade das flashes.

**Utility Usage per Round** mede frequência de uso.

**Flashes per Round** mede participação com flashbangs.

UTL é importante, mas tem peso controlado no OVERALL porque a API não captura todo o contexto tático de uma rodada.

---

## 📊 CON — Consistência na Season 8

O atributo **CON** mede a consistência do player na Season 8.

Ele responde perguntas como:

- O player jogou bastante?
- O player sustentou performance?
- O player converteu números em resultado?
- O player tem volume confiável?

### Variáveis usadas

```text
Quantidade de partidas na Season 8
K/D Ratio
K/R Ratio
Win Rate
```

### Fórmula

```text
CON =
65% volume de partidas na Season 8
35% performance consistency
```

A parte de performance consistency é:

```text
Performance Consistency =
40% K/D Ratio
30% K/R Ratio
30% Win Rate
```

### Volume de partidas

```text
matches_score = (partidas_do_player / maior_numero_de_partidas_da_pool) ^ 0.65 * 100
```

### Motivação

A Season 8 é o corte oficial da carta.

Por isso, quem joga mais partidas dentro desse período precisa ser valorizado.

Mas CON não é só volume.

Também entram KD, KR e Win Rate para medir se o player sustentou performance e converteu jogo.

---

## 🧠 INT — Inteligência, clutch e decisão

O atributo **INT** mede decisão sob pressão, clutch e leitura de jogo.

Ele responde perguntas como:

- O player decide bem em momentos críticos?
- O player ganha clutch?
- O player entra com qualidade?
- O player usa utilitário de forma inteligente?

### Variáveis usadas

```text
Clutch Score
Entry Success Rate
Utility Success Rate
```

### Fórmula

```text
INT =
70% Clutch Score
15% Entry Success Rate
15% Utility Success Rate
```

### Clutch Score

A FACEIT fornece dados como:

```text
1v1Count
1v1Wins
1v2Count
1v2Wins
```

Com isso, calculamos:

```text
1v1 Win Rate = 1v1Wins / 1v1Count
1v2 Win Rate = 1v2Wins / 1v2Count
Clutch Volume = 1v1Count + 1v2Count
```

A fórmula do Clutch Score é:

```text
Clutch Score =
50% 1v1 Win Rate
30% 1v2 Win Rate
20% Clutch Volume
```

### Motivação

Clutch tem peso alto em INT porque representa:

- 🧊 Calma
- 🧠 Leitura
- ⏱️ Noção de tempo
- 🎯 Escolha de duelo
- 🧍 Posicionamento
- 🏆 Decisão sob pressão

INT não é sobre matar muito. Para isso já existem AIM e IMP.

INT representa a capacidade de decidir bem em momentos importantes.

---

## 🧬 EXP — Experiência FACEIT

O atributo **EXP** mede experiência acumulada, liderança e bagagem competitiva.

Ele responde perguntas como:

- O player tem histórico na FACEIT?
- O player já chegou em nível alto?
- O player tem rodagem competitiva?
- O player tem bagagem suficiente para ser considerado experiente?

### Variáveis usadas

```text
Maior level FACEIT atingido em lifetime
Quantidade total de jogos FACEIT em lifetime
```

### Fórmula

```text
EXP =
40% maior level FACEIT lifetime
60% quantidade de jogos FACEIT lifetime
```

### Motivação

EXP é o único atributo que usa dados lifetime, porque experiência é naturalmente histórica.

**Maior level FACEIT lifetime** mostra o teto competitivo que o player já alcançou.

**Quantidade total de jogos FACEIT lifetime** mostra rodagem, bagagem e experiência acumulada.

EXP não usa Win Rate porque Win Rate já entra em CON.

EXP não usa performance atual porque isso já aparece em AIM, IMP, UTL, CON e INT.

Mesmo assim, EXP só é calculado se o player tiver pelo menos 20 partidas na Season 8.

---

## 🏆 OVERALL

O **OVERALL** é a nota geral da carta.

Ele representa a força geral do player dentro da metodologia BRz Cards.

### Fórmula base

```text
BASE_OVERALL =
25% AIM
25% IMP
10% UTL
18% CON
12% INT
10% EXP
```

### Multiplicador de FACEIT Level

Depois da fórmula base, aplicamos um multiplicador baseado no FACEIT Level atual.

```text
OVERALL = BASE_OVERALL * multiplicador_de_level
```

Tabela de multiplicador:

| FACEIT Level | Multiplicador |
|---|---:|
| Level 1 | 0.78 |
| Level 2 | 0.81 |
| Level 3 | 0.84 |
| Level 4 | 0.87 |
| Level 5 | 0.90 |
| Level 6 | 0.94 |
| Level 7 | 0.98 |
| Level 8 | 1.02 |
| Level 9 | 1.06 |
| Level 10 | 1.10 |

### Por que o level entra no OVERALL?

Porque o contexto competitivo importa.

Um player Level 10 joga contra adversários mais fortes do que um player Level 5.

Então, se dois players têm números parecidos, mas um performa em lobbies mais difíceis, isso precisa ser refletido na nota geral da carta.

Importante:

```text
O multiplicador de level não altera AIM, IMP, UTL, CON, INT ou EXP.
Ele afeta apenas o OVERALL final.
```

---

## 🧩 Roles

As roles da carta são definidas manualmente.

Exemplos:

```text
AWPER
ENTRY
SUPPORT
IGL
LURKER
CLUTCHER
RIFLER
```

### Por que a role é manual?

Porque a FACEIT API não sabe o contexto real da comunidade.

Ela não sabe se um player:

- Joga de entry por função real
- Pega AWP sempre ou só ocasionalmente
- Chama round
- Lurka por estilo
- Joga suporte
- Segura bomb
- Faz trade
- Joga para o time

Por isso, a role é tratada como identidade da carta, não como cálculo estatístico.

```text
Role = identidade visual / estilo do player
Stats = cálculo de performance
OVERALL = força geral da carta
```

A role não entra no cálculo do OVERALL.

---

## 📁 Estrutura principal do projeto

```text
brz-cards/
│
├── assets/
│   └── generated/
│       └── cartas geradas
│
├── data/
│   ├── brz_faceit_players_enriched.csv
│   ├── brz_faceit_season8_match_ids.csv
│   ├── brz_faceit_season8_stats.csv
│   └── brz_card_scores_v2.csv
│
├── src/
│   ├── collectors/
│   │   ├── export_faceit_season8_match_ids.py
│   │   └── export_faceit_season8_stats.py
│   │
│   └── scoring/
│       └── calculate_brz_card_scores_v2.py
│
└── README.md
```

---

## 🔐 Variáveis de ambiente

Para coletar dados da FACEIT API, é necessário configurar a chave da API:

```bash
FACEIT_API_KEY=sua_chave_aqui
```

No Windows PowerShell:

```powershell
$env:FACEIT_API_KEY="sua_chave_aqui"
```

---

## ⚙️ Como executar o projeto

### 1. Criar ambiente virtual

```bash
python -m venv venv
```

### 2. Ativar ambiente virtual

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

Windows CMD:

```cmd
venv\Scripts\activate
```

### 3. Instalar dependências

```bash
pip install -r requirements.txt
```

---

## 📥 Coleta de partidas da Season 8

O primeiro passo é coletar os IDs das partidas da Season 8.

Script:

```text
src/collectors/export_faceit_season8_match_ids.py
```

Execução:

```bash
python src/collectors/export_faceit_season8_match_ids.py
```

Output:

```text
data/brz_faceit_season8_match_ids.csv
```

Esse arquivo contém as partidas encontradas para os players da comunidade desde 22/04/2026.

---

## 📊 Coleta de stats da Season 8

Depois de coletar os match IDs, o próximo passo é buscar os stats das partidas.

Script:

```text
src/collectors/export_faceit_season8_stats.py
```

Execução:

```bash
python src/collectors/export_faceit_season8_stats.py
```

Output:

```text
data/brz_faceit_season8_stats.csv
```

Esse arquivo agrega os dados por player.

O script também usa cache local para evitar chamadas desnecessárias à API:

```text
data/cache/faceit_match_stats/
```

---

## 🧮 Cálculo dos scores

O cálculo principal das cartas fica em:

```text
src/scoring/calculate_brz_card_scores_v2.py
```

Execução:

```bash
python src/scoring/calculate_brz_card_scores_v2.py
```

Output:

```text
data/brz_card_scores_v2.csv
```

Esse arquivo contém os atributos finais de cada player:

```text
AIM
IMP
UTL
CON
INT
EXP
OVERALL
STATUS
ROLE
```

---

## 🃏 Geração das cartas

As cartas geradas ficam em:

```text
assets/generated/
```

Cada carta é criada visualmente a partir dos dados calculados no arquivo:

```text
data/brz_card_scores_v2.csv
```

---

## 🧪 Status atual

O projeto está em desenvolvimento ativo.

Principais decisões já tomadas:

- ✅ Season 8 como corte oficial
- ✅ Mínimo de 20 partidas para carta ativa
- ✅ Normalização pela própria comunidade BRz
- ✅ Remoção de lifetime stats dos atributos de performance
- ✅ EXP usando apenas lifetime level máximo e lifetime matches
- ✅ Role definida manualmente
- ✅ Role fora do cálculo do OVERALL
- ✅ FACEIT Level atual como multiplicador do OVERALL
- ✅ Players inativos com stats e OVERALL zerados

---

## 🚧 Próximos passos

- [ ] Implementar a nova metodologia no `calculate_brz_card_scores_v2.py`
- [ ] Ajustar cálculo de `INT`
- [ ] Ajustar cálculo de `EXP`
- [ ] Aplicar regra de `INACTIVE`
- [ ] Garantir que players inativos não participem da normalização
- [ ] Recalcular `brz_card_scores_v2.csv`
- [ ] Gerar novas cartas
- [ ] Validar visualmente os resultados
- [ ] Ajustar layout final das cartas
- [ ] Publicar ranking oficial

---

## 🏁 Filosofia do projeto

O BRz Cards não tenta dizer quem é “bom” ou “ruim” de forma absoluta.

A carta é uma leitura estatística e visual da performance do player dentro da comunidade BRz, usando dados da FACEIT e uma metodologia transparente.

A régua principal é:

```text
Comparação entre players ativos da comunidade na Season 8
```

O objetivo é criar algo divertido, competitivo, visualmente forte e minimamente justo.

---

## 👑 BRz eSports

Projeto criado para a comunidade **BRz eSports**.

Feito para transformar dados, rivalidade saudável e resenha em cartas competitivas.

```text
GG.
```
