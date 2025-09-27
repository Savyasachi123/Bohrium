import discord
from discord.ext import commands
import sqlite3
import os
import random
import aiohttp
import math

DB_FILE = "data/kaggle.db"

# Ensure data folder exists
if not os.path.exists("data"):
    os.makedirs("data")

# Setup database
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS kaggle_links (
    discord_id TEXT PRIMARY KEY,
    kaggle_id TEXT UNIQUE,
    verified INTEGER DEFAULT 0
)
""")
conn.commit()
conn.close()

class Kaggle(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.verification_codes = {}  # Temporary store {discord_id: code}

    @commands.group(invoke_without_command=True)
    async def kaggle(self, ctx):
        """Link or view Kaggle IDs."""
        await ctx.send("Use `!kaggle identify <username>` to start linking your Kaggle ID.")

    @kaggle.command()
    async def identify(self, ctx, kaggle_id: str):
        """Begin Kaggle account verification process."""
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        # Prevent duplicate Kaggle IDs
        c.execute("SELECT discord_id FROM kaggle_links WHERE kaggle_id = ?", (kaggle_id,))
        row = c.fetchone()
        if row:
            conn.close()
            await ctx.send(f"⚠️ The Kaggle ID `{kaggle_id}` is already linked to another user.")
            return

        # Generate random code
        code = f"SOTA-{random.randint(10000,99999)}"
        self.verification_codes[str(ctx.author.id)] = (kaggle_id, code)

        conn.close()

        await ctx.send(
            f"📝 {ctx.author.mention}, to verify ownership of `{kaggle_id}`:\n"
            f"1. Go to your Kaggle profile.\n"
            f"2. Add this code **{code}** to your bio/about section.\n"
            f"3. Then run `!kaggle verify`."
        )

    @kaggle.command()
    async def verify(self, ctx):
        """Verify your Kaggle account by checking profile bio."""
        discord_id = str(ctx.author.id)
        if discord_id not in self.verification_codes:
            await ctx.send("❌ You don’t have a pending verification. Use `!kaggle identify <username>` first.")
            return

        kaggle_id, code = self.verification_codes[discord_id]

        url = f"https://www.kaggle.com/{kaggle_id}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    await ctx.send(f"⚠️ Could not fetch Kaggle profile for `{kaggle_id}`.")
                    return
                text = await resp.text()

        if code in text:
            # Save verified link
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("""
                INSERT INTO kaggle_links (discord_id, kaggle_id, verified)
                VALUES (?, ?, 1)
                ON CONFLICT(discord_id) DO UPDATE SET kaggle_id=excluded.kaggle_id, verified=1
            """, (discord_id, kaggle_id))
            conn.commit()
            conn.close()

            del self.verification_codes[discord_id]
            await ctx.send(f"✅ {ctx.author.mention}, your Kaggle ID `{kaggle_id}` has been **verified** successfully!")
        else:
            await ctx.send("❌ Verification failed. Make sure you pasted the code in your Kaggle profile bio and try again.")

    @kaggle.command()
    async def get(self, ctx, member: discord.Member = None):
        """Get a member's Kaggle profile details with full stats."""
        if member is None:
            member = ctx.author

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT kaggle_id, verified FROM kaggle_links WHERE discord_id = ?", (str(member.id),))
        row = c.fetchone()
        conn.close()

        if not row:
            await ctx.send(f"❌ No Kaggle ID linked for {member.mention}")
            return

        kaggle_id, verified = row
        status = "✅ Verified" if verified else "⚠️ Unverified"
        profile_url = f"https://www.kaggle.com/{kaggle_id}"

        # Fetch Kaggle profile JSON
        api_url = f"https://www.kaggle.com/{kaggle_id}/json"
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as resp:
                if resp.status != 200:
                    await ctx.send(f"👤 {member.mention} → Kaggle ID: **{kaggle_id}** ({status})\n{profile_url}")
                    return
                data = await resp.json()

        # Extract details
        display_name = data.get("displayName", kaggle_id)
        join_date = data.get("userSince", "Unknown").split("T")[0]
        followers = data.get("followersCount", 0)
        following = data.get("followingCount", 0)
        competitions = data.get("totalCompetitions", 0)
        discussions = data.get("totalDiscussionPosts", 0)
        notebooks = data.get("totalKernels", 0)
        avatar = data.get("avatarUrl", None)
        bio = data.get("aboutMe", "No bio provided.")

        # Map performance tier to labels + embed colors
        tier_map = {
            1: ("⚪ Novice", discord.Color.light_grey()),
            2: ("🟢 Contributor", discord.Color.green()),
            3: ("🟣 Expert", discord.Color.purple()),
            4: ("🟡 Master", discord.Color.gold()),
            5: ("🔴 Grandmaster", discord.Color.red())
        }
        level_text, embed_color = tier_map.get(
            data.get("performanceTier", 0), 
            ("❓ Unknown", discord.Color.dark_grey())
        )

        # Build embed
        embed = discord.Embed(
            title=f"{display_name} ({kaggle_id})",
            url=profile_url,
            description=f"{status} Kaggle Profile\n\n*{bio}*",
            color=embed_color
        )
        embed.add_field(name="Level", value=level_text, inline=True)
        embed.add_field(name="Joined", value=join_date, inline=True)
        embed.add_field(name="Followers", value=followers, inline=True)
        embed.add_field(name="Following", value=following, inline=True)
        embed.add_field(name="Competitions", value=competitions, inline=True)
        embed.add_field(name="Notebooks", value=notebooks, inline=True)
        embed.add_field(name="Discussions", value=discussions, inline=True)

        if avatar:
            embed.set_thumbnail(url=avatar)

        embed.set_footer(text=f"Requested by {ctx.author.display_name}")

        await ctx.send(embed=embed)


    @kaggle.command()
    @commands.has_permissions(manage_guild=True)
    async def unlink(self, ctx, member: discord.Member):
        """Unlink someone’s Kaggle ID (Admin only)."""
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("DELETE FROM kaggle_links WHERE discord_id = ?", (str(member.id),))
        conn.commit()
        changes = conn.total_changes
        conn.close()

        if changes > 0:
            await ctx.send(f"🗑️ Kaggle ID unlinked for {member.mention}")
        else:
            await ctx.send(f"❌ {member.mention} has no Kaggle ID linked.")

    @kaggle.command()
    async def list(self, ctx):
        """List all linked Kaggle IDs in the server (20 per page)."""
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT discord_id, kaggle_id, verified FROM kaggle_links")
        rows = c.fetchall()
        conn.close()

        if not rows:
            await ctx.send("❌ No Kaggle IDs linked yet.")
            return

        # Sort alphabetically by Discord name (if available)
        rows.sort(key=lambda r: (ctx.guild.get_member(int(r[0])).display_name 
                                 if ctx.guild.get_member(int(r[0])) else str(r[0])))

        # Pagination
        per_page = 20
        pages = math.ceil(len(rows) / per_page)

        def make_page(page_index):
            start = page_index * per_page
            end = start + per_page
            subset = rows[start:end]

            lines = []
            for discord_id, kaggle_id, verified in subset:
                member = ctx.guild.get_member(int(discord_id))
                name = member.display_name if member else f"Unknown({discord_id})"
                check = "✅" if verified else "⚠️"
                lines.append(f"{name:<20} | {kaggle_id:<20} {check}")

            header = f"{'Discord Name':<20} | {'Kaggle ID':<20} Status"
            content = "\n".join([header, "-"*50] + lines)
            return f"```{content}```\nPage {page_index+1}/{pages}"

        # Send first page
        current_page = 0
        message = await ctx.send(make_page(current_page))

        # Add reactions for navigation if multiple pages
        if pages > 1:
            await message.add_reaction("◀")
            await message.add_reaction("▶")

            def check(reaction, user):
                return user == ctx.author and str(reaction.emoji) in ["◀", "▶"] and reaction.message.id == message.id

            while True:
                try:
                    reaction, user = await self.bot.wait_for("reaction_add", timeout=60.0, check=check)
                    if str(reaction.emoji) == "▶" and current_page < pages - 1:
                        current_page += 1
                        await message.edit(content=make_page(current_page))
                    elif str(reaction.emoji) == "◀" and current_page > 0:
                        current_page -= 1
                        await message.edit(content=make_page(current_page))

                    await message.remove_reaction(reaction, user)
                except Exception:
                    break

async def setup(bot):
    await bot.add_cog(Kaggle(bot))

