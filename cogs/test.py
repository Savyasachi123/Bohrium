import discord
from discord.ext import commands

class Test(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="whoisorz")
    async def whoisorz(self, ctx):
        """Reveals the legendary origins of ORZ."""
        message = (
            "Ofc my godfathers **Binny chan** the cute bunny,\n "
            "**Romatt dada** the bilak majic user,\n "
            "and **Aarav saar** the aura farmer."
        )
        await ctx.send(message)

async def setup(bot):
    await bot.add_cog(Test(bot))
