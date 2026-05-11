# BRz Cards

Bot Discord em Python para gerar cartas personalizadas de jogadores da comunidade **BRz eSports**, usando dados coletados da **Leetify**, processados no **BigQuery** e renderizados em uma carta visual no estilo card de jogador.

O comando principal do bot é:

```bash
/brzcards
```

Atualmente, o projeto está em desenvolvimento local no diretório:

```bash
C:\dev\brz-cards
```

---

## Objetivo do projeto

O objetivo do **BRz Cards** é criar cartas visuais de jogadores da comunidade BRz eSports com base em estatísticas reais de desempenho.

Cada carta combina:

* dados do jogador;
* estatísticas calculadas a partir das partidas;
* score geral da carta;
* foto personalizada do player;
* bandeira do país;
* logo BRz;
* badge FACEIT dinâmica;
* template visual próprio da comunidade.

A ideia é que cada jogador da comunidade tenha uma carta gerada automaticamente, com identidade visual da BRz e atributos calculados a partir de dados reais.

---

## Stack utilizada

O projeto utiliza:

* Python;
* ambiente virtual com `venv`;
* Discord.py;
* Google BigQuery;
* dados coletados da Leetify;
* Steam avatar fallback;
* assets locais para template, logo, flags, badges FACEIT e fotos dos jogadores;
* Pillow para composição visual da carta.

---

## Estrutura principal do projeto

Estrutura esperada do projeto:

```bash
brz-cards/
│
├── assets/
│   ├── templates/
│   │   └── brz_card_template.png
│   │
│   ├── logos/
│   │   └── brz_logo.png
│   │
│   ├── flags/
│   │   └── pt.png
│   │
│   ├── players/
│   │   └── brz_johnny.png
│   │
│   ├── faceit_levels/
│   │   ├── 1.png
│   │   ├── 2.png
│   │   ├── 3.png
│   │   ├── 4.png
│   │   ├── 5.png
│   │   ├── 6.png
│   │   ├── 7.png
│   │   ├── 8.png
│   │   ├── 9.png
│   │   └── 10.png
│   │
│   └── generated/
│
├── src/
│   ├── bot.py
│   ├── test_card_generator.py
│   ├── test_card_generator_layout.py
│   │
│   ├── cards/
│   │   └── card_generator.py
│   │
│   ├── collectors/
│   │   └── collect_leetify_profile.py
│   │
│   └── database/
│       └── bigquery_client.py
│
├── .env
├── .gitignore
├── requirements.txt
└── README.md
```

> Observação: a pasta `assets/generated/` deve existir localmente para armazenar cartas renderizadas, mas deve ser ignorada no Git.

---

## Fluxo geral da aplicação

O fluxo principal do projeto é:

```text
Leetify
   ↓
Coleta de dados via collector
   ↓
BigQuery
   ↓
Tabelas players, player_match_stats e player_card_scores
   ↓
Cálculo e atualização de scores
   ↓
Geração visual da carta
   ↓
Comando /brzcards no Discord
```

---

## Fluxo de dados no BigQuery

O projeto usa três tabelas principais.

### `players`

Guarda os dados principais do jogador.

Informações esperadas:

* `player_id`;
* nickname;
* Steam ID;
* país;
* role;
* avatar;
* `faceit_level`;
* demais metadados do jogador.

O campo `faceit_level` é usado diretamente na renderização da badge FACEIT da carta.

---

### `player_match_stats`

Guarda as partidas coletadas da Leetify.

Essa tabela é a fonte para identificar o FACEIT level mais recente do jogador, com base nas partidas FACEIT salvas.

O projeto **não usa FACEIT API neste momento**.

O FACEIT level vem da Leetify e é salvo no BigQuery.

---

### `player_card_scores`

Guarda os scores calculados para a carta.

A carta utiliza valores dinâmicos para atributos como:

* AIM;
* IMP;
* UTL;
* CON;
* CLT;
* EXP;
* overall.

Os labels visuais desses atributos já existem no template da carta. O Python desenha apenas os valores calculados.

---

## Regra importante sobre FACEIT level

