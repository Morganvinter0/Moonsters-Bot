from __future__ import annotations
from datetime import datetime, timedelta, timezone
import discord
from discord import app_commands
from discord.ext import commands
from config import CORES, ETAPA_NOMES, ETAPA_ORDEM
from permissoes import is_admin_servidor


def since_days(days=7):
    return (datetime.now(timezone.utc)-timedelta(days=days)).isoformat(timespec="seconds")

class Painel(commands.Cog):
    def __init__(self, bot): self.bot=bot

    @app_commands.command(name="dashboard", description="Painel geral da scan")
    async def dashboard(self, interaction: discord.Interaction):
        if not interaction.guild: return await interaction.response.send_message("Use no servidor.", ephemeral=True)
        s=await self.bot.db.dashboard_stats(interaction.guild.id); week=await self.bot.db.etapas_periodo(interaction.guild.id,since_days(7))
        embed=discord.Embed(title="📊 Dashboard da Scan", color=CORES["info"])
        embed.add_field(name="Obras",value=str(s["obras"] or 0),inline=True); embed.add_field(name="Capítulos",value=str(s["total_caps"] or 0),inline=True); embed.add_field(name="Abertos",value=str(s["abertos"] or 0),inline=True)
        embed.add_field(name="Fechados",value=str(s["fechados"] or 0),inline=True); embed.add_field(name="Etapas · 7 dias",value=str(week),inline=True)
        rows=await self.bot.db.ranking(interaction.guild.id,since=since_days(7),limit=5)
        embed.add_field(name="Top da semana",value="\n".join(f"{i}. <@{r['user_id']}> — {r['total']}" for i,r in enumerate(rows,1)) or "Nenhuma atividade.",inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="dashboard_equipe", description="Painel de uma equipe")
    @app_commands.describe(equipe="Nome da equipe")
    async def dashboard_equipe(self, interaction: discord.Interaction, equipe: str):
        if not interaction.guild: return await interaction.response.send_message("Use no servidor.",ephemeral=True)
        eq=await self.bot.db.get_equipe(interaction.guild.id,equipe)
        if not eq: return await interaction.response.send_message("Equipe não encontrada. Use `/registrar_equipe`.",ephemeral=True)
        membros=await self.bot.db.membros_equipe(eq["id"]); rows=await self.bot.db.stats_equipe(eq["id"]); week=await self.bot.db.stats_equipe(eq["id"],since_days(7))
        total=sum(r["total"] for r in rows); wt=sum(r["total"] for r in week)
        embed=discord.Embed(title=f"👥 Equipe — {eq['nome']}",color=CORES["obra"])
        embed.add_field(name="Membros",value=str(len(membros)),inline=True); embed.add_field(name="Etapas",value=str(total),inline=True); embed.add_field(name="Esta semana",value=str(wt),inline=True)
        embed.add_field(name="Produção",value="\n".join(f"<@{r['user_id']}> — **{r['total']}**" for r in rows[:15]) or "Sem produção.",inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="registrar_equipe", description="Cria uma equipe e opcionalmente adiciona um membro")
    @app_commands.describe(nome="Nome da equipe", membro="Membro inicial opcional")
    async def registrar_equipe(self, interaction: discord.Interaction, nome: str, membro: discord.Member|None=None):
        if not interaction.guild: return await interaction.response.send_message("Use no servidor.",ephemeral=True)
        if not is_admin_servidor(interaction): return await interaction.response.send_message("Só administradores podem registrar equipes.",ephemeral=True)
        if await self.bot.db.get_equipe(interaction.guild.id,nome): return await interaction.response.send_message("Essa equipe já existe.",ephemeral=True)
        eq=await self.bot.db.add_equipe(interaction.guild.id,nome,interaction.user.id)
        if membro: await self.bot.db.add_membro_equipe(eq["id"],membro.id,str(membro))
        await interaction.response.send_message(f"✅ Equipe **{nome}** registrada." + (f" Membro: {membro.mention}" if membro else ""))

    @app_commands.command(name="perfil", description="Mostra o perfil de produção de um membro")
    @app_commands.describe(membro="Membro; se vazio, você")
    async def perfil(self, interaction: discord.Interaction, membro: discord.Member|None=None):
        if not interaction.guild: return await interaction.response.send_message("Use no servidor.",ephemeral=True)
        alvo=membro or interaction.user; s=await self.bot.db.user_stats(interaction.guild.id,alvo.id); et=await self.bot.db.user_etapas(interaction.guild.id,alvo.id)
        rank=await self.bot.db.ranking(interaction.guild.id,limit=1000); pos=next((i for i,r in enumerate(rank,1) if r["user_id"]==alvo.id),None)
        embed=discord.Embed(title=f"👤 Perfil — {alvo.display_name}",color=CORES["info"]); embed.set_thumbnail(url=alvo.display_avatar.url)
        embed.add_field(name="Etapas",value=str(s["total"] or 0),inline=True); embed.add_field(name="Capítulos",value=str(s["capitulos"] or 0),inline=True); embed.add_field(name="Obras",value=str(s["obras"] or 0),inline=True); embed.add_field(name="Ranking",value=f"#{pos}" if pos else "Sem ranking",inline=True)
        embed.add_field(name="Por etapa",value="\n".join(f"`{r['tipo']}` {ETAPA_NOMES.get(r['tipo'],r['tipo'])}: **{r['total']}**" for r in et) or "Nenhuma etapa registrada.",inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="rank", description="Ranking geral dos membros")
    async def rank(self, interaction: discord.Interaction):
        if not interaction.guild: return await interaction.response.send_message("Use no servidor.",ephemeral=True)
        rows=await self.bot.db.ranking(interaction.guild.id,limit=20); embed=discord.Embed(title="🏆 Ranking geral",color=CORES["ok"])
        embed.description="\n".join(f"**{i}.** <@{r['user_id']}> — **{r['total']}** etapas" for i,r in enumerate(rows,1)) or "Nenhuma atividade."
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="semanal", description="Produção dos últimos 7 dias")
    async def semanal(self, interaction: discord.Interaction):
        await self._semanal(interaction)

    @app_commands.command(name="smanal", description="Atalho para o relatório semanal")
    async def smanal(self, interaction: discord.Interaction):
        await self._semanal(interaction)

    async def _semanal(self, interaction):
        if not interaction.guild: return await interaction.response.send_message("Use no servidor.",ephemeral=True)
        rows=await self.bot.db.ranking(interaction.guild.id,since=since_days(7),limit=20); total=await self.bot.db.etapas_periodo(interaction.guild.id,since_days(7))
        embed=discord.Embed(title="📅 Produção semanal",description=f"Total nos últimos 7 dias: **{total}** etapas",color=CORES["info"])
        embed.add_field(name="Produção por membro",value="\n".join(f"**{i}.** <@{r['user_id']}> — **{r['total']}**" for i,r in enumerate(rows,1)) or "Nenhuma atividade.",inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="top_etapa", description="Top de cada etapa")
    async def top_etapa(self, interaction: discord.Interaction):
        if not interaction.guild: return await interaction.response.send_message("Use no servidor.",ephemeral=True)
        embed=discord.Embed(title="📈 Top por etapa",color=CORES["obra"])
        for sigla in ETAPA_ORDEM:
            rows=await self.bot.db.ranking_por_etapa(interaction.guild.id,sigla,limit=3)
            val="\n".join(f"{i}. <@{r['user_id']}> — {r['total']}" for i,r in enumerate(rows,1)) or "—"
            embed.add_field(name=f"{sigla} · {ETAPA_NOMES[sigla]}",value=val,inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="medalhas", description="Mostra as medalhas conquistadas")
    @app_commands.describe(membro="Membro; se vazio, você")
    async def medalhas(self, interaction: discord.Interaction, membro: discord.Member|None=None):
        if not interaction.guild: return await interaction.response.send_message("Use no servidor.",ephemeral=True)
        alvo=membro or interaction.user; s=await self.bot.db.user_stats(interaction.guild.id,alvo.id); n=s["total"] or 0; c=s["capitulos"] or 0
        medals=[]
        for threshold,emoji,name in [(1,"🥉","Primeira etapa"),(25,"🥈","25 etapas"),(50,"🥇","50 etapas"),(100,"💎","100 etapas"),(250,"👑","250 etapas"),(500,"🔥","500 etapas"),(10,"📚","10 capítulos"),(50,"📖","50 capítulos")]:
            if n>=threshold if name.endswith("etapas") else c>=threshold: medals.append(f"{emoji} **{name}**")
        embed=discord.Embed(title=f"🏅 Medalhas — {alvo.display_name}",color=CORES["aviso"]); embed.description="\n".join(medals) or "Nenhuma medalha ainda. Continue produzindo!"
        embed.set_footer(text=f"{n} etapas · {c} capítulos")
        await interaction.response.send_message(embed=embed)

async def setup(bot): await bot.add_cog(Painel(bot))
