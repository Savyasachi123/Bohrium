import discord
from discord.ext import commands
import asyncio
import random
import subprocess
import sys
import io
import csv

class Problems(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _fetch_competitions_cli_sync(self):
        cmds_to_try = [
            [sys.executable, "-m", "kaggle", "competitions", "list", "--csv"],
            ["kaggle", "competitions", "list", "--csv"]
        ]
        output = None
        for cmd in cmds_to_try:
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=30)
                output = proc.stdout
                break
            except Exception:
                continue

        if not output:
            return []

        comps = []
        try:
            reader = csv.DictReader(io.StringIO(output))
            for row in reader:
                ref = row.get("ref") or row.get("Ref") or row.get("competition")
                title = row.get("title") or row.get("Title") or ref
                url = row.get("url") or (f"{ref}" if ref else None)
                name = row.get("name") or row.get("Name") or ""
                deadline = row.get("deadline") or row.get("Deadline") or ""

                # If no name then get from URL UwU
                if not name and url:
                    slug = url.rstrip("/").split("/")[-1]
                    name = slug.replace("-", " ").title()

                if url:
                    comps.append({
                        "title": title or ref,
                        "url": url,
                        "name": name,
                        "deadline": deadline
                    })
            return comps
        except Exception:
            return []

    async def fetch_competitions_cli(self):
        return await asyncio.to_thread(self._fetch_competitions_cli_sync)

    @commands.command()
    async def problem(self, ctx):
        comps = await self.fetch_competitions_cli()
        if not comps:
            await ctx.send("❌ Could not fetch competitions. Please ping Admin.")
            return

        comp = random.choice(comps)

        embed = discord.Embed(
            title=comp["title"],
            url=comp["url"],
            description=comp["name"] if comp["name"] else "No description available.",
            color=discord.Color.green()
        )

        if comp["deadline"]:
            embed.add_field(name="Competition Deadline", value=comp["deadline"], inline=True)

        embed.set_footer(text="From Kaggle")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Problems(bot))
