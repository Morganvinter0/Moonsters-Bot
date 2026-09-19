# Bot de Scan (Discord)

Bot para gerenciar obras, capítulos e etapas de um grupo de scan. Feito em Python (`discord.py` + SQLite).

## Fluxo

1. Staff cadastra a obra com `/adc`.
2. Qualquer um marca uma etapa com `/cap`. Se o capítulo ainda não existe, ele é aberto.
3. A mesma obra pode ter **vários capítulos abertos** ao mesmo tempo.
4. Quando as 7 etapas estão preenchidas, o capítulo **fecha sozinho** (ou use `/fechar` se o auto-fechar estiver desligado).
5. `/ranking` mostra quem mais trabalhou.

## Etapas

| Sigla | Nome      |
|-------|-----------|
| RW    | Raw       |
| CL    | Clean/RD  |
| TD    | Tradução  |
| TL    | Typer     |
| RV    | Revisão   |
| QA    | Q.A       |
| QC    | Q.C       |

## Comandos

| Comando | O que faz |
|---------|-----------|
| `/adc nome sigla` | Cadastra obra |
| `/obras` | Lista obras |
| `/status obra` | Caps ativos e fechados da obra |
| `/cap obra capitulo etapa` | Marca etapa (ex.: obra `OP`, cap `101`, etapa `TL`) |
| `/vercap obra capitulo` | Mostra o progresso do cap |
| `/caps [obra]` | Lista capítulos abertos |
| `/fechar obra capitulo` | Fecha o cap na mão |
| `/reabrir obra capitulo` | Reabre cap fechado (staff) |
| `/desfazer obra capitulo etapa` | Tira uma etapa marcada errado |
| `/ranking` | Ranking da staff |
| `/remover obra` | Apaga a obra e todos os capítulos |
| `/obra_pausar` | Pausar ou reativar obra |
| `/ajuda` | Lista os comandos |

Permissões por cargo (`.env`):

- `ROLE_ABRIR_ID` — marca etapa e abre capítulo. **Não fecha.**
- `ROLE_FECHAR_ID` — abre, fecha (`/fechar`) e reabre (`/reabrir`). Também cadastra obra.
- Quem tem **Gerenciar Servidor** passa por cima dos dois.

## Como subir o bot

### 1. Criar o app no Discord

1. Acesse [Discord Developer Portal](https://discord.com/developers/applications).
2. New Application → Bot → Reset Token → copie o token.
3. Em **Bot**, ligue o bot (ele já vem habilitado). Intents privilegiados **não** são necessários.
4. OAuth2 → URL Generator:
   - Scopes: `bot` + `applications.commands`
   - Permissões: `Send Messages`, `Embed Links`, `Use Application Commands`
5. Abra a URL e convide o bot para o servidor.

### 2. Instalar

```bash
cd scan-bot
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edite o `.env`:

```
DISCORD_TOKEN=token_copiado_do_portal
GUILD_ID=1519505177478959114
STAFF_ROLE_ID=
AUTO_FECHAR=1
```

- `GUILD_ID` (recomendado): os slash commands aparecem **na hora** nesse servidor. Sem ele, a sincronização global pode levar até 1 hora.
- Para copiar IDs no Discord: Configurações → Avançado → Modo desenvolvedor, depois clique com o botão direito no servidor/cargo → Copiar ID.
- `AUTO_FECHAR=0` (padrão): só o cargo `ROLE_FECHAR_ID` fecha com `/fechar`.

### 3. Rodar

```bash
python bot.py
```

Os dados ficam em `data/scan.db`. Não apague essa pasta se quiser manter o histórico.

## Exemplos

```
/adc nome:One Piece sigla:OP
/cap obra:OP capitulo:101 etapa:TD
/cap obra:OP capitulo:101 etapa:TL
/cap obra:OP capitulo:102 etapa:RW
/status obra:OP
/ranking periodo:Últimos 30 dias
```

Pode ter o 101 e o 102 abertos ao mesmo tempo na mesma obra.

## Personalizar etapas

Edite a lista `ETAPAS` e os `ETAPA_ALIASES` em `config.py` e reinicie o bot.
"# Moonsters-Bot" 