O FACEIT level **não deve ser hardcoded**.

A regra correta é:

```text
Leetify → player_match_stats → players.faceit_level → badge da carta
```

A função responsável por atualizar o FACEIT level do jogador é:

```python
update_player_faceit_level_from_leetify_matches(player_id)
```

Essa função deve buscar a partida FACEIT mais recente disponível em `player_match_stats` e atualizar o campo:

```text
players.faceit_level
```

Para o jogador Johnny, o BigQuery já validou:

```text
faceit_level = 9
```

Portanto, a carta do Johnny deve carregar:

```bash
assets/faceit_levels/9.png
```

Caso `faceit_level` venha como `None`, a badge FACEIT não deve ser desenhada.

---

## Geração da carta

A geração visual da carta acontece principalmente no arquivo:

```bash
src/cards/card_generator.py
```

A função de preview:

```python
generate_player_card_preview()
```

não deve ter dados hardcoded. Ela deve chamar:

```python
generate_player_card("brz_johnny")
```

A função responsável por montar os dados do jogador deve usar:

```python
_parse_faceit_level(profile.get("faceit_level"))
```

Isso garante que a badge FACEIT seja desenhada a partir do valor dinâmico vindo do BigQuery.

---

## Prioridade de imagem do jogador

A imagem do jogador deve seguir esta ordem de prioridade:

```text
1. Foto local do player em assets/players/
2. Avatar FACEIT, caso exista
3. Avatar Steam, caso exista
4. Fallback visual padrão, se necessário
```

No caso do Johnny, a imagem local deve ter prioridade:

```bash
assets/players/brz_johnny.png
```

Isso é importante porque a carta usa uma imagem personalizada no estilo visual da BRz, e não apenas o avatar público do Steam ou FACEIT.

---

## Assets visuais

### Template da carta

Arquivo principal:

```bash
assets/templates/brz_card_template.png
```

O template original está em:

```text
800x800 px
```

Durante a geração, o Python redimensiona para:

```text
600x600 px
```

Depois de renderizar os elementos, a carta final recebe um crop lateral:

```text
40 px de cada lado
```

Resultado final:

```text
520x600 px
```

---

## Regra de coordenadas do layout

As coordenadas visuais foram medidas no Figma/Kittl com base em uma carta de:

```text
600x600 px
```

Como o desenho acontece antes do crop lateral, é importante lembrar:

```text
Coordenada medida no resultado final pode precisar de +40 no código.
```

Exemplo:

Se um elemento parece estar no `x = 100` na imagem final já cortada, no código ele pode precisar estar em:

```text
x = 140
```

Isso acontece porque o crop remove 40 px da esquerda depois que o desenho já foi feito.

---

## Configurações visuais principais

Configuração base:

```python
CANVAS_SIZE = 600
```

A carta final é gerada a partir de um canvas 600x600 e depois cortada lateralmente para 520x600.

Exemplo de configuração visual relevante para a logo:

```python
"logo": {"x": 88, "y": 265, "w": 123, "h": 123}
```

A logo foi ajustada para aparecer mais baixa no card.

---

## Nome, role e stats

Regras visuais atuais:

* o nome do jogador deve aparecer em maiúsculas;
* o nome não deve ter contorno preto;
* a role deve aparecer no campo de role;
* a role não deve ser confundida com o nome;
* os labels `AIM`, `IMP`, `UTL`, `CON`, `CLT`, `EXP` são estáticos no template;
* os valores dos atributos são dinâmicos;
* o overall tem efeito dourado com glow.

---

## Badge FACEIT

As badges FACEIT ficam em:

```bash
assets/faceit_levels/
```

Com arquivos de:

```bash
1.png
2.png
3.png
4.png
5.png
6.png
7.png
8.png
9.png
10.png
```

A lógica esperada é:

```python
level = _parse_faceit_level(profile.get("faceit_level"))
```

Se `level` existir:

```python
badge_path = f"assets/faceit_levels/{level}.png"
```

Se `level` for `None`, a badge não deve ser desenhada.

A badge deve usar o valor dinâmico salvo em:

