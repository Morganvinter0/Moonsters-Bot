from __future__ import annotations

import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from config import GUILD_ID, STAFF_ROLE_ID, TOKEN
from database import Database

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("scan-bot")


class ScanBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True
        super().__init__(command_prefix="!", intents=intents)
        self.db = Database()
        self.config_staff_role = STAFF_ROLE_ID

    async def setup_hook(self) -> None:
        await self.db.connect()
        for cog in ("cogs.obras", "cogs.capitulos", "cogs.ranking", "cogs.painel"):
            await self.load_extension(cog)
            log.info("Cog carregado: %s", cog)

        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info("Comandos sincronizados no servidor %s: %s", GUILD_ID, len(synced))
        else:
            synced = await self.tree.sync()
            log.info("Comandos sincronizados globalmente: %s", len(synced))

    async def on_ready(self) -> None:
        log.info("Logado como %s (%s)", self.user, self.user.id if self.user else "?")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="obras e capítulos · /ajuda",
            )
        )

    async def close(self) -> None:
        await self.db.close()
        await super().close()


def main() -> None:
    token = TOKEN or os.getenv("DISCORD_TOKEN", "")
    if not token or token == "cole_o_token_do_bot_aqui":
        raise SystemExit(
            "Defina DISCORD_TOKEN no arquivo .env (copie de .env.example)."
        )
    bot = ScanBot()
    bot.run(token)


if __name__ == "__main__":
    main()
