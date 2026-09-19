from __future__ import annotations

from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from config import CORES
from embeds import embed_obra_status
from permissoes import MSG_SEM_OBRA, pode_gerenciar_obra


class Obras(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _obra_autocomplete(self, interaction: discord.Interaction, current: str):
        if not interaction.guild:
            return []
        rows = await self.bot.db.search_obras(interaction.guild.id, current or "")  # type: ignore
        return [
            app_commands.Choice(name=f"{r['sigla']} — {r['nome']}", value=r["sigla"])
            for r in rows[:25]
        ]

    @app_commands.command(name="adc", description="Cadastra uma nova obra no servidor")
    @app_commands.describe(
        nome="Nome completo da obra",
        sigla="Sigla curta usada nos comandos (ex: OP, JJK)",
    )
    async def adc(self, interaction: discord.Interaction, nome: str, sigla: str):
        if not interaction.guild:
            return await interaction.response.send_message("Use no servidor.", ephemeral=True)
        if not pode_gerenciar_obra(interaction):
            return await interaction.response.send_message(MSG_SEM_OBRA, ephemeral=True)

        sigla = sigla.upper().replace(" ", "")
        if len(sigla) > 12:
            return await interaction.response.send_message(
                "Sigla muito longa (máx. 12 caracteres).", ephemeral=True
            )
        existente = await self.bot.db.get_obra(interaction.guild.id, sigla)  # type: ignore
        if existente:
            return await interaction.response.send_message(
                f"Já existe obra com essa sigla: **{existente['sigla']}** — {existente['nome']}",
                ephemeral=True,
            )

        obra = await self.bot.db.add_obra(  # type: ignore
            interaction.guild.id, nome, sigla, interaction.user.id
        )
        embed = discord.Embed(
            title="Obra cadastrada",
            description=f"**{obra['nome']}** (`{obra['sigla']}`)",
            color=CORES["ok"],
        )
        embed.set_footer(text="Use /cap para abrir o primeiro capítulo")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="obras", description="Lista as obras cadastradas")
    async def obras(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("Use no servidor.", ephemeral=True)
        rows = await self.bot.db.list_obras(interaction.guild.id)  # type: ignore
        if not rows:
            return await interaction.response.send_message(
                "Nenhuma obra cadastrada. Use `/adc` para criar a primeira.",
                ephemeral=True,
            )
        embed = discord.Embed(title="Obras do servidor", color=CORES["obra"])
        ativas, pausadas = [], []
        for o in rows:
            stats = await self.bot.db.stats_obra(o["id"])  # type: ignore
            linha = (
                f"`{o['sigla']}` **{o['nome']}** — "
                f"{stats['abertos']} aberto(s) · {stats['fechados']} fechado(s)"
            )
            (ativas if o["status"] == "ativa" else pausadas).append(linha)
        if ativas:
            embed.add_field(name="Ativas", value="\n".join(ativas)[:1024], inline=False)
        if pausadas:
            embed.add_field(name="Pausadas", value="\n".join(pausadas)[:1024], inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="status", description="Status da obra: caps ativos e fechados")
    @app_commands.describe(obra="Sigla ou nome da obra")
    async def status(self, interaction: discord.Interaction, obra: str):
        if not interaction.guild:
            return await interaction.response.send_message("Use no servidor.", ephemeral=True)
        row = await self.bot.db.get_obra(interaction.guild.id, obra)  # type: ignore
        if not row:
            return await interaction.response.send_message(
                f"Obra `{obra}` não encontrada. Use `/obras`.", ephemeral=True
            )
        stats = await self.bot.db.stats_obra(row["id"])  # type: ignore
        caps = await self.bot.db.list_caps(row["id"], status="aberto")  # type: ignore
        progresso = await self.bot.db.progresso_caps([c["id"] for c in caps])  # type: ignore
        embed = embed_obra_status(row, stats, caps, progresso)
        await interaction.response.send_message(embed=embed)

    @status.autocomplete("obra")
    async def status_ac(self, interaction: discord.Interaction, current: str):
        return await self._obra_autocomplete(interaction, current)

    @app_commands.command(name="obra_pausar", description="Pausa ou reativa uma obra")
    @app_commands.describe(obra="Sigla ou nome", acao="pausar ou reativar")
    @app_commands.choices(
        acao=[
            app_commands.Choice(name="Pausar", value="pausada"),
            app_commands.Choice(name="Reativar", value="ativa"),
        ]
    )
    async def obra_pausar(
        self, interaction: discord.Interaction, obra: str, acao: app_commands.Choice[str]
    ):
        if not interaction.guild:
            return await interaction.response.send_message("Use no servidor.", ephemeral=True)
        if not pode_gerenciar_obra(interaction):
            return await interaction.response.send_message(MSG_SEM_OBRA, ephemeral=True)
        row = await self.bot.db.get_obra(interaction.guild.id, obra)  # type: ignore
        if not row:
            return await interaction.response.send_message("Obra não encontrada.", ephemeral=True)
        await self.bot.db.set_obra_status(row["id"], acao.value)  # type: ignore
        await interaction.response.send_message(
            f"**{row['sigla']}** agora está `{acao.value}`."
        )

    @obra_pausar.autocomplete("obra")
    async def pausar_ac(self, interaction: discord.Interaction, current: str):
        return await self._obra_autocomplete(interaction, current)

    @app_commands.command(name="remover", description="Remove uma obra e todos os capítulos dela")
    @app_commands.describe(obra="Sigla ou nome da obra")
    async def remover(self, interaction: discord.Interaction, obra: str):
        if not interaction.guild:
            return await interaction.response.send_message("Use no servidor.", ephemeral=True)
        if not pode_gerenciar_obra(interaction):
            return await interaction.response.send_message(MSG_SEM_OBRA, ephemeral=True)
        row = await self.bot.db.get_obra(interaction.guild.id, obra)  # type: ignore
        if not row:
            return await interaction.response.send_message("Obra não encontrada.", ephemeral=True)
        stats = await self.bot.db.stats_obra(row["id"])  # type: ignore
        await self.bot.db.delete_obra(row["id"])  # type: ignore
        await interaction.response.send_message(
            f"Obra **{row['sigla']} — {row['nome']}** removida "
            f"({stats['total']} capítulo(s) apagados)."
        )

    @remover.autocomplete("obra")
    async def remover_ac(self, interaction: discord.Interaction, current: str):
        return await self._obra_autocomplete(interaction, current)


async def setup(bot: commands.Bot):
    await bot.add_cog(Obras(bot))