```text
players.faceit_level
```

---

## Discord bot

O bot principal está em:

```bash
src/bot.py
```

O comando esperado é:

```bash
/brzcards
```

Esse comando deve gerar uma carta para o jogador solicitado ou, no estado atual do projeto, gerar a carta de teste do Johnny.

Fluxo esperado do comando:

```text
Usuário executa /brzcards
   ↓
Bot chama função de geração da carta
   ↓
Sistema busca dados do jogador no BigQuery
   ↓
Sistema renderiza a carta com assets locais
   ↓
Imagem final é enviada no Discord
```

---

## Configuração do ambiente local

### 1. Clonar o projeto

```bash
git clone <url-do-repositorio>
cd brz-cards
```

Ou, se o projeto já estiver localmente:

```bash
cd C:\dev\brz-cards
```

---

### 2. Criar ambiente virtual

No Windows PowerShell:

```powershell
python -m venv .venv
```

Ativar o ambiente:

```powershell
.\.venv\Scripts\Activate.ps1
```

---

### 3. Instalar dependências

```powershell
pip install -r requirements.txt
```

Caso ainda não exista um `requirements.txt`, gerar um a partir do ambiente atual:

```powershell
pip freeze > requirements.txt
```

---

## Variáveis de ambiente

O projeto deve usar um arquivo `.env` local.

Exemplo de variáveis possíveis:

```env
DISCORD_TOKEN=seu_token_do_discord
GOOGLE_APPLICATION_CREDENTIALS=caminho/para/credencial.json
BIGQUERY_PROJECT_ID=seu_project_id
BIGQUERY_DATASET=seu_dataset
```

O arquivo `.env` **nunca deve ser versionado no Git**.

Para ajudar outros desenvolvedores, pode existir um arquivo seguro:

```bash
.env.example
```

Exemplo:

```env
DISCORD_TOKEN=
GOOGLE_APPLICATION_CREDENTIALS=
BIGQUERY_PROJECT_ID=
BIGQUERY_DATASET=
```

---

## Arquivos que não devem ir para o Git

O `.gitignore` deve proteger arquivos sensíveis, ambientes locais e arquivos gerados.

Sugestão de `.gitignore`:

```gitignore
# Python
__pycache__/
*.py[cod]
*.pyo
*.pyd

# Virtual environment
.venv/
venv/

# Environment / secrets
.env
.env.*
!.env.example

# Generated cards
assets/generated/

# Local credentials
credentials/
*.key.json
*service-account*.json
```

---

## Arquivos que podem ser versionados

Estes assets fazem parte da identidade visual do projeto e podem ser versionados:

```bash
assets/templates/
assets/logos/
assets/flags/
assets/faceit_levels/
```

A pasta abaixo também pode ser versionada, desde que o repositório seja privado ou que exista autorização para uso das imagens:

```bash
assets/players/
```

Caso o repositório seja público, é recomendável avaliar com cuidado antes de versionar fotos reais dos jogadores.

---

## Testes locais

O projeto possui arquivos de teste para geração da carta:

```bash
src/test_card_generator.py
src/test_card_generator_layout.py
```

Para testar a geração da carta:

```powershell
python src/test_card_generator.py
```

Para testar ajustes visuais de layout:

```powershell
python src/test_card_generator_layout.py
```

A carta gerada deve ser salva em:

```bash
assets/generated/
```

Como essa pasta é ignorada no Git, as imagens geradas localmente não entram no repositório.

---

## Checklist antes do commit

Antes de fazer commit, executar:

```powershell
git status --short
```

Verificar se `.env`, `.venv` e `assets/generated/` não aparecem como arquivos para commit.

Também é recomendado conferir se algum arquivo sensível já está rastreado:

```powershell
git ls-files .env
git ls-files .venv
git ls-files venv
git ls-files assets/generated
```

Se algum deles aparecer, remover do Git sem apagar localmente:

```powershell
git rm -r --cached --ignore-unmatch .env .venv venv assets/generated
```

Depois conferir novamente:

```powershell
git status --short
```

---

## Staging recomendado

Evitar `git add .` sem revisar.

