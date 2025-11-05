import discord
from discord.ext import commands
import asyncio
import subprocess
import csv
import zipfile
import os
import sqlite3
import json
import time

DB_FILE = "data/competition.db"


class CompetitionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_comps = {}
        os.makedirs("data", exist_ok=True)
        os.makedirs("data/leaderboard", exist_ok=True)
        os.makedirs("data/competitions_jsons", exist_ok=True)
        self.init_db()
        self.bot.loop.create_task(self._recover_after_ready())


    # ------------------ DB Setup ------------------
    def init_db(self):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        # Store frozen scores
        c.execute("""
        CREATE TABLE IF NOT EXISTS frozen_scores (
            user_id TEXT,
            comp_type TEXT,
            comp_id TEXT,
            score REAL,
            norm_score REAL,
            PRIMARY KEY (user_id, comp_type, comp_id)
        )""")

        # Store active participants
        c.execute("""
        CREATE TABLE IF NOT EXISTS participants (
            user_id TEXT,
            comp_type TEXT,
            comp_id TEXT,
            baseline REAL,
            active INTEGER,
            joined_at REAL,
            PRIMARY KEY (user_id, comp_type, comp_id)
        )""")

        conn.commit()
        conn.close()

    async def load_active_comps(self):
        """Load existing competitions from JSON files into memory on startup and restore timers."""
        folder = "data/competitions_jsons"
        os.makedirs(folder, exist_ok=True)

        # We assume we're running after wait_until_ready(), so guilds are available.
        guilds = list(self.bot.guilds)
        if not guilds:
            print("⚠️ No guilds found; skipping timer recovery for now.")
            return
        guild = guilds[0]  # pick your primary guild, or locate by ID if you prefer

        for file in os.listdir(folder):
            if not file.endswith(".json"):
                continue
            try:
                with open(os.path.join(folder, file), "r", encoding="utf-8") as f:
                    data = json.load(f)
                comp_type = data["type"]
                self.active_comps[comp_type] = {
                    "thread_id": data["thread_id"],
                    "discussion_id": data.get("discussion_id"),
                    "name": data["name"],
                    "duration": data["duration"],
                    "direction": data["direction"],
                    "baseline": data["baseline"],
                    "problems": data["problems"],
                    "participants": {},
                    "lock": asyncio.Lock()
                }
                print(f"🔁 Restored competition '{comp_type}' from {file}")
            except Exception as e:
                print(f"⚠️ Failed to load competition from {file}: {e}")
                continue

            # Restore participants (MERGE baselines for multi-problem comps)
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("""
                SELECT user_id, comp_id, baseline, active, joined_at
                FROM participants
                WHERE comp_type=?
            """, (comp_type,))
            rows = c.fetchall()
            conn.close()

            for user_id, comp_id, baseline, active, joined_at in rows:
                p = self.active_comps[comp_type]["participants"].setdefault(
                    user_id,
                    {"baseline": {}, "active": bool(active), "joined_at": joined_at}
                )
                # Merge multiple comp_id baselines
                p["baseline"][comp_id] = baseline
                # Keep the most recent joined_at and any active truthy
                p["active"] = bool(active) or p.get("active", False)
                if not p.get("joined_at") or (joined_at and joined_at > p["joined_at"]):
                    p["joined_at"] = joined_at

            print(f"✅ Restored {len(rows)} participant row(s) for {comp_type}")

            # Re-schedule or finalize timers
            now = time.time()
            duration_sec = self.active_comps[comp_type]["duration"] * 60

            for user_id, pdata in self.active_comps[comp_type]["participants"].items():
                if not pdata.get("active"):
                    continue
                joined_at = pdata.get("joined_at") or now  # fallback
                remaining = duration_sec - (now - joined_at)

                if remaining <= 0:
                    # Timer expired while offline → freeze immediately
                    asyncio.create_task(self.freeze_participant(guild, comp_type, user_id))
                    print(f"🧊 Auto-froze expired participant {user_id} in {comp_type}")
                else:
                    # Still time left → reschedule
                    async def resume_timer(uid=user_id, delay=remaining, ctype=comp_type, g=guild):
                        await asyncio.sleep(delay)
                        await self.freeze_participant(g, ctype, uid)
                    asyncio.create_task(resume_timer())
                    print(f"⏳ Rescheduled timer for {user_id} in {comp_type}, {remaining/60:.1f}m left")


    def save_participant(self, user_id: str, comp_type: str, comp_id: str, baseline: float, active: bool):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        joined_at = time.time()  # seconds since loop start, fine for relative timers
        c.execute("""
            INSERT INTO participants (user_id, comp_type, comp_id, baseline, active, joined_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, comp_type, comp_id)
            DO UPDATE SET baseline=excluded.baseline, active=excluded.active, joined_at=excluded.joined_at
        """, (user_id, comp_type, comp_id, baseline, 1 if active else 0, joined_at))
        conn.commit()
        conn.close()

    def remove_participant(self, user_id: str, comp_type: str):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("DELETE FROM participants WHERE user_id=? AND comp_type=?", (user_id, comp_type))
        conn.commit()
        conn.close()

    # ------------------ Helpers ------------------
    def _compute_norm(self, direction: str, baseline: float, score: float, min_score: float, max_score: float) -> float:
        """
        Returns a 0..100 normalized improvement from baseline toward the 'best' extreme, respecting direction.
        - 'higher': improvement is (score - baseline) over (max - baseline)
        - 'lower' : improvement is (baseline - score) over (baseline - min)
        Clamped to [0, 100] and robust to zero/negative denominators.
        """
        EPS = 1e-12
        if direction == "higher":
            denom = max(max_score - baseline, EPS)
            value = (score - baseline) / denom * 100.0
        else:
            denom = max(baseline - min_score, EPS)
            value = (baseline - score) / denom * 100.0
        if value < 0:
            return 0.0
        if value > 100:
            return 100.0
        return value

    # ------------------ Kaggle Fetch ------------------
    async def _recover_after_ready(self):
        await asyncio.sleep(5)
        await self.load_active_comps()  # now guilds/threads are available

    async def fetch_kaggle_score(self, comp_id, discord_id: int):
        """
        Download leaderboard and return (user_score, min_score, max_score) for this Discord user.
        """
        base_dir = os.path.join("data", "leaderboard")
        latest_dir = os.path.join(base_dir, f"{comp_id}_latest")
        os.makedirs(latest_dir, exist_ok=True)

        # 1) Clear old files
        for f in os.listdir(latest_dir):
            try:
                os.remove(os.path.join(latest_dir, f))
            except Exception:
                pass

        # 2) Download leaderboard via Kaggle CLI
        try:
            print(f"📥 Downloading leaderboard for {comp_id}...")
            subprocess.run(
                ["kaggle", "competitions", "leaderboard", comp_id, "--download", "-p", latest_dir],
                check=True,
                capture_output=True,
                text=True
            )
        except subprocess.CalledProcessError as e:
            print(f"❌ Kaggle CLI failed: {e.stderr or e.stdout}")
            # Return a safe tuple: (user, min, max)
            return 0.0, 0.0, 1.0

        # 3) Extract the zip
        zip_files = [f for f in os.listdir(latest_dir) if f.endswith(".zip")]
        if not zip_files:
            print(f"❌ No zip file found for {comp_id}")
            return 0.0, 0.0, 1.0

        for zf in zip_files:
            zip_path = os.path.join(latest_dir, zf)
            try:
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    zip_ref.extractall(latest_dir)
                print(f"✅ Extracted {zf}")
            except Exception as e:
                print(f"❌ Failed to extract {zf}: {e}")

        # 4) Find CSV
        csv_files = [f for f in os.listdir(latest_dir) if f.endswith(".csv")]
        if not csv_files:
            print(f"❌ No CSV found after extraction in {latest_dir}")
            return 0.0, 0.0, 1.0

        csv_path = os.path.join(latest_dir, csv_files[0])
        print(f"📄 Found leaderboard CSV: {csv_path}")

        # 5) Get Kaggle ID
        conn = sqlite3.connect("data/kaggle.db")
        c = conn.cursor()
        c.execute("SELECT kaggle_id FROM kaggle_links WHERE discord_id = ?", (str(discord_id),))
        row = c.fetchone()
        conn.close()

        if not row:
            print(f"⚠️ No Kaggle ID linked for Discord user {discord_id}")
            return 0.0, 0.0, 1.0
        kaggle_id = (row[0] or "").strip().lower()

        # 6) Parse leaderboard → user_score, min_score, max_score
        user_score = 0.0
        min_score = float("inf")
        max_score = float("-inf")

        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    # Normalize columns to lowercase
                    cols = { (k or "").strip().lower(): (v or "").strip() for k, v in r.items() }

                    # Score
                    score_raw = cols.get("score", "")
                    try:
                        score = float(score_raw)
                    except Exception:
                        continue

                    # Track min/max
                    if score < min_score:
                        min_score = score
                    if score > max_score:
                        max_score = score

                    # team/user columns (Kaggle CSV can vary)
                    members_field = (
                        cols.get("teammemberusernames")
                        or cols.get("team member usernames")
                        or cols.get("username")
                        or ""
                    )
                    team_name = cols.get("teamname", "")

                    members = [m.strip().lower() for m in members_field.split(",") if m.strip()]
                    if kaggle_id in members or kaggle_id == team_name.lower():
                        user_score = score

            # Fallbacks if CSV was weird/empty
            if min_score == float("inf"):
                min_score = user_score
            if max_score == float("-inf"):
                max_score = user_score

            print(f"✅ {kaggle_id} score={user_score}, min={min_score}, max={max_score}")
            return user_score, min_score, max_score
        except Exception as e:
            print(f"❌ Failed to parse leaderboard CSV: {e}")
            return 0.0, 0.0, 1.0

    # ------------------ Commands ------------------
    @commands.group(name="comp", invoke_without_command=True)
    async def competition(self, ctx):
        await ctx.send(
            "Usage:\n"
            ";competition join <weekly/biweekly/monthly>\n"
            ";competition leaderboard <weekly/biweekly/monthly>\n"
            "Only ADMIN commands:\n"
            ";competition kick <type> <member>\n"
            ";competition forcejoin <type> <member>"
            ";competition make <weekly/biweekly/monthly> <thread_name> <duration_minutes> <direction> <baseline> <problem_links>\n"
        )

    # ----- Make -----
    @competition.command(name="make")
    @commands.has_permissions(administrator=True)
    async def make_competition(self, ctx, comp_type: str, thread_name: str, duration_minutes: int,
                               direction: str, baseline: float, *problem_links):
        """
        Creates a new competition of given type with full metadata.
        Usage:
        ;competition make <type> <thread_name> <duration_minutes> <direction> <baseline> <problem_links...>
        Example:
        ;competition make weekly AI_Weekly 120 higher 0.75 https://www.kaggle.com/competitions/titanic
        """
        comp_type = comp_type.lower()
        direction = direction.lower()
        if direction not in ["higher", "lower"]:
            await ctx.send("❌ Direction must be 'higher' or 'lower'.")
            return

        try:
            baseline = float(baseline)
        except ValueError:
            await ctx.send("❌ Baseline must be a number.")
            return

        problems = [link.split("/competitions/")[-1].split("/")[0]
                    for link in problem_links if "kaggle.com/competitions/" in link]
        if not problems:
            await ctx.send("❌ Provide at least one valid Kaggle competition link.")
            return

        competitions_channel = discord.utils.get(ctx.guild.text_channels, name="competitions")
        if competitions_channel is None:
            await ctx.send("❌ No #competitions channel found.")
            return

        # Create MAIN read-only thread
        try:
            comp_thread = await competitions_channel.create_thread(
                name=f"{thread_name}-{comp_type}",
                type=discord.ChannelType.private_thread,
                invitable=False
            )
            await comp_thread.edit(locked=True, archived=False)

            arrow = "↑" if direction == "higher" else "↓"
            await comp_thread.send(
                f"📢 **Competition `{comp_type}` created!**\n"
                f"Problems: {', '.join(problems)}\n"
                f"Duration: {duration_minutes} minutes\n"
                f"Direction of score: `{direction}` {arrow}\n"
                f"Baseline: `{baseline}`\n\n"
                f"This is a read-only thread for announcements. "
                f"Only admins and the bot can post here."
                f"\n Good luck everyone! May the best man win!"
                f"\n\n And remember everyone, no matter how skilled you are, you can still lose. A large part of AI is governed by randomness. And it might be that a simpler approach works better than your sophisticated approach because the data prefers that. Ultimately, what you gain from this competition is knowledge about the different ways of solving a single problem and an experience of what to use and when to use something. Lets not hold hard feelings for we all are working together towards becoming better versions of ourselves."
            )

        except Exception as e:
            await ctx.send(f"❌ Failed to create competition thread: {e}")
            return

        # Create DISCUSSION thread (locked initially)
        try:
            discussion_thread = await competitions_channel.create_thread(
                name=f"{thread_name}-{comp_type}-discussion",
                type=discord.ChannelType.private_thread,
                invitable=False
            )
            await discussion_thread.edit(locked=True)
            await discussion_thread.send(
                "💬 This thread will unlock automatically for you once your timer ends. "
                "Use it to discuss approaches with other frozen participants. Hope you had a fun time!"
            )
        except Exception as e:
            await ctx.send(f"⚠️ Discussion thread creation failed: {e}")
            discussion_thread = None

        # Register in memory
        self.active_comps[comp_type] = {
            "thread_id": comp_thread.id,
            "discussion_id": discussion_thread.id if discussion_thread else None,
            "name": thread_name,
            "duration": duration_minutes,
            "direction": direction,
            "baseline": baseline,
            "problems": problems,
            "participants": {},
            "lock": asyncio.Lock()
        }

        # Persist to JSON
        json_data = {
            "type": comp_type,
            "name": thread_name,
            "duration": duration_minutes,
            "direction": direction,
            "baseline": baseline,
            "problems": problems,
            "thread_id": comp_thread.id,
            "discussion_id": discussion_thread.id if discussion_thread else None
        }

        json_path = os.path.join("data", "competitions_jsons", f"{comp_type}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=4)

        await ctx.send(f"✅ Created `{comp_type}` competition. Metadata saved to `{json_path}`.")

    # ----- Join -----
    @competition.command(name="join")
    async def join_competition(self, ctx, comp_type: str):
        comp_type = comp_type.lower()
        comp = self.active_comps.get(comp_type)
        if not comp:
            await ctx.send("❌ No active competition.")
            return

        async with comp["lock"]:
            if str(ctx.author.id) in comp["participants"]:
                await ctx.send("❌ You already joined this competition.")
                return

            comp_thread = ctx.guild.get_thread(comp["thread_id"])
            if comp_thread:
                try:
                    await comp_thread.add_user(ctx.author)
                except Exception:
                    pass

            baselines = {}
            for comp_id in comp["problems"]:
                user_score, min_s, max_s = await self.fetch_kaggle_score(comp_id, ctx.author.id)
                # Baseline is your current leaderboard score at join time
                baselines[comp_id] = comp["baseline"]
                self.save_participant(str(ctx.author.id), comp_type, comp_id, user_score, True)

            comp["participants"][str(ctx.author.id)] = {"baseline": baselines, "active": True, "joined_at": time.time()}
            await ctx.send(f"✅ {ctx.author.display_name} joined {comp['name']}.")

            # Timer
            async def timer_task(user_id_str: str):
                await asyncio.sleep(comp["duration"] * 60)
                await self.freeze_participant(ctx.guild, comp_type, user_id_str)

            asyncio.create_task(timer_task(str(ctx.author.id)))

    # ----- Leaderboard -----
    @competition.command(name="leaderboard")
    async def leaderboard(self, ctx, comp_type: str):
        comp = self.active_comps.get(comp_type.lower())
        if not comp:
            await ctx.send("❌ No active competition.")
            return

        rows = []
        for uid_str, pdata in comp["participants"].items():
            uid = int(uid_str)
            member = ctx.guild.get_member(uid)
            name = member.display_name if member else f"Unknown({uid_str})"

            # get kaggle id (for display)
            conn = sqlite3.connect("data/kaggle.db")
            c = conn.cursor()
            c.execute("SELECT kaggle_id FROM kaggle_links WHERE discord_id=?", (uid_str,))
            row = c.fetchone()
            conn.close()
            kaggle_id = row[0] if row else "?"

            total_norm = 0.0
            detail = []
            for comp_id in comp["problems"]:
                if pdata["active"]:
                    user_score, min_s, max_s = await self.fetch_kaggle_score(comp_id, uid)
                    baseline = comp["baseline"]
                    norm = self._compute_norm(comp["direction"], baseline, user_score, min_s, max_s)
                else:
                    # use frozen values
                    conn = sqlite3.connect(DB_FILE)
                    c = conn.cursor()
                    c.execute(
                        "SELECT score, norm_score FROM frozen_scores WHERE user_id=? AND comp_type=? AND comp_id=?",
                        (uid_str, comp_type, comp_id)
                    )
                    row = c.fetchone()
                    conn.close()
                    if row:
                        user_score, norm = row
                    else:
                        user_score, norm = 0.0, 0.0

                total_norm += norm
                detail.append(f"{norm:.1f} ({user_score:.4f})")

            rows.append((name, kaggle_id, total_norm, detail))

        rows.sort(key=lambda x: x[2], reverse=True)
        header = " | ".join([f"P{i+1}" for i in range(len(comp["problems"]))])
        arrow = "↑" if comp["direction"] == "higher" else "↓"
        msg = "```\n"
        msg += f"Direction: {comp['direction']} {arrow}\n"
        msg += "Name         | KaggleID       | NormSum | " + header + "\n"
        for name, kaggle_id, total, detail in rows:
            msg += f"{name:12} | {kaggle_id:13} | {total:.1f} | {' | '.join(detail)}\n"
        msg += "```"
        await ctx.send(msg)

    @competition.command(name="time")
    async def competition_time(self, ctx, comp_type: str):
        """Show remaining time for active participants."""
        import time
        comp_type = comp_type.lower()
        comp = self.active_comps.get(comp_type)
        if not comp:
            await ctx.send("❌ No active competition found.")
            return

        duration_sec = comp["duration"] * 60
        lines = []
        now = time.time()

        for uid_str, pdata in comp["participants"].items():
            if not pdata.get("active"):
                continue
            joined_at = pdata.get("joined_at")
            if not joined_at:
                # fallback: fetch from DB
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute(
                    "SELECT joined_at FROM participants WHERE user_id=? AND comp_type=? LIMIT 1",
                    (uid_str, comp_type)
                )
                row = c.fetchone()
                conn.close()
                if row and row[0]:
                    joined_at = row[0]
                else:
                    continue

            elapsed = now - joined_at
            remaining = max(0, duration_sec - elapsed)
            m, s = divmod(int(remaining), 60)
            member = ctx.guild.get_member(int(uid_str))
            name = member.display_name if member else uid_str
            lines.append(f"{name}: {m}m {s}s left")

        if not lines:
            await ctx.send("Nobody currently active in that competition.")
            return

        msg = "```\n" + "\n".join(lines) + "\n```"
        await ctx.send(msg)

    # ----- Admin Overrides -----
    @competition.command(name="kick")
    @commands.has_permissions(administrator=True)
    async def kick_participant(self, ctx, comp_type: str, member: discord.Member):
        comp_type = comp_type.lower()
        comp = self.active_comps.get(comp_type)
        if not comp:
            await ctx.send("❌ No active competition.")
            return

        uid_str = str(member.id)
        if uid_str not in comp["participants"]:
            await ctx.send(f"⚠️ {member.display_name} is not a participant in {comp['name']}.")
            return

        comp_thread = ctx.guild.get_thread(comp["thread_id"])
        if comp_thread:
            try:
                await comp_thread.remove_user(member)
            except Exception:
                pass

        del comp["participants"][uid_str]
        self.remove_participant(uid_str, comp_type)
        await ctx.send(f"🗑️ {member.display_name} has been removed from {comp['name']}.")

    @competition.command(name="forcejoin")
    @commands.has_permissions(administrator=True)
    async def forcejoin_participant(self, ctx, comp_type: str, member: discord.Member):
        comp_type = comp_type.lower()
        comp = self.active_comps.get(comp_type)
        if not comp:
            await ctx.send("❌ No active competition.")
            return

        comp_thread = ctx.guild.get_thread(comp["thread_id"])
        if comp_thread:
            try:
                await comp_thread.add_user(member)
            except Exception:
                pass

        baselines = {}
        for comp_id in comp["problems"]:
            user_score, min_s, max_s = await self.fetch_kaggle_score(comp_id, member.id)
            baselines[comp_id] = user_score
            self.save_participant(str(member.id), comp_type, comp_id, user_score, True)

        comp["participants"][str(member.id)] = {"baseline": baselines, "active": True}
        await ctx.send(f"✅ {member.display_name} was forcibly added to {comp['name']} by an admin.")

    @competition.command(name="end")
    @commands.has_permissions(administrator=True)
    async def end_competition(self, ctx, comp_type: str):
        """Ends an active competition and removes all related data."""
        comp_type = comp_type.lower()
        comp = self.active_comps.get(comp_type)

        if not comp:
            await ctx.send(f"❌ No active competition found for type `{comp_type}`.")
            return

        # Try to close / archive threads
        comp_thread = ctx.guild.get_thread(comp["thread_id"])
        discussion_thread = ctx.guild.get_thread(comp["discussion_id"])
        closed_threads = []
        for thread in [comp_thread, discussion_thread]:
            if thread:
                try:
                    await thread.edit(archived=True, locked=True)
                    closed_threads.append(thread.name)
                except Exception:
                    pass

        # Remove DB entries
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        try:
            c.execute("DELETE FROM participants WHERE comp_type=?", (comp_type,))
            c.execute("DELETE FROM frozen_scores WHERE comp_type=?", (comp_type,))
            conn.commit()
        finally:
            conn.close()

        # Remove from memory
        del self.active_comps[comp_type]

        # 5️⃣ Delete saved JSON file
        json_path = os.path.join("data", "competitions_jsons", f"{comp_type}.json")
        try:
            if os.path.exists(json_path):
                os.remove(json_path)
                print(f"🗑️ Deleted saved JSON for competition {comp_type}")
        except Exception as e:
            print(f"⚠️ Failed to delete competition JSON {json_path}: {e}")


        # Confirm to Discord
        msg = f"🛑 Competition `{comp_type}` has been ended and cleared from the database."
        if closed_threads:
            msg += f"\n🧵 Threads archived: {', '.join(closed_threads)}"
        await ctx.send(msg)
    
    async def freeze_participant(self, guild, comp_type: str, user_id_str: str):
        """Freeze a participant manually (for expired timers or recovery)."""
        comp = self.active_comps.get(comp_type)
        if not comp:
            return

        user_id = int(user_id_str)
        member = guild.get_member(user_id)

        # 1) Unlock discussion and add user
        discussion_thread = guild.get_thread(comp["discussion_id"])
        if discussion_thread:
            try:
                await discussion_thread.edit(locked=False)
                if member:
                    await discussion_thread.add_user(member)
                await discussion_thread.send(f"⏰ <@{user_id_str}>, your time ended. Scores frozen.")
            except Exception as e:
                print(f"⚠️ Discussion unlock failed during recovery: {e}")

        # 2) Remove from main thread
        comp_thread = guild.get_thread(comp["thread_id"])
        if comp_thread and member:
            try:
                await comp_thread.remove_user(member)
            except Exception as e:
                print(f"⚠️ Could not remove {user_id_str} from comp thread: {e}")

        # 3) Freeze and record scores
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        for comp_id in comp["problems"]:
            user_score, min_s, max_s = await self.fetch_kaggle_score(comp_id, user_id)
            user_data = comp["participants"].get(user_id_str)
            if not user_data:
                print(f"⚠️ No participant data for {user_id_str} in {comp_type}, skipping freeze.")
                return

            baseline = user_data["baseline"].get(comp_id, comp["baseline"])
            norm = self._compute_norm(comp["direction"], baseline, user_score, min_s, max_s)
            c.execute("REPLACE INTO frozen_scores VALUES (?, ?, ?, ?, ?)",
                    (user_id_str, comp_type, comp_id, user_score, norm))
        conn.commit()
        conn.close()

        # 4) Mark inactive
        comp["participants"][user_id_str]["active"] = False
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("UPDATE participants SET active=0 WHERE user_id=? AND comp_type=?",
                (user_id_str, comp_type))
        conn.commit()
        conn.close()

async def setup(bot):
    await bot.add_cog(CompetitionCog(bot))
