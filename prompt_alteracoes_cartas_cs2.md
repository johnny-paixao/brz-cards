# Prompt — Refatoração do sistema de cartas CS2 (estilo FIFA)

> Cole este documento como instrução para o agente. Ele descreve **o que** mudar em cada stat e no overall. **Onde** mudar (qual arquivo, qual função, qual linha) é trabalho de investigação do agente — o código atual é a fonte da verdade sobre a localização.

---

## Contexto do projeto

Este projeto gera cartas de jogadores de CS2 (estilo cartas FIFA), com 6 atributos (AIM, IMP, UTL, CON, INT, EXP) e uma nota geral (OVERALL). Os dados vêm de duas fontes:

- **API pública da FACEIT** (`open.faceit.com/data/v4`) → médias agregadas da **Season 8 inteira** e dados lifetime.
- **Endpoint interno da FACEIT** (`match-rounds`, cache incremental) → dados **por partida** das partidas mais recentes (round_swing, rating por partida, etc.).

Apenas jogadores **ACTIVE** (≥ 20 partidas na Season 8) entram no cálculo e na normalização. INACTIVE recebe tudo zerado — **manter essa regra como está**.

## Fase 0 — Investigação (faça antes de qualquer alteração)

Antes de editar, mapeie o pipeline e relate o que encontrou:

1. Onde cada uma das 6 stats é calculada hoje (função e arquivo).
2. Onde ficam as funções de normalização (ex.: a normalização atual por `x / máximo`).
3. Onde o OVERALL é montado e onde está o `LEVEL_MULTIPLIER` (multiplicador por nível).
4. De qual fonte cada campo bruto vem (API pública vs cache incremental) e qual janela de partidas é usada.
5. Onde os campos de clutch (`1v1Count`, `1v1Wins`, `1v2Count`, `1v2Wins`), o `faceit_round_swing_avg`, o `faceit_rating` por partida, o `Highest Elo` e o `opponent_team_elo_avg` são lidos/armazenados.

Só depois disso, aplique as mudanças abaixo. Se algum campo necessário não existir no pipeline, **sinalize** em vez de inventar.

---

## Conceito central da refatoração

O objetivo é que as 6 stats sejam **eixos distintos e ortogonais** — cada uma medindo UMA coisa, sem redundância entre elas. A carta deve celebrar **habilidade ("skill"), não tempo de jogo ("volume")**. Várias mudanças abaixo removem volume e redundância para cumprir isso.

---

## 1. Motor de normalização — Curva-S (substitui a normalização atual)

A normalização atual (`valor / máximo × 100`) deve ser **substituída** por uma **Curva-S** ancorada no pool, para as stats que usam normalização relativa.

**Por quê:** a normalização antiga desperdiça metade da régua (ancora no zero, que ninguém atinge) e deixa o "miolo" do pool grudado em notas quase idênticas. A Curva-S dá mais régua onde há mais jogadores (centro da distribuição) e comprime as caudas, sem inventar diferença entre quem é equivalente.

**Especificação da Curva-S:**

- Parâmetros globais: `FLOOR = 50`, `CEILING = 99`, `K = 6` (inclinação).
- Passos para cada valor `x`, dado o conjunto de valores do pool (só jogadores ACTIVE):
  1. `lo = min(pool)`, `hi = max(pool)`. Se `hi == lo`, retornar `FLOOR`.
  2. `t = clamp((x - lo) / (hi - lo), 0, 1)` — posição linear (preserva o gap real).
  3. Aplicar sigmoide: `sig(z) = 1 / (1 + exp(-K·(z - 0.5)))`.
  4. `curva = (sig(t) - sig(0)) / (sig(1) - sig(0))` — normaliza a sigmoide entre 0 e 1.
  5. `nota = FLOOR + curva · (CEILING - FLOOR)`.

