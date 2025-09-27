import discord
from discord.ext import commands
import asyncio
import subprocess
import csv
import zipfile
import os
import sqlite3

DB_FILE = "data/competition.db"

class CompetitionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_comps = {}
        os.makedirs("data", exist_ok=True)
        os.makedirs("data/leaderboard", exist_ok=True)
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("""
        CREATE TABLE IF NOT EXISTS frozen_scores (
            user_id TEXT,
            comp_type TEXT,
            comp_id TEXT,
            score REAL,
            norm_score REAL,
            PRIMARY KEY (user_id, comp_type, comp_id)
        )""")
        conn.commit()
        conn.close()

    async def fetch_kaggle_score(self, comp_id, discord_id: int):
        """Download leaderboard and return (user_score, max_score) for this Discord user."""
        try:
            exe = r"C:\Users\email\AppData\Roaming\Python\Python313\Scripts\kaggle.exe"

            # Ensure folders
            base_dir = os.path.join("data", "leaderboard")
            latest_dir = os.path.join(base_dir, f"{comp_id}_latest")
            os.makedirs(latest_dir, exist_ok=True)

            # Wipe old files
            for f in os.listdir(latest_dir):
                os.remove(os.path.join(latest_dir, f))

            # Download leaderboard
            subprocess.run(
                [exe, "competitions", "leaderboard", comp_id, "--download", "-p", latest_dir],
                check=True
            )

            # Extract if zip
            for file in os.listdir(latest_dir):
                if file.endswith(".zip"):
                    with zipfile.ZipFile(os.path.join(latest_dir, file), "r") as zip_ref:
                        zip_ref.extractall(latest_dir)
                    os.remove(os.path.join(latest_dir, file))

            # Find CSV
            csv_files = [f for f in os.listdir(latest_dir) if f.endswith(".csv")]
            if not csv_files:
                return 0.0, 1.0

            csv_path = os.path.join(latest_dir, csv_files[0])
            os.rename(csv_path, os.path.join(latest_dir, "latest.csv"))
            csv_path = os.path.join(latest_dir, "latest.csv")

            # 🔑 Get Kaggle ID from kaggle.db
            conn = sqlite3.connect("data/kaggle.db")
            c = conn.cursor()
            c.execute("SELECT kaggle_id FROM kaggle_links WHERE discord_id = ?", (str(discord_id),))
            row = c.fetchone()
            conn.close()
            if not row:
                return 0.0, 1.0
            kaggle_id = row[0].lower()

            # Parse leaderboard
            max_score = 0.0
            user_score = 0.0
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    score = float(row["Score"])
                    max_score = max(max_score, score)
                    if kaggle_id in row["TeamMemberUserNames"].lower():
                        user_score = score
            return user_score, max_score

        except Exception as e:
            print(f"Error fetching score: {e}")
            return 0.0, 1.0

    @commands.group(name="competition", invoke_without_command=True)
    async def competition(self, ctx):
        await ctx.send(
            "Usage:\n"
            "!competition make <weekly/biweekly/monthly> <thread_name> <duration_hours> <problem_links...>\n"
            "!competition join <weekly/biweekly/monthly>\n"
            "!competition leaderboard <weekly/biweekly/monthly>"
        )

    @competition.command(name="make")
    @commands.has_permissions(administrator=True)
    async def make_competition(self, ctx, comp_type: str, thread_name: str, duration_hours: int, *problem_links):
        comp_type = comp_type.lower()
        problems = [link.split("/")[-1] for link in problem_links if "kaggle.com/competitions/" in link]
        if not problems:
            await ctx.send("❌ Provide 1–3 Kaggle competition links.")
            return

        competitions_channel = discord.utils.get(ctx.guild.text_channels, name="competitions")
        comp_thread = await competitions_channel.create_thread(
            name=f"{thread_name}-{comp_type}",
            type=discord.ChannelType.private_thread,
            invitable=False
        )
        discussion_thread = await competitions_channel.create_thread(
            name=f"{thread_name}-{comp_type}-discussion",
            type=discord.ChannelType.private_thread,
            invitable=False
        )
        await discussion_thread.edit(locked=True)

        self.active_comps[comp_type] = {
            "thread_id": comp_thread.id,
            "discussion_id": discussion_thread.id,
            "name": thread_name,
            "duration": duration_hours,
            "problems": problems,
            "participants": {}
        }

        await ctx.send(f"✅ Created {comp_type} competition with {len(problems)} problem(s).")

    @competition.command(name="join")
    async def join_competition(self, ctx, comp_type: str):
        comp_type = comp_type.lower()
        comp = self.active_comps.get(comp_type)
        if not comp:
            await ctx.send("❌ No active competition.")
            return

        comp_thread = ctx.guild.get_thread(comp["thread_id"])
        await comp_thread.add_user(ctx.author)

        baselines = {}
        for comp_id in comp["problems"]:
            score, _ = await self.fetch_kaggle_score(comp_id, ctx.author.id)
            baselines[comp_id] = score

        comp["participants"][ctx.author.id] = {"baseline": baselines, "active": True}
        await ctx.send(f"✅ {ctx.author.display_name} joined {comp['name']}.")

        async def timer_task():
            await asyncio.sleep(comp["duration"] * 60)
            discussion_thread = ctx.guild.get_thread(comp["discussion_id"])
            await comp_thread.remove_user(ctx.author)
            await discussion_thread.edit(locked=False)
            await discussion_thread.add_user(ctx.author)
            await discussion_thread.send(f"⏰ {ctx.author.mention}, your time ended. Scores frozen.")

            # Freeze scores
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            for comp_id in comp["problems"]:
                score, max_score = await self.fetch_kaggle_score(comp_id, ctx.author.id)
                baseline = comp["participants"][ctx.author.id]["baseline"][comp_id]
                norm = (score - baseline) / (max_score - baseline) * 100 if max_score > baseline else 0
                c.execute(
                    "REPLACE INTO frozen_scores VALUES (?, ?, ?, ?, ?)",
                    (ctx.author.id, comp_type, comp_id, score, norm)
                )
            conn.commit()
            conn.close()

            comp["participants"][ctx.author.id]["active"] = False

        self.bot.loop.create_task(timer_task())

    @competition.command(name="leaderboard")
    async def leaderboard(self, ctx, comp_type: str):
        comp = self.active_comps.get(comp_type.lower())
        if not comp:
            await ctx.send("❌ No active competition.")
            return

        rows = []
        for uid, pdata in comp["participants"].items():
            member = ctx.guild.get_member(uid)

            # Lookup Kaggle ID
            conn = sqlite3.connect("data/kaggle.db")
            c = conn.cursor()
            c.execute("SELECT kaggle_id FROM kaggle_links WHERE discord_id=?", (str(uid),))
            row = c.fetchone()
            conn.close()
            kaggle_id = row[0] if row else "?"

            total_norm = 0
            detail = []
            for comp_id in comp["problems"]:
                if pdata["active"]:
                    score, max_score = await self.fetch_kaggle_score(comp_id, uid)
                    baseline = pdata["baseline"][comp_id]
                    norm = (score - baseline) / (max_score - baseline) * 100 if max_score > baseline else 0
                else:
                    conn = sqlite3.connect(DB_FILE)
                    c = conn.cursor()
                    c.execute(
                        "SELECT score, norm_score FROM frozen_scores WHERE user_id=? AND comp_type=? AND comp_id=?",
                        (uid, comp_type, comp_id)
                    )
                    row = c.fetchone()
                    conn.close()
                    score, norm = row if row else (0.0, 0.0)

                total_norm += norm
                detail.append(f"{norm:.1f} ({score:.4f})")

            rows.append((member.display_name, kaggle_id, total_norm, detail))

        rows.sort(key=lambda x: x[2], reverse=True)
        msg = "```\nName         | KaggleID       | NormSum | " + " | ".join([f"P{i+1}" for i in range(len(comp["problems"]))]) + "\n"
        for name, kaggle_id, total, detail in rows:
            msg += f"{name:12} | {kaggle_id:13} | {total:.1f} | {' | '.join(detail)}\n"
        msg += "```"
        await ctx.send(msg)

async def setup(bot):
    await bot.add_cog(CompetitionCog(bot))
