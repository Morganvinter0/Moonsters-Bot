import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN", "")
GUILD_ID = int(os.getenv("GUILD_ID") or "1519505177478959114")

# Cargo que marca etapa / abre cap, MAS NÃO fecha nem reabre
ROLE_ABRIR_ID = int(os.getenv("ROLE_ABRIR_ID", "1549173200930209956") or 0)
# Cargo que abre, fecha e reabre capítulo
ROLE_FECHAR_ID = int(os.getenv("ROLE_FECHAR_ID", "1531111836152234054") or 0)
# Compatível com versão antiga
STAFF_ROLE_ID = ROLE_FECHAR_ID

# Fecha sozinho quando todas as etapas estão prontas? 0 = só o cargo de fechar
AUTO_FECHAR = os.getenv("AUTO_FECHAR", "0").strip() not in {"0", "false", "False", "nao", "não"}

# Ordem do pipeline. Sigla usada nos comandos + nome bonito no embed.
ETAPAS = [
    ("RW", "Raw"),
    ("CL", "Clean/RD"),
    ("TD", "Tradução"),
    ("TL", "Typer"),
    ("RV", "Revisão"),
    ("QA", "Q.A"),
    ("QC", "Q.C"),
]

ETAPA_ALIASES = {
    "RW": "RW",
    "RAW": "RW",
    "CL": "CL",
    "CL/RD": "CL",
    "CLRD": "CL",
    "CLEAN": "CL",
    "RD": "CL",
    "REDRAW": "CL",
    "TD": "TD",
    "TRAD": "TD",
    "TRADUCAO": "TD",
    "TRADUÇÃO": "TD",
    "TL": "TL",
    "TYPER": "TL",
    "TYPESET": "TL",
    "TS": "TL",
    "RV": "RV",
    "REV": "RV",
    "REVISAO": "RV",
    "REVISÃO": "RV",
    "QA": "QA",
    "Q.A": "QA",
    "Q.A.": "QA",
    "QC": "QC",
    "Q.C": "QC",
    "Q.C.": "QC",
}

ETAPA_NOMES = {sigla: nome for sigla, nome in ETAPAS}
ETAPA_ORDEM = [sigla for sigla, _ in ETAPAS]

CORES = {
    "ok": 0x2ECC71,
    "aviso": 0xF1C40F,
    "erro": 0xE74C3C,
    "info": 0x5865F2,
    "obra": 0x9B59B6,
}