Adicionar de forma controlada:

```powershell
git add .gitignore
git add README.md
git add requirements.txt
git add src
git add assets/templates
git add assets/logos
git add assets/flags
git add assets/faceit_levels
git add assets/players
```

Conferir o que será commitado:

```powershell
git diff --cached --name-only
```

Não deve aparecer:

```text
.env
.venv/
venv/
assets/generated/
credentials/
service-account json
```

---

## Commit sugerido

Para o marco atual do projeto:

```powershell
git commit -m "feat: generate BRz player cards with dynamic FACEIT level"
```

Esse commit representa:

* geração visual da carta BRz;
* uso de template próprio;
* uso de foto local do jogador;
* fallback para avatar externo;
* badge FACEIT dinâmica;
* integração com BigQuery;
* scores dinâmicos;
* layout ajustado com crop final.

---

## Estado atual do projeto

O estado atual validado é:

* a carta é gerada a partir do template visual da BRz;
* o template original 800x800 é redimensionado para 600x600;
* a imagem final recebe crop lateral de 40 px de cada lado;
* a foto local do Johnny tem prioridade sobre avatares externos;
* o `faceit_level` vem do BigQuery;
* o FACEIT level do Johnny já foi validado como `9`;
* a badge FACEIT deve carregar `assets/faceit_levels/9.png`;
* o nome do jogador aparece em maiúsculas;
* a role aparece no campo correto;
* os labels dos atributos são estáticos no template;
* os valores dos atributos são dinâmicos;
* o overall tem efeito dourado com glow.

---

## Próximos passos recomendados

### 1. Congelar o layout atual

Antes de adicionar novas features, é importante considerar o layout atual como uma versão base estável.

Isso evita que ajustes de lógica quebrem o visual já aprovado.

---

### 2. Validar o FACEIT level dinâmico

Criar ou manter um teste simples garantindo que:

```text
players.faceit_level = 9
```

carrega:

```bash
assets/faceit_levels/9.png
```

E que:

```text
players.faceit_level = None
```

não desenha nenhuma badge.

---

### 3. Validar o comando no Discord

Testar o fluxo real:

```bash
/brzcards
```

Verificar:

* se o bot responde corretamente;
* se a imagem é gerada;
* se a carta é enviada no canal;
* se o arquivo temporário não causa conflito;
* se o bot funciona com o ambiente virtual ativo.

---

### 4. Adicionar suporte para múltiplos jogadores

Depois que a carta do Johnny estiver estável, o próximo passo é permitir que o comando gere cartas para outros jogadores.

Exemplo futuro:

```bash
/brzcards player:brz_johnny
/brzcards player:outro_player
```

Ou:

```bash
/brzcards steam_id:<steam_id>
```

---

### 5. Melhorar tratamento de erro

Adicionar mensagens amigáveis para casos como:

* jogador não encontrado;
* jogador sem partidas suficientes;
* jogador sem score calculado;
* jogador sem foto local;
* falha ao acessar BigQuery;
* badge FACEIT inexistente;
* erro ao renderizar imagem.

---

### 6. Criar cache de cartas geradas

No futuro, pode ser interessante gerar cache para evitar renderização repetida.

Exemplo:

```text
Se os dados do jogador não mudaram desde a última geração, reutilizar a carta existente.
```

Isso pode reduzir custo, tempo de resposta e uso de recursos.

---

### 7. Criar ranking ou coleção de cards

Depois da geração individual estar estável, o projeto pode evoluir para:

* ranking geral da comunidade;
* ranking por AIM, IMP, UTL, CON, CLT e EXP;
* comparação entre jogadores;
* histórico de evolução da carta;
* cartas por temporada;
* carta especial para eventos internos.

---

## Cuidados importantes

### Não hardcodar dados do jogador

Evitar deixar informações fixas dentro do `card_generator.py`, como:

```python
faceit_level = 9
nickname = "JOHNNY"
```

Essas informações devem vir do BigQuery ou de uma camada de dados centralizada.

---

### Não integrar FACEIT API agora

A integração com FACEIT API não faz parte da etapa atual.

