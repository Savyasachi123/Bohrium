import os
import sys
import discord
from discord.ext import commands
import subprocess
import json
import aiohttp

class GitGud(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.groq_endpoint = "https://api.groq.com/openai/v1/chat/completions"

    @commands.command(name="gitgud_detail")
    async def gitgud_detail(self, ctx, competition_id: str):
        """
        Fetch Kaggle competition details using Kaggle CLI (via -m) and summarize with Groq.
        Works even if kaggle.exe is not in PATH.
        """
        try:
            result = subprocess.run(
                [sys.executable, "-m", "kaggle", "competitions", "view", competition_id, "--json"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            comp_data = json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            await ctx.send(f"⚠️ Kaggle CLI error: {e.stderr}")
            return
        except Exception as e:
            await ctx.send(f"⚠️ Error: {e}")
            return

        title = comp_data.get("title", competition_id)
        description = comp_data.get("description", "No description available.")
        reward = comp_data.get("reward", "Unknown")
        deadline = comp_data.get("deadline", "Unknown")
        evaluation = comp_data.get("evaluationMetric", "Not specified")

        preview = (description[:1000] + "…") if len(description) > 1000 else description
        embed = discord.Embed(
            title=f"📄 Kaggle Competition: {title}",
            description=preview,
            url=f"https://www.kaggle.com/competitions/{competition_id}",
            color=discord.Color.dark_grey()
        )
        embed.add_field(name="Reward", value=reward, inline=True)
        embed.add_field(name="Deadline", value=deadline, inline=True)
        embed.add_field(name="Evaluation", value=evaluation, inline=True)
        await ctx.send(embed=embed)

        # --- Summarize with Groq ---
        headers = {"Authorization": f"Bearer {self.groq_api_key}", "Content-Type": "application/json"}
        body = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": "Summarize Kaggle competitions into: Overview, Objective, Data, Evaluation, and Notes."},
                {"role": "user", "content": description}
            ],
            "max_completion_tokens": 500,
            "temperature": 0.5
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(self.groq_endpoint, headers=headers, json=body) as resp:
                if resp.status != 200:
                    await ctx.send(f"⚠️ Groq API error {resp.status}")
                    return
                data = await resp.json()
                summary = data["choices"][0]["message"]["content"]

        embed = discord.Embed(
            title=f"📝 Summarized: {title}",
            description=summary,
            url=f"https://www.kaggle.com/competitions/{competition_id}",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(GitGud(bot))
