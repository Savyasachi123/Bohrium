import discord
from discord.ext import commands
import os
import random
from kaggle import api  # Official Kaggle API client

class GitGud(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.kaggle_username = os.getenv("KAGGLE_USERNAME")
        self.kaggle_key = os.getenv("KAGGLE_KEY")

    @commands.command(name="gitgud")
    async def gitgud(self, ctx, *filters):
        """
        Fetch a random Kaggle competition with optional filters.

        Usage:
          ;gitgud
          ;gitgud category=featured
          ;gitgud tag=nlp
          ;gitgud category=playground tag=vision
        """

        if not self.kaggle_username or not self.kaggle_key:
            await ctx.send("❌ Kaggle API credentials not configured properly.")
            return

        try:
            # --- Parse filters ---
            params = {}
            tags = []
            for f in filters:
                if "=" in f:
                    key, value = f.split("=", 1)
                    key = key.lower().strip()
                    value = value.lower().strip()
                    if key == "category":
                        params["category"] = value
                    elif key == "tag":
                        tags.append(value)

            # --- Fetch competitions ---
            competitions = api.competitions_list(**params)

            # --- Manual tag filter (title/description) ---
            if tags:
                competitions = [
                    c for c in competitions
                    if any(
                        t in (c.title.lower() + (c.description or "").lower())
                        for t in tags
                    )
                ]

            if not competitions:
                await ctx.send("⚠️ No competitions found for those filters.")
                return

            # --- Pick one ---
            comp = random.choice(competitions)

            # --- Build URL ---
            url = f"https://www.kaggle.com/competitions/{comp.ref}"

            # --- Create embed ---
            embed = discord.Embed(
                title=comp.title,
                url=url,
                description=(comp.description or "No description available."),
                color=discord.Color.blue()
            )

            embed.add_field(name="Category", value=getattr(comp, "category", "N/A") or "N/A", inline=True)
            embed.add_field(name="Reward", value=getattr(comp, "reward", "N/A") or "N/A", inline=True)
            embed.add_field(name="Deadline", value=getattr(comp, "deadline", "N/A") or "N/A", inline=False)
            embed.add_field(name="Organization", value=getattr(comp, "organization_name", "N/A") or "N/A", inline=False)
            embed.set_footer(text="Fetched from Kaggle")

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"⚠️ Something went wrong: `{type(e).__name__}: {e}`")

async def setup(bot):
    await bot.add_cog(GitGud(bot))
