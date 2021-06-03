#!/usr/bin/python
import iohandler
import re
import discord
import discord_slash
import asyncio
import datetime

from discord.ext import commands, tasks
from discord_slash import SlashCommand, cog_ext
from discord_slash.utils import manage_commands

log = iohandler.Logger()
config = iohandler.Config(log)
data = iohandler.Data(log)
driver = iohandler.Driver(log, config)

class Rooster(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot


if __name__ == "__main__":
    bot = commands.Bot(command_prefix=",")
    slash = SlashCommand(bot, sync_commands=True)
    bot.add_cog(Rooster(bot))

    @bot.event
    async def on_ready():
        log.info(f"Logged in as {bot.user}")
    bot.run(config.token)
