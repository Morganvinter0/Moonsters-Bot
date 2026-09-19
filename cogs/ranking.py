from __future__ import annotations

from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from config import CORES, ETAPA_ALIASES, ETAPA_NOMES, ETAPA_ORDEM


MEDALHAS = ["🥇", "🥈", "🥉"]


def _periodo_desde(periodo: str) -> tuple[str | None, str]:
    agora = datetime.now(timezone.utc)
    if periodo == "semana":
        return (agora - timedelta(days=7)).isoformat(), "últimos 7 dias"
    if periodo == "mes":
        return (agora - timedelta(days=30)).isoformat(), "últimos 30 dias"
    return None, "todo o período"


class Ranking(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="ranking",
        description="Ranking dos staffs que mais fizeram etapas",
    )
    @app_commands.describe(
        periodo="Período do ranking",
        etapa="Opcional: filtrar por uma etapa (TD, TL, RV...)",
    )
    @app_commands.choices(
        periodo=[
            app_commands.Choice(name="Todo o período", value="tudo"),
            app_commands.Choice(name="Últimos 7 dias", value="semana"),
            app_commands.Choice(name="Últimos 30 dias", value="mes"),
        ]
    )
    async def ranking(
        self,
        interaction: discord.Interaction,
        periodo: app_commands.Choice[str] | None = None,
        etapa: str | None = None,
    ):
        if not interaction.guild:
            return await interaction.response.send_message("Use no servidor.", ephemeral=True)

        valor_periodo = periodo.value if periodo else "tudo"
        since, rotulo = _periodo_desde(valor_periodo)

        tipo = None
        if etapa:
            tipo = ETAPA_ALIASES.get(etapa.strip().upper().replace(" ", ""))
            if not tipo:
                return await interaction.response.send_message("Etapa inválida.", ephemeral=True)

        if tipo:
            rows = await self.bot.db.ranking_por_etapa(interaction.guild.id, tipo)  # type: ignore
            titulo = f"Ranking — {ETAPA_NOMES[tipo]} (`{tipo}`)"
        else:
            rows = await self.bot.db.ranking(interaction.guild.id, since=since)  # type: ignore
            titulo = "Ranking da staff"

        if not rows:
            return await interaction.response.send_message(
                "Ainda não há etapas registradas nesse filtro.", ephemeral=True
            )

        embed = discord.Embed(title=titulo, color=CORES["ok"])
        embed.set_footer(text=rotulo if not tipo else f"{ETAPA_NOMES[tipo]} · {rotulo}")
        linhas = []
        for i, r in enumerate(rows, start=1):
            medalha = MEDALHAS[i - 1] if i <= 3 else f"`{i}.`"
            linhas.append(f"{medalha} <@{r['user_id']}> — **{r['total']}** etapa(s)")
        embed.description = "\n".join(linhas)
        await interaction.response.send_message(embed=embed)

    @ranking.autocomplete("etapa")
    async def ranking_etapa_ac(self, interaction: discord.Interaction, current: str):
        current = (current or "").upper()
        out = []
        for sigla in ETAPA_ORDEM:
            nome = ETAPA_NOMES[sigla]
            if not current or current in sigla or current in nome.upper():
                out.append(app_commands.Choice(name=f"{sigla} — {nome}", value=sigla))
        return out

    @app_commands.command(name="ajuda", description="Como usar o bot de scan")
    async def ajuda(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Bot de Scan — comandos",
            color=CORES["info"],
            description=(
                "Fluxo: cadastra a obra → abre capítulo ao marcar a primeira etapa → "
                "cada um marca a etapa que fez → o cargo de fechar usa `/fechar`. "
                "Cap fechado pode ser reaberto com `/reabrir`. "
                "Pode ter vários capítulos abertos na mesma obra."
            ),
        )
        embed.add_field(
            name="Obras",
            value=(
                "`/adc nome sigla` — cadastrar obra\n"
                "`/obras` — listar obras\n"
                "`/status obra` — caps ativos e fechados\n"
                "`/remover obra` — apaga a obra e os capítulos\n"
                "`/obra_pausar`"
            ),
            inline=False,
        )
        embed.add_field(
            name="Capítulos e etapas",
            value=(
                "`/cap obra capitulo etapa` — marcar etapa (ex: `/cap OP 101 TL`)\n"
                "`/vercap obra capitulo` — ver progresso\n"
                "`/caps [obra]` — capítulos abertos\n"
                "`/fechar` · `/reabrir` · `/desfazer`"
            ),
            inline=False,
        )
        embed.add_field(
            name="Etapas",
            value="`RW` Raw · `CL` Clean/RD · `TD` Tradução · `TL` Typer · `RV` Revisão · `QA` Q.A · `QC` Q.C",
            inline=False,
        )
        embed.add_field(
            name="Staff",
            value="`/ranking` — quem mais fez etapas (geral, 7 dias, 30 dias ou por etapa)",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Ranking(bot))
