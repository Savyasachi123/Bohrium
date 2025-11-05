import discord
from discord.ext import commands

# =======================
# 🔧 HARD-CODE HELP HERE
# =======================
# Structure:
# HELPTABLE = {
#   "command": {
#       "subcommand": "description",
#       "_desc": "optional overall command description (shown on ;help command)"
#   },
#   ...
# }
HELPTABLE = {
    "kaggle": {
        "_desc": ("Manage Kaggle account verification, linking, and stats inside the SOTA-AI Discord server.\n\n"
                  "**Subcommands include:**\n"
                  "- `identify`\n- `verify`\n- `get`\n- `list`\n\n"
                  "ADMIN only command:\n"
                  "- `unlink`"
        ),
        
        "identify": (
            "Begin linking your Kaggle account to your Discord profile.\n\n"
            "**Usage:** `;kaggle identify <kaggle_username>`\n"
            "**What it does:**\n"
            "- Generates a one-time verification code like `SOTA-12345`.\n"
            "- You must paste this code in your Kaggle profile **bio/About Me**.\n"
            "- Then run `;kaggle verify` to complete verification.\n"
            "**Example:** `;kaggle identify Bohrium`"
        ),

        "verify": (
            "Finalize your Kaggle account verification process.\n\n"
            "**Usage:** `;kaggle verify`\n"
            "**What it does:**\n"
            "- Fetches your Kaggle profile webpage.\n"
            "- Checks if your assigned verification code (from `;kaggle identify`) appears in your bio.\n"
            "- If found, marks your Kaggle ID as **verified** in the database.\n"
            "**Tip:** Make sure your bio is public and contains the full code before running this."
        ),

        "get": (
            "Display a member’s Kaggle profile and statistics as an embed.\n\n"
            "**Usage:** `;kaggle get <@discord name>`\n"
            "**What it does:**\n"
            "- If no member is tagged, shows your own linked Kaggle info.\n"
            "- If another user is tagged, shows their Kaggle profile if linked.\n"
            "- Includes Kaggle rank (Novice → Grandmaster), join date, followers, competitions, notebooks, discussions, and bio.\n"
            "**Example:** `;kaggle get @Alice`"
        ),

        "unlink": (
            "⚙️ **Admin-only:** Remove someone’s Kaggle link from the database.\n\n"
            "**Usage:** `;kaggle unlink @member`\n"
            "**Permissions required:** `Manage Server`\n"
            "**What it does:**\n"
            "- Deletes the specified member’s record from the Kaggle database.\n"
        ),

        "list": (
            "List all Discord members who have linked Kaggle IDs.\n\n"
            "**Usage:** `;kaggle list`\n"
            "**What it does:**\n"
            "- Displays all linked accounts with verification status.\n"
            "- Shows up to 20 users per page and supports reaction-based page navigation. Use arrows to go forward and backwards.\n"
            "- Verified accounts show ✅, unverified show ⚠️.\n"
        )
    }
    ,
    "comp": {
        "_desc": (
            "Join, attempt and see your scores in SOTA-AI community Kaggle-based competitions.\n\n"
            "Competitions can be **weekly**, **biweekly**, or **monthly** — each with a fixed duration and Kaggle problem set. "
            "Scores are automatically fetched from Kaggle, normalized against your baseline, and frozen when your timer ends.\n\n"
            "**Subcommands include:**\n"
            "- `join`\n- `leaderboard`\n- `time`\n\n"
            "ADMIN only command:\n"
            "- `make`\n- `kick`\n- `forcejoin`\n- `end`"
        ),
        "time": (
            "⏱️ Check how much time is left for currently active participants in a competition.\n\n"
            "**Usage:** `;comp time <weekly/biweekly/monthly>`\n\n"
            "**What it does:**\n"
            "- Shows a list of all participants who are still active (their timer hasn’t expired yet).\n"
            "- Displays their **remaining time** in minutes and seconds.\n"
            "- Useful for admins to monitor ongoing competition progress, or for participants to confirm their remaining duration.\n\n"
            "**Example:**\n"
            "```\n"
            ";comp time weekly\n"
            "Alice: 42m 18s left\n"
            "Bob: 11m 05s left\n"
            "Charlie: 0m 59s left\n"
            "```"
        ),
        "make": (
            "🛠️ **Admin-only:** Create and initialize a new competition.\n\n"
            "**Usage:**\n"
            "`;comp make <type> <thread_name> <duration_minutes> <direction> <baseline> <problem_links...>`\n\n"
            "**Arguments:**\n"
            "- `<type>` — one of `weekly`, `biweekly`, `monthly` (used as competition key)\n"
            "- `<thread_name>` — short title for competition threads (e.g., `Titanic_Weekly`)\n"
            "- `<duration_minutes>` — how long each participant gets before freeze (e.g., `120`)\n"
            "- `<direction>` — `higher` or `lower`, depending on metric orientation\n"
            "- `<baseline>` — baseline score to normalize improvements from\n"
            "- `<problem_links...>` — one or more Kaggle competition links\n\n"
            "**What it does:**\n"
            "1. Creates a locked competition thread for announcements.\n"
            "2. Creates a locked discussion thread that unlocks for each participant after their timer ends.\n"
            "3. Saves competition metadata to `/data/competitions_jsons/<type>.json`.\n\n"
            "**Example:**\n"
            "`;comp make weekly AI_Weekly 120 higher 0.75 https://www.kaggle.com/competitions/titanic`"
        ),

        "join": (
            "🎯 Join an ongoing competition and start your timer.\n\n"
            "**Usage:** `;comp join <weekly/biweekly/monthly>`\n\n"
            "**What it does:**\n"
            "1. Validates that the competition exists.\n"
            "2. Fetches your current Kaggle leaderboard score for each competition problem.\n"
            "3. Adds you to the private competition thread.\n"
            "4. Starts your personal timer for the competition duration.\n"
            "5. When time is up, your scores are frozen and your access to the main thread is removed.\n"
            "6. Discussion thread unlocks so you can chat with others.\n\n"
            "**Example:** `;comp join weekly`"
        ),

        "leaderboard": (
            "🏆 Show the live or frozen leaderboard for an active competition.\n\n"
            "**Usage:** `;comp leaderboard <weekly/biweekly/monthly>`\n\n"
            "**What it shows:**\n"
            "- All participants’ names and Kaggle IDs.\n"
            "- Normalized scores (0–100 scale) across all problems.\n"
            "- Raw Kaggle scores per problem.\n\n"
            "**How it works:**\n"
            "- If a user’s timer is still running, their current Kaggle score is fetched live.\n"
            "- If their timer ended, their frozen score is used.\n\n"
            "**Example output:**\n"
            '''\n
            Direction: higher ↑
            `Name         | KaggleID       | NormSum | P1 | P2
            Alice        | alice123       | 89.4    | 92.0 (0.8610) | 86.8 (0.7533)
            Bob          | bob_ai         | 74.2    | 70.0 (0.6987) | 78.4 (0.7821)`
            '''
        ),

        "kick": (
            "🚫 **Admin-only:** Remove a participant from an active competition.\n\n"
            "**Usage:** `;comp kick <weekly/biweekly/monthly> <@member>`\n\n"
            "**What it does:**\n"
            "- Removes the user from the competition’s participant list.\n"
            "- Deletes their participation data from the database.\n"
            "- Removes them from the competition thread.\n\n"
            "**Example:** `;comp kick weekly @JohnDoe`"
        ),

        "forcejoin": (
            "⚙️ **Admin-only:** Force-add a member into a competition without them running `join`.\n\n"
            "**Usage:** `;comp forcejoin <weekly/biweekly/monthly> <@member>`\n\n"
            "**What it does:**\n"
            "- Adds the specified member directly to the competition and its thread.\n"
            "- Fetches their current Kaggle scores.\n"
            "- Saves participation data into the database.\n\n"
            "**Example:** `;comp forcejoin monthly @Jane`"
        ),

        "end": (
            "🛑 **Admin-only:** End and archive a competition, clearing all related data.\n\n"
            "**Usage:** `;comp end <weekly/biweekly/monthly>`\n\n"
            "**What it does:**\n"
            "1. Archives and locks both the main and discussion threads.\n"
            "2. Deletes all participants and frozen score data from the database.\n"
            "3. Removes the competition from memory.\n"
            "4. Deletes its saved JSON file from `data/competitions_jsons/`.\n\n"
            "**Example:** `;comp end weekly`"
        )
    },
    "gitgud": {
        "_desc": (
            "🎲 **Command:** `;gitgud [filters]`\n\n"
            "**Purpose:**\n"
            "Fetch and display a random Kaggle competition, optionally filtered by category or keyword tags.\n\n"
            "**Filters (optional):**\n"
            "- `category=<type>` — filter by Kaggle category (e.g. `featured`, `playground`, `research`, `recruitment`).\n"
            "- `tag=<keyword>` — filter by topic keyword (e.g. `nlp`, `vision`, `finance`). You can include multiple tag filters. This is a bit clanky and is not perfect so we reccomend not using this.\n\n"
            "**Examples:**\n"
            "- `;gitgud` → Random competition from all categories.\n"
            "- `;gitgud category=featured` → Random competition from Kaggle’s Featured list.\n"
            "- `;gitgud tag=nlp tag=transformers` → Random competition mentioning NLP or transformers. (Chances are that this fails)\n\n"
            "**Output:**\n"
            "- An embedded card showing:\n"
            "  - Competition Title (with clickable Kaggle link)\n"
            "  - Description (short summary)\n"
            "  - Category (e.g., Playground, Featured)\n"
            "  - Reward and Deadline (if available)\n"
            "  - Organizing institution name\n\n"
            "- If filters yield no results, a message will inform you accordingly."
        )
    },
    "chat": {
        "_desc": (
            "💬 **Gemini-Powered Conversational Chatbot** — Talk naturally with the bot by simply mentioning it in any channel.\n\n"
            "This Cog connects to **Google Gemini (model: gemini-2.5-flash-lite)** and lets you chat contextually — the bot remembers your recent messages in that channel.\n\n"
            "**How it works:**\n"
            "- Mention the bot (`@BotName`) followed by your message.\n"
            "- It responds intelligently, using the last 20 messages in that channel as conversation context.\n"
            "- Each channel has its own independent memory.\n\n"
            "**Example:**\n"
            "`@Bohrium how do I improve my Kaggle score?`\n"
            "→ The bot replies using Gemini’s reasoning and prior messages in the thread."
        )
    },
    "whoisorz": {
        "_desc": (
            "Run it too find out! UwU"
        )
    }

    # Add more commands here...
}

