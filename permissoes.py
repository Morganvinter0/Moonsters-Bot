from __future__ import annotations

import discord

from config import ROLE_ABRIR_ID, ROLE_FECHAR_ID


def _member(interaction: discord.Interaction) -> discord.Member | None:
    if interaction.guild and isinstance(interaction.user, discord.Member):
        return interaction.user
    return None


def _tem_cargo(member: discord.Member, role_id: int) -> bool:
    return bool(role_id) and any(r.id == role_id for r in member.roles)


def is_admin_servidor(interaction: discord.Interaction) -> bool:
    member = _member(interaction)
    return bool(member and member.guild_permissions.manage_guild)


def pode_abrir(interaction: discord.Interaction) -> bool:
    """Abrir capítulo e marcar etapa: cargo de staff OU cargo que fecha OU gerenciar servidor."""
    member = _member(interaction)
    if not member:
        return False
    if member.guild_permissions.manage_guild:
        return True
    return _tem_cargo(member, ROLE_ABRIR_ID) or _tem_cargo(member, ROLE_FECHAR_ID)


def pode_fechar(interaction: discord.Interaction) -> bool:
    """Fechar ou reabrir capítulo: só o cargo de fechar (ou quem gerencia o servidor)."""
    member = _member(interaction)
    if not member:
        return False
    if member.guild_permissions.manage_guild:
        return True
    return _tem_cargo(member, ROLE_FECHAR_ID)


def pode_gerenciar_obra(interaction: discord.Interaction) -> bool:
    return pode_fechar(interaction)


MSG_SEM_ABRIR = "Você não tem cargo para abrir capítulo ou marcar etapa."
MSG_SEM_FECHAR = "Seu cargo não pode fechar nem reabrir capítulo."
MSG_SEM_OBRA = "Só o cargo de gerência da scan pode cadastrar/alterar obra."