**`K = 6` é um dial** ajustável: maior = descola mais o miolo (aproxima de percentil); menor = mais linear (miolo gruda). Começar com 6 e calibrar visualmente depois.

**Aplicar a Curva-S em:** AIM, IMP, UTL, EXP (as stats de escala livre, normalizadas relativas ao pool).
**NÃO aplicar a Curva-S em:** CON e INT (são absolutas — ver seções específicas).

---

## 2. AIM — mecânica de tiro

**Fórmula nova:**

```
AIM = 0,42 · ADR_norm + 0,35 · HS%_norm + 0,23 · KR_norm
```

Onde cada campo (ADR, HS%, KR) é primeiro normalizado individualmente pela **Curva-S** sobre o pool, depois combinado com os pesos acima.

**Mudanças face ao atual:**
- **Remover o KD** completamente do AIM (KD carrega "deaths" = posicionamento, não mira; já é capturado em outras lógicas).
- **Remover qualquer componente de multi-kill** do AIM.
- HS% sobe para 0,35 (era baixo); ADR lidera por ser o sinal mais estável e neutro a função; KR refina como eficiência de conversão.

**Fonte/janela:** API pública, **Season 8 inteira** (médias por partida agregadas).

---

## 3. IMP — impacto no round

**Fórmula nova:**

```
IMP = RoundSwing_norm
```

Onde `RoundSwing` = campo **`faceit_round_swing_avg`** (o campo **geral**, não os `_t`/`_ct` separados), normalizado pela **Curva-S** sobre o pool.

**Mudanças face ao atual:**
- **Remover ADR e KR do IMP** (são do AIM — causavam colinearidade entre AIM e IMP).
- **Não incluir entry nem clutch como componentes** do IMP. O round_swing já captura entry, clutch e impacto de mid-round em forma de deslocamento de probabilidade de vitória — somar entry/clutch por fora seria dupla contagem.
- IMP passa a ser uma stat de **um único campo** (o swing geral).

**Fonte/janela:** **cache incremental**. O IMP **acumula** conforme o cache cresce (usar todas as partidas disponíveis no cache, não uma janela fixa) — porque impacto é uma medida de nível médio, que fica mais robusta com mais amostra.

**Fallback:** se o campo geral `faceit_round_swing_avg` não estiver populado mas os `_t`/`_ct` estiverem, reconstruir o geral ponderando pelos rounds jogados em cada lado. Isso é fallback técnico, não preferência de design.

---

## 4. UTL — utility (granadas)

**Fórmula nova:**

```
UTL = 0,30 · UtilitySuccess_norm
    + 0,22 · UtilityDamageRound_norm
    + 0,28 · FlashSuccess_norm
    + 0,20 · EnemiesFlashedRound_norm
```

Cada campo normalizado individualmente pela **Curva-S** sobre o pool, depois combinado.

**Mudanças face ao atual:**
- **Remover os componentes de volume puro de uso**: `FlashesRound` (flashes por round) e `UtilityUsageRound` (uso de utility por round). Volume de uso não é habilidade — jogar muitas granadas pode ser desperdício. Eficácia (success rate) deve liderar, não volume.
- Estrutura final: dois eixos quase equilibrados — **dano** (UtilitySuccess + UtilityDamageRound ≈ 0,52) e **flash** (FlashSuccess + EnemiesFlashedRound ≈ 0,48), com a eficácia liderando dentro de cada eixo.

**Fonte/janela:** API pública, **Season 8 inteira**.

**Nota:** o UTL naturalmente favorece roles de suporte (IGL, suporte usam mais utility). Isso é desejável (diversidade de identidade no radar) e é controlado pelo peso baixo do UTL no overall — **não tentar "corrigir" esse viés dentro da stat**.

---

## 5. CON — consistência (stat ABSOLUTA, sem Curva-S)

Esta stat foi obtida por **engenharia reversa da barra de "Consistency" da FACEIT** (definida por eles como "how stable your rating is across recent matches"), validada em 7 jogadores reais.

