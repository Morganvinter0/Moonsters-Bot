from __future__ import annotations

from typing import Iterable, Optional

import discord

from config import CORES, ETAPA_NOMES, ETAPA_ORDEM


def barra(feitos: int, total: int = 7, tamanho: int = 7) -> str:
    if total <= 0:
        return ""
    preenchido = round((feitos / total) * tamanho)
    return "▰" * preenchido + "▱" * (tamanho - preenchido)


def embed_base(titulo: str, cor: int = CORES["info"]) -> discord.Embed:
    return discord.Embed(title=titulo, color=cor)


def formatar_etapas(etapas: dict, pendentes: bool = True) -> str:
    linhas = []
    for sigla in ETAPA_ORDEM:
        nome = ETAPA_NOMES[sigla]
        if sigla in etapas:
            e = etapas[sigla]
            linhas.append(f"`{sigla}` **{nome}** — <@{e['user_id']}>")
        elif pendentes:
            linhas.append(f"`{sigla}` **{nome}** — *em aberto*")
    return "\n".join(linhas) if linhas else "*Nenhuma etapa registrada.*"


def embed_capitulo(
    obra_nome: str,
    obra_sigla: str,
    numero: str,
    status: str,
    etapas: dict,
    extra: Optional[str] = None,
) -> discord.Embed:
    feitos = sum(1 for s in ETAPA_ORDEM if s in etapas)
    total = len(ETAPA_ORDEM)
    fechado = status == "fechado"
    cor = CORES["ok"] if fechado else (CORES["aviso"] if feitos else CORES["info"])
    titulo = f"{obra_sigla} — Cap. {numero}"
    embed = discord.Embed(title=titulo, color=cor)
    embed.description = f"**{obra_nome}**\n{barra(feitos, total)} `{feitos}/{total}`"
    embed.add_field(name="Etapas", value=formatar_etapas(etapas), inline=False)
    status_txt = "Fechado" if fechado else "Aberto"
    embed.set_footer(text=f"Status: {status_txt}")
    if extra:
        embed.add_field(name="\u200b", value=extra, inline=False)
    return embed


def embed_obra_status(
    obra,
    stats: dict,
    caps_abertos: Iterable,
    progresso: dict[int, int],
) -> discord.Embed:
    embed = discord.Embed(
        title=f"{obra['sigla']} — {obra['nome']}",
        color=CORES["obra"] if obra["status"] == "ativa" else CORES["aviso"],
    )
    embed.add_field(name="Status da obra", value=obra["status"].capitalize(), inline=True)
    embed.add_field(name="Caps abertos", value=str(stats["abertos"]), inline=True)
    embed.add_field(name="Caps fechados", value=str(stats["fechados"]), inline=True)

    linhas = []
    for cap in caps_abertos:
        feitos = progresso.get(cap["id"], 0)
        linhas.append(f"`{cap['numero']}` {barra(feitos)} `{feitos}/{len(ETAPA_ORDEM)}`")
    embed.add_field(
        name="Capítulos ativos",
        value="\n".join(linhas) if linhas else "*Nenhum capítulo aberto.*",
        inline=False,
    )
    embed.set_footer(text=f"Total de capítulos: {stats['total']}")
    return embed
