from __future__ import annotations

import re

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
        description="Registra uma etapa em um ou vários capítulos/obras",
    )
    @app_commands.describe(
        obra=(
            "Obra. Para várias: OP:101,102; NAR:5,6. "
            "Para uma: OP"
        ),
        etapa="Etapa que você finalizou: RW, CL, TD, TL, RV, QA, QC",
        capitulo=(
            "Capítulo(s): 101 ou 101,102,103. "
            "Pode ficar vazio ao usar OP:101,102;NAR:5,6"
        ),
    )
    async def cap(
        self,
        interaction: discord.Interaction,
        obra: str,
        etapa: str,
        capitulo: str | None = None,
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

        try:
            pares = self._parse_lote_cap(obra, capitulo)
        except ValueError as exc:
            return await interaction.response.send_message(
                f"Formato inválido: {exc}", ephemeral=True
            )

        if not pares:
            return await interaction.response.send_message(
                "Informe pelo menos um capítulo.", ephemeral=True
            )

        # Evita um comando acidentalmente gigante e mantém a resposta do Discord legível.
        if len(pares) > 50:
            return await interaction.response.send_message(
                "Você pode registrar no máximo 50 capítulos por comando.", ephemeral=True
            )

        resultados: list[tuple[str, str, str]] = []
        fechados: list[str] = []
        erros: list[str] = []

        for obra_query, numeros in pares:
            row_obra = await self.bot.db.get_obra(  # type: ignore
                interaction.guild.id, obra_query
            )
            if not row_obra:
                for numero in numeros:
                    erros.append(f"`{obra_query}` cap. **{numero}**: obra não encontrada")
                continue

            if row_obra["status"] != "ativa":
                for numero in numeros:
                    erros.append(
                        f"`{row_obra['sigla']}` cap. **{numero}**: obra pausada"
                    )
                continue

            for numero in numeros:
                try:
                    cap_row, criado = await self.bot.db.get_or_create_cap(  # type: ignore
                        row_obra["id"], numero, interaction.user.id
                    )
                    if cap_row["status"] == "fechado":
                        erros.append(
                            f"`{row_obra['sigla']}` cap. **{cap_row['numero']}**: já fechado"
                        )
                        continue

                    acao, antiga = await self.bot.db.set_etapa(  # type: ignore
                        cap_row["id"], tipo, interaction.user.id, str(interaction.user)
                    )

                    completa = await self.bot.db.etapas_completas(cap_row["id"])  # type: ignore
                    status = cap_row["status"]

                    if completa and AUTO_FECHAR:
                        await self.bot.db.fechar_cap(cap_row["id"])  # type: ignore
                        status = "fechado"
                        fechados.append(
                            f"{row_obra['sigla']} #{cap_row['numero']}"
                        )

                    if criado:
                        acao_txt = "aberto + etapa marcada"
                    elif acao == "trocada" and antiga and antiga["user_id"] != interaction.user.id:
                        acao_txt = f"etapa assumida de <@{antiga['user_id']}>"
                    else:
                        acao_txt = "etapa marcada"

                    resultados.append(
                        (row_obra["sigla"], str(cap_row["numero"]), acao_txt)
                    )
                except Exception as exc:
                    erros.append(
                        f"`{row_obra['sigla']}` cap. **{numero}**: erro ao registrar ({exc})"
                    )

        linhas: list[str] = []
        if resultados:
            linhas.append(
                f"### {ETAPA_NOMES[tipo]} (`{tipo}`) registrada em {len(resultados)} capítulo(s)"
            )
            # Agrupa visualmente por obra.
            por_obra: dict[str, list[tuple[str, str]]] = {}
            for sigla, numero, acao_txt in resultados:
                por_obra.setdefault(sigla, []).append((numero, acao_txt))
            for sigla, caps in por_obra.items():
                caps_txt = ", ".join(f"**{n}** ({a})" for n, a in caps)
                linhas.append(f"`{sigla}` → {caps_txt}")

        if fechados:
            linhas.append(
                "\n**Fechados automaticamente:** "
                + ", ".join(f"`{x}`" for x in fechados)
            )

        if erros:
            linhas.append(
                "\n**Não registrados:**\n" + "\n".join(f"• {x}" for x in erros)
            )

        if not linhas:
            linhas.append("Nenhum capítulo foi registrado.")

        texto = "\n".join(linhas)
        # Limite confortável para a mensagem do Discord.
        if len(texto) > 4000:
            texto = texto[:3950] + "\n… (resposta truncada)"

        await interaction.response.send_message(texto)

    @staticmethod
    def _parse_lote_cap(obra: str, capitulo: str | None) -> list[tuple[str, list[str]]]:
        """
        Aceita:
          OP + 101
          OP + 101,102,103
          OP,NAR + 101,102       -> aplica cada capítulo a cada obra
          OP:101,102;NAR:5,6     -> obras com capítulos diferentes
          OP:101,102 | NAR:5,6   -> mesma sintaxe usando |
        """
        obra = (obra or "").strip()
        capitulo = (capitulo or "").strip()

        if not obra:
            raise ValueError("informe a obra.")

        # Formato explícito para várias obras com capítulos diferentes.
        if ":" in obra:
            grupos = re.split(r"[;|]+", obra)
            pares: list[tuple[str, list[str]]] = []
            for grupo in grupos:
                grupo = grupo.strip()
                if not grupo:
                    continue
                if ":" not in grupo:
                    raise ValueError(
                        "mistura inválida. Use `OP:101,102;NAR:5,6`."
                    )
                nome, caps_txt = grupo.split(":", 1)
                nome = nome.strip()
                caps = Capitulos._split_caps(caps_txt)
                if not nome or not caps:
                    raise ValueError(
                        "cada grupo deve ser `OBRA:CAP1,CAP2`."
                    )
                pares.append((nome, caps))
            return Capitulos._dedup_pares(pares)

        obras = [x.strip() for x in re.split(r"[,;|]+", obra) if x.strip()]
        caps = Capitulos._split_caps(capitulo)

        if not caps:
            raise ValueError("informe o capítulo, por exemplo `101,102,103`.")

        # Várias obras sem mapeamento explícito: aplica todos os caps a todas as obras.
        return Capitulos._dedup_pares([(o, caps) for o in obras])

    @staticmethod
    def _split_caps(valor: str) -> list[str]:
        return list(dict.fromkeys(
            x.strip() for x in re.split(r"[,\s]+", valor or "") if x.strip()
        ))

    @staticmethod
    def _dedup_pares(pares: list[tuple[str, list[str]]]) -> list[tuple[str, list[str]]]:
        vistos: set[tuple[str, str]] = set()
        saida: list[tuple[str, list[str]]] = []
        for obra, caps in pares:
            novos: list[str] = []
            for cap in caps:
                chave = (obra.casefold(), cap)
                if chave not in vistos:
                    vistos.add(chave)
                    novos.append(cap)
            if novos:
                saida.append((obra, novos))
        return saida

    @cap.autocomplete("obra")
    async def cap_obra_ac(self, interaction: discord.Interaction, current: str):
        # Autocomplete continua útil para uso simples. Em lote, digite a sintaxe manualmente.
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
