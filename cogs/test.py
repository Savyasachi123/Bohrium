import discord
from discord.ext import commands

class Test(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def hello(self, ctx):
        """Test command that says hello."""
        await ctx.send(f"Hello {ctx.author.mention}, the bot is working! 🎉")

async def setup(bot):
    await bot.add_cog(Test(bot))
