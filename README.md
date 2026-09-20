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
| `/cap obra capitulo etapa` | Marca etapa em um ou vários capítulos. Ex.: `OP` + `101,102,103` + `TL`. Para várias obras com capítulos diferentes: `OP:101,102;NAR:5,6` + `TL`. |
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
/cap obra:OP capitulo:101,102,103 etapa:TL
/cap obra:OP,NAR capitulo:101,102 etapa:RW
/cap obra:OP:101,102;NAR:5,6 etapa:QC
/status obra:OP
/ranking periodo:Últimos 30 dias
```

Pode ter o 101 e o 102 abertos ao mesmo tempo na mesma obra.

### `/cap` em lote

O comando aceita até **50 capítulos por execução**.

- **Vários capítulos da mesma obra:** `obra:OP` + `capitulo:101,102,103`
- **Várias obras usando os mesmos capítulos:** `obra:OP,NAR` + `capitulo:101,102`
  - Isso registra `101` e `102` nas duas obras.
- **Várias obras com capítulos diferentes:** coloque o mapeamento no campo `obra`:
  `obra:OP:101,102;NAR:5,6`
  - Também pode usar `|`: `OP:101,102 | NAR:5,6`
- **Uma etapa é aplicada a todos os capítulos informados.** Ex.: etapa `TL` marca `TL` em todos os caps.
- Se um capítulo já tiver essa etapa, ela continua sendo atualizada para o usuário que executou o comando, seguindo a regra atual do bot.
- Capítulos fechados não são alterados; eles aparecem na lista de erros.
- Se `AUTO_FECHAR=1`, um capítulo que completar as 7 etapas será fechado automaticamente, inclusive em lote.
- Se uma obra não existir ou estiver pausada, somente os itens dessa obra falham; os demais continuam sendo processados.

O formato `OP:101,102;NAR:5,6` é o recomendado quando os números dos capítulos são diferentes entre as obras.

## Personalizar etapas

Edite a lista `ETAPAS` e os `ETAPA_ALIASES` em `config.py` e reinicie o bot.


## Novos comandos
- `/dashboard` — painel geral.
- `/dashboard_equipe equipe` — produção de uma equipe.
- `/registrar_equipe nome [membro]` — cria equipe (admin).
- `/perfil [membro]` — estatísticas individuais.
- `/rank` — ranking geral.
- `/semanal` e `/smanal` — produção dos últimos 7 dias.
- `/top_etapa` — top 3 de cada etapa.
- `/medalhas [membro]` — conquistas por produção.

O comando `/ia` não foi implementado.
