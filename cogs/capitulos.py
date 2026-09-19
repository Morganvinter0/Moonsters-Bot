from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from config import AUTO_FECHAR, CORES, ETAPA_ALIASES, ETAPA_NOMES, ETAPA_ORDEM
from embeds import barra, embed_capitulo
from permissoes import MSG_SEM_ABRIR, MSG_SEM_FECHAR, pode_abrir, pode_fechar


def _normaliza_etapa(valor: str) -> str | None:
    key = valor.strip().upper().replace(" ", "")
    return ETAPA_ALIASES.get(key)


class Capitulos(commands.Cog):
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

    async def _etapa_autocomplete(self, interaction: discord.Interaction, current: str):
        current = (current or "").upper()
        choices = []
        for sigla, nome in ETAPA_NOMES.items():
            label = f"{sigla} — {nome}"
            if not current or current in sigla or current in nome.upper():
                choices.append(app_commands.Choice(name=label, value=sigla))
        return choices[:25]

    @app_commands.command(
        name="cap",
        description="Registra sua etapa em um capítulo (cria o cap se ainda não existir)",
    )
    @app_commands.describe(
        obra="Sigla ou nome da obra",
        capitulo="Número do capítulo (ex: 101 ou 101.5)",
        etapa="Etapa que você finalizou: RW, CL, TD, TL, RV, QA, QC",
    )
    async def cap(
        self, interaction: discord.Interaction, obra: str, capitulo: str, etapa: str
    ):
        if not interaction.guild:
            return await interaction.response.send_message("Use no servidor.", ephemeral=True)
        if not pode_abrir(interaction):
            return await interaction.response.send_message(MSG_SEM_ABRIR, ephemeral=True)

        tipo = _normaliza_etapa(etapa)
        if not tipo:
            validas = ", ".join(ETAPA_ORDEM)
            return await interaction.response.send_message(
                f"Etapa `{etapa}` inválida. Use: {validas}", ephemeral=True
            )

        row_obra = await self.bot.db.get_obra(interaction.guild.id, obra)  # type: ignore
        if not row_obra:
            return await interaction.response.send_message(
                f"Obra `{obra}` não encontrada. Cadastre com `/adc`.", ephemeral=True
            )
        if row_obra["status"] != "ativa":
            return await interaction.response.send_message(
                f"**{row_obra['sigla']}** está pausada.", ephemeral=True
            )

        cap, criado = await self.bot.db.get_or_create_cap(  # type: ignore
            row_obra["id"], capitulo, interaction.user.id
        )
        if cap["status"] == "fechado":
            return await interaction.response.send_message(
                f"Cap. **{cap['numero']}** de `{row_obra['sigla']}` já está fechado. "
                f"Quem tem o cargo de fechar pode usar `/reabrir`.",
                ephemeral=True,
            )

        acao, antiga = await self.bot.db.set_etapa(  # type: ignore
            cap["id"], tipo, interaction.user.id, str(interaction.user)
        )
        etapas = await self.bot.db.get_etapas(cap["id"])  # type: ignore
        completa = await self.bot.db.etapas_completas(cap["id"])  # type: ignore

        extra_bits = []
        if criado:
            extra_bits.append(f"Capítulo **{cap['numero']}** aberto.")
        if acao == "trocada" and antiga and antiga["user_id"] != interaction.user.id:
            extra_bits.append(
                f"`{tipo}` era de <@{antiga['user_id']}> e foi assumido por {interaction.user.mention}."
            )
        else:
            extra_bits.append(
                f"{interaction.user.mention} marcou **{ETAPA_NOMES[tipo]}** (`{tipo}`)."
            )

        fechou = False
        if completa and AUTO_FECHAR:
            await self.bot.db.fechar_cap(cap["id"])  # type: ignore
            cap = dict(cap)
            cap["status"] = "fechado"
            fechou = True
            extra_bits.append("Todas as etapas prontas — capítulo **fechado automaticamente**.")
        elif completa:
            extra_bits.append(
                "Todas as etapas prontas. Quem tem o cargo de fechar pode usar `/fechar`."
            )

        embed = embed_capitulo(
            row_obra["nome"],
            row_obra["sigla"],
            cap["numero"],
            cap["status"],
            etapas,
            extra=" ".join(extra_bits),
        )
        await interaction.response.send_message(embed=embed)

        if fechou:
            await interaction.followup.send(
                f"Cap. **{cap['numero']}** de **{row_obra['sigla']}** finalizado."
            )

    @cap.autocomplete("obra")
    async def cap_obra_ac(self, interaction: discord.Interaction, current: str):
        return await self._obra_autocomplete(interaction, current)

    @cap.autocomplete("etapa")
    async def cap_etapa_ac(self, interaction: discord.Interaction, current: str):
        return await self._etapa_autocomplete(interaction, current)

    @app_commands.command(name="caps", description="Lista capítulos abertos (de uma obra ou de todas)")
    @app_commands.describe(obra="Opcional: filtrar por obra")
    async def caps(self, interaction: discord.Interaction, obra: str | None = None):
        if not interaction.guild:
            return await interaction.response.send_message("Use no servidor.", ephemeral=True)

        if obra:
            row = await self.bot.db.get_obra(interaction.guild.id, obra)  # type: ignore
            if not row:
                return await interaction.response.send_message("Obra não encontrada.", ephemeral=True)
            lista = await self.bot.db.list_caps(row["id"], status="aberto")  # type: ignore
            titulo = f"Caps abertos — {row['sigla']}"
            itens = [(row["sigla"], row["nome"], c) for c in lista]
        else:
            lista = await self.bot.db.list_caps_abertos_guild(interaction.guild.id)  # type: ignore
            titulo = "Capítulos abertos no servidor"
            itens = [(c["obra_sigla"], c["obra_nome"], c) for c in lista]

        if not itens:
            return await interaction.response.send_message(
                "Nenhum capítulo aberto.", ephemeral=True
            )

        progresso = await self.bot.db.progresso_caps([c["id"] for _, _, c in itens])  # type: ignore
        embed = discord.Embed(title=titulo, color=CORES["info"])
        linhas = []
        for sigla, nome, c in itens:
            feitos = progresso.get(c["id"], 0)
            linhas.append(
                f"`{sigla}` cap **{c['numero']}** {barra(feitos)} `{feitos}/{len(ETAPA_ORDEM)}`"
            )
        # Discord field limit
        texto = "\n".join(linhas)
        if len(texto) > 4000:
            texto = "\n".join(linhas[:40]) + f"\n… +{len(linhas) - 40} capítulos"
        embed.description = texto
        await interaction.response.send_message(embed=embed)

    @caps.autocomplete("obra")
    async def caps_obra_ac(self, interaction: discord.Interaction, current: str):
        return await self._obra_autocomplete(interaction, current)

    @app_commands.command(name="vercap", description="Mostra as etapas de um capítulo")
    @app_commands.describe(obra="Sigla ou nome", capitulo="Número do capítulo")
    async def vercap(self, interaction: discord.Interaction, obra: str, capitulo: str):
        if not interaction.guild:
            return await interaction.response.send_message("Use no servidor.", ephemeral=True)
        row = await self.bot.db.get_obra(interaction.guild.id, obra)  # type: ignore
        if not row:
            return await interaction.response.send_message("Obra não encontrada.", ephemeral=True)
        cap = await self.bot.db.get_cap(row["id"], capitulo)  # type: ignore
        if not cap:
            return await interaction.response.send_message(
                f"Cap. `{capitulo}` ainda não existe nessa obra.", ephemeral=True
            )
        etapas = await self.bot.db.get_etapas(cap["id"])  # type: ignore
        embed = embed_capitulo(row["nome"], row["sigla"], cap["numero"], cap["status"], etapas)
        await interaction.response.send_message(embed=embed)

    @vercap.autocomplete("obra")
    async def vercap_obra_ac(self, interaction: discord.Interaction, current: str):
        return await self._obra_autocomplete(interaction, current)

    @app_commands.command(name="fechar", description="Fecha um capítulo manualmente")
    @app_commands.describe(obra="Sigla ou nome", capitulo="Número do capítulo")
    async def fechar(self, interaction: discord.Interaction, obra: str, capitulo: str):
        if not interaction.guild:
            return await interaction.response.send_message("Use no servidor.", ephemeral=True)
        if not pode_fechar(interaction):
            return await interaction.response.send_message(MSG_SEM_FECHAR, ephemeral=True)
        row = await self.bot.db.get_obra(interaction.guild.id, obra)  # type: ignore
        if not row:
            return await interaction.response.send_message("Obra não encontrada.", ephemeral=True)
        cap = await self.bot.db.get_cap(row["id"], capitulo)  # type: ignore
        if not cap:
            return await interaction.response.send_message("Capítulo não encontrado.", ephemeral=True)
        if cap["status"] == "fechado":
            return await interaction.response.send_message(
                "Esse capítulo já está fechado. Use `/reabrir` se quiser voltar.",
                ephemeral=True,
            )

        etapas = await self.bot.db.get_etapas(cap["id"])  # type: ignore

        await self.bot.db.fechar_cap(cap["id"])  # type: ignore
        embed = embed_capitulo(
            row["nome"], row["sigla"], cap["numero"], "fechado", etapas,
            extra=f"Fechado por {interaction.user.mention}.",
        )
        await interaction.response.send_message(embed=embed)

    @fechar.autocomplete("obra")
    async def fechar_obra_ac(self, interaction: discord.Interaction, current: str):
        return await self._obra_autocomplete(interaction, current)

    @app_commands.command(name="reabrir", description="Reabre um capítulo fechado")
    @app_commands.describe(obra="Sigla ou nome", capitulo="Número")
    async def reabrir(self, interaction: discord.Interaction, obra: str, capitulo: str):
        if not interaction.guild:
            return await interaction.response.send_message("Use no servidor.", ephemeral=True)
        if not pode_fechar(interaction):
            return await interaction.response.send_message(MSG_SEM_FECHAR, ephemeral=True)
        row = await self.bot.db.get_obra(interaction.guild.id, obra)  # type: ignore
        if not row:
            return await interaction.response.send_message("Obra não encontrada.", ephemeral=True)
        cap = await self.bot.db.get_cap(row["id"], capitulo)  # type: ignore
        if not cap:
            return await interaction.response.send_message("Capítulo não encontrado.", ephemeral=True)
        await self.bot.db.reabrir_cap(cap["id"])  # type: ignore
        etapas = await self.bot.db.get_etapas(cap["id"])  # type: ignore
        embed = embed_capitulo(
            row["nome"], row["sigla"], cap["numero"], "aberto", etapas,
            extra=f"Reaberto por {interaction.user.mention}.",
        )
        await interaction.response.send_message(embed=embed)

    @reabrir.autocomplete("obra")
    async def reabrir_obra_ac(self, interaction: discord.Interaction, current: str):
        return await self._obra_autocomplete(interaction, current)

    @app_commands.command(name="desfazer", description="Remove uma etapa marcada por engano")
    @app_commands.describe(obra="Sigla ou nome", capitulo="Número", etapa="Etapa a remover")
    async def desfazer(
        self, interaction: discord.Interaction, obra: str, capitulo: str, etapa: str
    ):
        if not interaction.guild:
            return await interaction.response.send_message("Use no servidor.", ephemeral=True)
        tipo = _normaliza_etapa(etapa)
        if not tipo:
            return await interaction.response.send_message("Etapa inválida.", ephemeral=True)
        row = await self.bot.db.get_obra(interaction.guild.id, obra)  # type: ignore
        if not row:
            return await interaction.response.send_message("Obra não encontrada.", ephemeral=True)
        cap = await self.bot.db.get_cap(row["id"], capitulo)  # type: ignore
        if not cap:
            return await interaction.response.send_message("Capítulo não encontrado.", ephemeral=True)
        if cap["status"] == "fechado":
            return await interaction.response.send_message(
                "Capítulo fechado. Use `/reabrir` antes de alterar etapas.",
                ephemeral=True,
            )

        atual = await self.bot.db.get_etapas(cap["id"])  # type: ignore
        if tipo not in atual:
            return await interaction.response.send_message(
                f"`{tipo}` ainda não estava marcado nesse cap.", ephemeral=True
            )
        dono = atual[tipo]["user_id"]
        if dono != interaction.user.id and not pode_fechar(interaction):
            return await interaction.response.send_message(
                "Só quem marcou a etapa (ou o cargo que fecha) pode desfazer.",
                ephemeral=True,
            )

        await self.bot.db.unset_etapa(cap["id"], tipo)  # type: ignore
        etapas = await self.bot.db.get_etapas(cap["id"])  # type: ignore
        embed = embed_capitulo(
            row["nome"], row["sigla"], cap["numero"], cap["status"], etapas,
            extra=f"`{tipo}` removido por {interaction.user.mention}.",
        )
        await interaction.response.send_message(embed=embed)

    @desfazer.autocomplete("obra")
    async def desfazer_obra_ac(self, interaction: discord.Interaction, current: str):
        return await self._obra_autocomplete(interaction, current)

    @desfazer.autocomplete("etapa")
    async def desfazer_etapa_ac(self, interaction: discord.Interaction, current: str):
        return await self._etapa_autocomplete(interaction, current)


async def setup(bot: commands.Bot):
    await bot.add_cog(Capitulos(bot))