**Fórmula:**

```
CV  = desvio_padrão(ratings das últimas 30) / média(ratings das últimas 30)
CON = round( clamp( 121 - 265 · CV , 0 , 99 ) )
```

**Pontos críticos de implementação:**
- Usar a coluna **"Rating" de performance** por partida (escala aproximada 0,4–1,7), **NÃO** o número grande de ELO acumulado.
- **CON é ABSOLUTO**: NÃO passa pela Curva-S. A escala 0–99 é direta (é uma porcentagem de consistência com significado próprio). Por isso o CON **pode ficar abaixo de 50** (diferente das stats relativas, que têm piso 50).
- `clamp` antes do `round`.
- Arredondamento padrão (`round`, 0,5 para cima).

**Fonte/janela:** **cache incremental**, **janela deslizante das últimas 30 partidas** (fixa em 30). Conforme o cache cresce, usar sempre as 30 mais recentes, descartando as mais antigas da conta. **NÃO acumular** — consistência mede o estado atual do jogador, e os coeficientes `121 / 265` foram calibrados especificamente para janela de 30.

**Atenção (não unificar com IMP):** IMP e CON vêm da mesma fonte (cache) mas usam janelas **diferentes de propósito** — IMP acumula, CON fica em 30 deslizante. Não uniformizar achando que é inconsistência.

**Nota de refinamento futuro (opcional, não implementar agora):** a análise indicou um possível 2º fator (desvio-padrão absoluto além do CV) que explicaria ~2% de variância adicional nos casos extremos. Modelo de 2 fatores `≈ 128 - 84·SD - 212·CV` atingiu R² 0,996, mas precisa de ~12+ jogadores para calibrar sem overfit. Manter a versão de 1 fator (`121 - 265·CV`) por enquanto.

---

## 6. INT — inteligência / sangue frio sob pressão (stat RELATIVA, com Curva-S)

Mede a capacidade de **converter situações de clutch (1vX)** — sangue frio em desvantagem. É a **taxa de vitória em clutch**, normalizada pelo pool.

> **IMPORTANTE — esta stat foi corrigida.** Versões anteriores usavam punição assimétrica (k=1,4) e escala absoluta, o que afundava **todos** os jogadores (porque o break-even ficava em 58% de win rate de clutch, irreal — ninguém ganha tanto de 1v2). A versão correta abaixo usa **win rate puro (sem assimetria) normalizado pela Curva-S relativa ao pool**.

**Definição de "conversão de clutch":**

```
winrate_1v1 = 1v1Wins / 1v1Count
winrate_1v2 = 1v2Wins / 1v2Count
```

Um clutch "convertido" = o jogador esteve na situação (entrou em `Count`) e **venceu o round** (entrou em `Wins`).

> **Agente: confirmar a definição de "Win" da FACEIT.** O esperado é que `1v1Wins`/`1v2Wins` signifiquem **"venceu o round"** (resolveu a situação a favor do time), não apenas "matou os oponentes". Verifique na documentação ou inspecionando os dados (ex.: `Wins ≤ Count` sempre). Se a definição for outra, sinalize.

**Fórmula:**

```
INT_bruto = 0,75 · winrate_1v2 + 0,25 · winrate_1v1
INT       = round( Curva-S(INT_bruto) sobre o pool )
```

- **1v2 pesa mais (0,75 vs 0,25)** porque a desvantagem numérica é onde a inteligência sob pressão realmente aparece (1v1 é quase um duelo normal).
- **Sem punição assimétrica** (equivalente a k=1,0). O "baiter" (quem sobra muito mas converte mal) cai no fundo do pool **naturalmente**, por ter o pior win rate de clutch — a Curva-S relativa já o coloca embaixo, sem precisar de assimetria artificial.
- **INT é RELATIVO** (Curva-S, igual a AIM/IMP/UTL/EXP, piso 50). Mudou em relação às versões anteriores: o INT **não** é mais absoluto, porque não há referência externa que defina "tantos % de clutch = tal nota" (diferente do CON, que foi calibrado contra a barra real da FACEIT).
- **Não incluir entry** (é mecânica/impacto = AIM/IMP).
- **Não usar KAST** (não existe no payload, não dá para reconstruir o componente "Traded").
- **Sem shrinkage** — o corte de 20 partidas já filtra amostras minúsculas; converter poucos clutches com boa taxa é um feito legítimo.