O FACEIT level deve continuar vindo da Leetify via BigQuery.

Regra atual:

```text
Não usar FACEIT API.
Não hardcodar FACEIT level.
Usar players.faceit_level.
```

---

### Cuidado com coordenadas após o crop

Como o desenho ocorre antes do crop lateral, qualquer ajuste horizontal precisa considerar a diferença de 40 px.

Regra prática:

```text
Elemento medido na imagem final → somar 40 px no código.
```

---

### Cuidado com assets pessoais

Fotos de jogadores podem ser dados pessoais.

Se o repositório for privado, versionar `assets/players/` pode ser aceitável.

Se o repositório for público, é melhor avaliar se essas fotos devem ficar fora do Git ou ser substituídas por imagens genéricas.

---

## Troubleshooting

### A badge FACEIT não aparece

Verificar:

* se `players.faceit_level` está preenchido no BigQuery;
* se `_parse_faceit_level()` está retornando um número válido;
* se o arquivo existe em `assets/faceit_levels/{level}.png`;
* se o valor não está vindo como `None`;
* se o caminho relativo está correto ao executar o script.

---

### A carta aparece cortada ou desalinhada

Verificar:

* se o template foi redimensionado para 600x600;
* se o crop lateral está removendo 40 px de cada lado;
* se as coordenadas foram medidas no card final ou no canvas antes do crop;
* se o elemento precisa de `+40` no eixo X.

---

### A foto do player não aparece

Verificar:

* se o arquivo existe em `assets/players/`;
* se o nome do arquivo bate com o `player_id` ou slug esperado;
* se a função de busca de imagem local roda antes do fallback Steam/FACEIT;
* se o arquivo está em formato compatível, como PNG.

---

### O bot não responde no Discord

Verificar:

* se o token está no `.env`;
* se o ambiente virtual está ativo;
* se as dependências estão instaladas;
* se o bot foi convidado com permissões corretas;
* se o comando slash foi sincronizado;
* se não há erro no terminal ao iniciar `src/bot.py`.

---

### Erro ao acessar o BigQuery

Verificar:

* se a credencial do Google está configurada;
* se `GOOGLE_APPLICATION_CREDENTIALS` aponta para o arquivo correto;
* se a service account tem permissão no projeto;
* se o dataset e as tabelas existem;
* se o nome do projeto está correto no `.env`.

---

## Convenções do projeto

Recomendações para manter o projeto organizado:

* manter lógica de dados separada da lógica visual;
* evitar dados hardcoded no gerador de cartas;
* centralizar acesso ao BigQuery em `bigquery_client.py`;
* manter assets visuais organizados por categoria;
* salvar imagens geradas apenas em `assets/generated/`;
* manter `assets/generated/` fora do Git;
* testar visualmente a carta antes de alterar o layout;
* fazer commits pequenos e descritivos.

---

## Roadmap sugerido

### Versão 0.1

* gerar carta do Johnny localmente;
* carregar dados dinâmicos do BigQuery;
* renderizar FACEIT level dinâmico;
* estabilizar layout visual;
* enviar carta via Discord.

### Versão 0.2

* suportar múltiplos jogadores;
* permitir escolha do jogador no comando `/brzcards`;
* melhorar mensagens de erro;
* validar ausência de dados;
* organizar cache local.

### Versão 0.3

* adicionar ranking da comunidade;
* criar comandos de comparação;
* adicionar histórico por temporada;
* melhorar design das cartas;
* criar cards especiais.

---

## Resumo técnico

O **BRz Cards** é um bot Discord que transforma dados reais de performance da comunidade BRz eSports em cartas visuais personalizadas.

A regra central do projeto é manter a carta dinâmica e baseada no BigQuery, sem hardcodar informações relevantes.

O FACEIT level, em especial, deve seguir o fluxo:

```text
Leetify → BigQuery → players.faceit_level → assets/faceit_levels/{level}.png
```

A etapa atual é consolidar a geração da carta do Johnny, garantir que o commit está seguro e, em seguida, evoluir para múltiplos jogadores e comandos mais completos no Discord.
