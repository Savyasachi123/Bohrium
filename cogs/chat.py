import os
import discord
from discord.ext import commands
from groq import Groq

class Chat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    @commands.command(name="chat")
    async def chat(self, ctx, *, prompt: str):
        """Chat with a Groq model. Usage: ;chat <message>"""
        try:
            response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",   # fast + free option
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300
            )
            reply = response.choices[0].message.content
            await ctx.send(reply)
        except Exception as e:
            await ctx.send(f"⚠️ Error: {e}")

async def setup(bot):
    await bot.add_cog(Chat(bot))