**Regra de borda — quando falta um tipo de clutch (Count = 0):**

Não reponderar para 100% no componente que sobra (isso superestimaria o sinal mais fraco e permitiria notas extremas baseadas em 1-2 eventos). Em vez disso, **preencher o componente ausente com a média do pool**:

| Situação | INT_bruto |
|----------|-----------|
| Tem 1v1 e 1v2 | `0,75·winrate_1v2 + 0,25·winrate_1v1` |
| Tem 1v1, **sem 1v2** | `0,75·(média_pool_1v2) + 0,25·winrate_1v1` |
| Tem 1v2, **sem 1v1** | `0,75·winrate_1v2 + 0,25·(média_pool_1v1)` |
| Sem nenhum | `INT_bruto = média do pool` (fica neutro) |

Onde `média_pool_1vX` = média do `winrate_1vX` **apenas dos jogadores que têm aquele tipo** (Count > 0). Ordem de cálculo: (1) calcular os winrates de quem tem cada tipo, (2) tirar as médias do pool, (3) preencher os ausentes, (4) combinar e aplicar Curva-S. Tratar explicitamente para evitar divisão por zero.

**Fonte/janela:** API pública, **Season 8 inteira** (`1v1Count`, `1v1Wins`, `1v2Count`, `1v2Wins`).

---

## 7. EXP — experiência qualitativa

Mede o **teto de habilidade já alcançado** (experiência qualitativa = "chegou longe"), não volume de partidas (experiência quantitativa = "jogou muito").

**Fórmula nova:**

```
EXP = PeakElo_norm
```

Onde `PeakElo` = campo **`Highest Elo`**, normalizado pela **Curva-S** sobre o pool.

**Mudanças face ao atual:**
- **Remover completamente o componente de volume de partidas** (lifetime matches). Volume mede tempo de jogo, não habilidade, e contradiz a filosofia "skill, não tempo" da carta.
- EXP passa a ser **peak ELO puro** (um único campo).

**Fonte:** o `Highest Elo` é mantido **manualmente** (via consulta ao FACEIT tracker) e atualizado dinamicamente — quando um jogador supera o próprio recorde de ELO, o novo valor substitui o antigo. Essa lógica já existe; **preservá-la**.

**Normalização:** Curva-S relativa ao pool (ELO é escala livre, sem teto natural — por isso é relativo, diferente de CON/INT).

---

## 8. OVERALL — consolidação

**Sequência de cálculo:**

```
1. OVERALL_base = 0,24·AIM + 0,24·IMP + 0,10·UTL + 0,20·CON + 0,12·INT + 0,10·EXP

2. CONTEXT_MULT = clamp( (opp_elo_médio / E_ref) ^ 0,4 , 0,80 , 1,12 )
       onde:
       - opp_elo_médio = média do `opponent_team_elo_avg` do jogador (das partidas disponíveis no cache)
       - E_ref = mediana do opp_elo_médio entre todos os jogadores ACTIVE do pool

3. OVERALL_dif = OVERALL_base × CONTEXT_MULT

4. OVERALL_final = OVERALL_dif + 0,15 · (rating_norm - OVERALL_dif)
       onde rating_norm = `faceit_rating` do jogador normalizado para a mesma escala 0–99 do pool

5. OVERALL = round( clamp( OVERALL_final , 0 , 99 ) )
```

**Mudanças face ao atual:**

