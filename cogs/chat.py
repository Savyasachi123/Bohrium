import os
import discord
from discord.ext import commands
import google.generativeai as genai

class Chat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        genai.configure(api_key=os.getenv("GEMMA_API_KEY"))
        # Put style/constraints here, not at the end of the transcript
        self.model = genai.GenerativeModel(
            "gemini-2.5-flash-lite",
            system_instruction=(
                "You are a helpful, concise Discord bot. "
                "Keep replies under ~1500 characters. Avoid @-mentioning users."
            ),
        )
        # Keep role-structured messages per channel:
        # contents = [{"role": "user"|"model", "parts": [text]}]
        self.memory = {}  # {channel_id: [content_dict, ...]}

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not self.bot.user or not self.bot.user.mentioned_in(message):
            return

        # Remove literal mention tokens like <@123...>
        prompt = message.content
        for m in message.mentions:
            prompt = prompt.replace(m.mention, "").strip()
        if not prompt:
            await message.channel.send(
                "👋 Hey there! Mention me and say something to start chatting.",
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        cid = message.channel.id
        history = self.memory.setdefault(cid, [])

        # Append just the user's text (optionally include display name *inside* the text)
        history.append({"role": "user", "parts": [f"{message.author.display_name}: {prompt}"]})
        # Keep last 20 turns
        if len(history) > 40:  # (user+model pairs ≈ 20 turns)
            history[:] = history[-40:]

        try:
            # Give Gemini *structured* history
            resp = self.model.generate_content(contents=history)
            reply = (resp.text or "").strip()

            # Append model turn (role **must** be "model")
            history.append({"role": "model", "parts": [reply]})

            await message.channel.send(
                reply,
                allowed_mentions=discord.AllowedMentions.none()
            )
        except Exception as e:
            await message.channel.send(f"⚠️ Error: {e}")
async def setup(bot):
    await bot.add_cog(Chat(bot))
