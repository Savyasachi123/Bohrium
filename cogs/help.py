import discord
from discord.ext import commands

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.remove_command("help")

    @commands.command()
    async def help(self, ctx):
        """Show all commands grouped by cog"""
        help_text = ""

        for cog_name, cog in self.bot.cogs.items():
            help_text += f"{cog_name}:\n"
            for command in cog.get_commands():
                if not command.hidden:
                    if isinstance(command, commands.Group):  
                        # Show group command
                        help_text += f"  {command.name} - {command.help}\n"
                        # Show its subcommands
                        for sub in command.commands:
                            help_text += f"    {sub.name} - {sub.help}\n"
                    else:
                        help_text += f"  {command.name} - {command.help}\n"
            help_text += "\n"

        if not help_text:
            help_text = "No commands available."

        await ctx.send(f"```{help_text}```")

async def setup(bot):
    await bot.add_cog(HelpCog(bot))