- **Substituir o `LEVEL_MULTIPLIER` discreto** (10 baldes fixos por nível: 0,78 … 1,10) pelo **`CONTEXT_MULTIPLIER` contínuo** baseado no `opponent_team_elo_avg` real. Isso reconhece a dificuldade real do ambiente enfrentado (contínua), em vez de degraus por nível. Dentro de um mesmo nível, quem pega lobbies mais duros é reconhecido.
  - `β = 0,4` e clamp `[0,80; 1,12]` são dials ajustáveis.
- **Adicionar a âncora do rating** (`k = 0,15`): puxa levemente o overall na direção do `faceit_rating` da FACEIT, corrigindo excessos da fórmula própria sem deixar o viés de fragging do rating dominar. Onde a fórmula e o rating concordam, quase nada muda; onde discordam muito, o overall cede 15% na direção do rating.

**Pesos — racional:** AIM e IMP lideram (coração do jogo); CON tem peso alto (confiabilidade importa); UTL e EXP têm os menores pesos (0,10 cada) — isso impede que um jogador mediano infle o overall só por utility/exp. Os pesos são a parte mais "ajustável por gosto" — podem ser recalibrados depois de ver as cartas.

---

## Resumo da arquitetura de normalização

| Stat | Normalização | Fonte | Janela |
|------|-------------|-------|--------|
| AIM | Curva-S (relativa ao pool) | API pública | Season 8 inteira |
| IMP | Curva-S (relativa ao pool) | Cache incremental | **Acumula** |
| UTL | Curva-S (relativa ao pool) | API pública | Season 8 inteira |
| CON | **Absoluta** (`121 - 265·CV`) | Cache incremental | **30 deslizante** |
| INT | Curva-S (relativa ao pool) | API pública | Season 8 inteira |
| EXP | Curva-S (relativa ao pool) | `Highest Elo` (manual/tracker) | — |

- **5 stats relativas** (Curva-S, piso 50): AIM, IMP, UTL, **INT**, EXP.
- **1 stat absoluta** (significado próprio, calibrada contra a FACEIT): **CON** — pode ir abaixo de 50 (proposital).
- Todas as stats finais e o OVERALL são **inteiros** (arredondamento padrão).

---

## Avisos para o agente

1. **Não unificar janelas de IMP e CON** — vêm da mesma fonte (cache) mas IMP acumula e CON fica em 30 deslizante, de propósito.
2. **Apenas o CON não passa pela Curva-S** (é absoluto, calibrado contra a FACEIT). AIM, IMP, UTL, INT e EXP usam Curva-S relativa ao pool. Não "consertar" isso achando que é bug.
3. **O CON pode ficar abaixo de 50** (castigo de inconsistência). As stats relativas (incluindo INT) têm piso 50 — o baiter cai para perto de 50, no fundo do pool, mas não abaixo.
4. **Preservar a regra ACTIVE/INACTIVE** (≥ 20 partidas Season 8) e a manutenção manual/dinâmica do `Highest Elo`.
5. Se qualquer campo necessário não existir no pipeline (`opponent_team_elo_avg`, `faceit_round_swing_avg`, `faceit_rating` por partida, campos de clutch `1v1`/`1v2`), **sinalizar** antes de prosseguir, em vez de inventar valores.
6. **Confirmar a definição de "Win" nos campos de clutch** (`1v1Wins`/`1v2Wins`): o esperado é "venceu o round", não "matou os oponentes". Verificar antes de implementar o INT.
7. **Tratar Count=0 no INT** com a regra de borda (preencher o tipo ausente com a média do pool, nunca reponderar para 100% no sinal que sobra, nunca dividir por zero).
8. Os dials (`K=6` da Curva-S, `β=0,4` e clamp do multiplier, `k=0,15` da âncora do rating, pesos do overall) devem ficar como **constantes nomeadas e fáceis de ajustar**, não enterradas no meio do código.