DISPLAY_PREFIX = ";"  # shown in help text; doesn't change your actual bot prefix

DISPLAY_PREFIX = ";"

def _keys_ci(d):
    return {k.lower(): k for k in d.keys()}

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        try:
            bot.remove_command("help")
        except Exception:
            pass

    @commands.command(name="help")
    async def help_cmd(self, ctx, command: str = None, subcommand: str = None):
        """
        ;help                -> show description of help and all commands
        ;help <command>      -> show that command’s description + subcommands
        ;help <command> <subcommand> -> show exact subcommand description
        """
        # ✅ When no args → show general help description first
        if command is None:
            embed = discord.Embed(
                title="🆘 Help Command",
                description=(
                    "This command helps you understand how to use the bot and its features.\n\n"
                    "**Usage:**\n"
                    f"- `{DISPLAY_PREFIX}help` — Show this overview.\n"
                    f"- `{DISPLAY_PREFIX}help <command>` — Show help for a specific command.\n"
                    f"- `{DISPLAY_PREFIX}help <command> <subcommand>` — Show help for a specific subcommand.\n\n"
                    "Below is a list of all available commands:\n" 
                    "- `kaggle`\n- `comp`\n- `gitgud`\n- `chat`\n- `whoisorz`"
                ),
                color=discord.Color.blurple()
            )
            await ctx.send(embed=embed)
            await self._send_all_commands(ctx)
            return

        table_ci = _keys_ci(HELPTABLE)
        cmd_key = table_ci.get(command.lower())
        if cmd_key is None:
            await ctx.send(f"❌ Unknown command `{command}`. Try `{DISPLAY_PREFIX}help`.")
            return

        if subcommand is None:
            desc = HELPTABLE[cmd_key].get("_desc", "No description available.")
            await self._send_embed_or_text(ctx, title=f"{cmd_key} — Overview", description=desc)
            return

        subs = HELPTABLE[cmd_key]
        subs_ci = _keys_ci(subs)
        sub_key = subs_ci.get(subcommand.lower())
        if sub_key is None or sub_key == "_desc":
            await ctx.send(f"❌ Unknown subcommand `{subcommand}` for `{cmd_key}`. Try `{DISPLAY_PREFIX}help {cmd_key}`.")
            return

        desc = subs[sub_key]
        await self._send_embed_or_text(ctx, title=f"{cmd_key} → {sub_key}", description=desc)

    async def _send_all_commands(self, ctx):
        embed = discord.Embed(
            title="Command Index",
            description=f"Use `{DISPLAY_PREFIX}help <command>` or `{DISPLAY_PREFIX}help <command> <subcommand>`",
            color=discord.Color.blurple()
        )
        for cmd, subs in HELPTABLE.items():
            brief = subs.get("_desc", "No description.")
            sub_list = [s for s in subs.keys() if s != "_desc"]
            preview = ", ".join(sub_list[:5]) + ("…" if len(sub_list) > 5 else "")
            embed.add_field(name=f"{cmd}", value=f"{brief}\n**Subcommands:** {preview or '—'}", inline=False)
        await self._safe_send(ctx, embed)

    async def _send_command_overview(self, ctx, cmd_key: str):
        subs = HELPTABLE[cmd_key]
        embed = discord.Embed(
            title=f"{cmd_key} — Help",
            description=subs.get("_desc", "No description."),
            color=discord.Color.green()
        )
        for sub, desc in subs.items():
            if sub == "_desc":
                continue
            embed.add_field(name=f"{DISPLAY_PREFIX}{cmd_key} {sub}", value=desc if len(desc) < 1024 else (desc[:1000] + "…"), inline=False)
        await self._safe_send(ctx, embed)

    async def _send_embed_or_text(self, ctx, title: str, description: str):
        embed = discord.Embed(title=title, description=description, color=discord.Color.gold())
        await self._safe_send(ctx, embed)

    async def _safe_send(self, ctx, embed: discord.Embed):
        try:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            lines = [f"# {embed.title or ''}", embed.description or ""]
            for f in embed.fields:
                lines.append(f"\n**{f.name}**\n{f.value}")
            text = "\n".join(lines).strip()
            await ctx.send(f"```md\n{text}\n```")

async def setup(bot):
    await bot.add_cog(HelpCog(bot))
