import os
import json
import asyncio
import datetime
import re
from typing import Optional, Dict, Any, List

import aiohttp
import discord
from discord.ext import commands, tasks
from discord import app_commands

# ------------- CONFIG SECTION (YOUR IDS) -------------

CONFIG = {
    "guild_id": None,  # optional, can be left as None

    "channels": {
        "server_announcements": 1439867318116159519,
        "event_updates": 1439867838130294845,
        "milestone_feed": 1439867579916091433,
        "furnace_upgrades": 1439872050922782840,
        "server_chat": 1439859903329075271,

        "review_inbox": 1439897703923322941,
        "mod_log": 1439900032961745006,
        "join_leave_log": 1439900133184765993,
        "application_log": 1439900188323086439,
        "translation_log": 1439900280991907991,
        "bot_errors": 1439900350990520343,
        "giftcode_updates": 1439869895444795402,
        "giftcode_log": 1439870315093032981,

        # These you can update when you have the IDs:
        "welcome_channel": 0,                 # optional: 👋｜welcome
        "verify_channel": 1439783924539723868,  # 🛂｜verify-here
        "verification_form_channel": 0        # optional extra if you make one
    },

    "alliance_channels": {
        "BTK": {
            "alliance_chat": 1439797314347864124,
            "leader_chat": 1439798704868561007,
        },
        "SUN": {
            "alliance_chat": 1439842114707128504,
            "leader_chat": 1439842810642829374,
        },
        "vVv": {
            "alliance_chat": 1439846131088494744,
            "leader_chat": 1439846389856206900,
        },
        "EUA": {
            "alliance_chat": 1439848280216567848,
            "leader_chat": 1439848487935283272,
        },
        "FUN": {
            "alliance_chat": 1439852214414872576,
            "leader_chat": 1439852442459312208,
        },
        "WRS": {
            "alliance_chat": 1439855657221230684,
            "leader_chat": 1439855930513821737,
        },
        "TEA": {
            "alliance_chat": 1439857216516788246,
            "leader_chat": 1439857391272333383,
        },
    },

    "roles": {
        "admin": 1439730058276245585,
        "moderator": 1439731096391520398,
        "bot_role": 1439731617798160485,
        "r5_global": 1439781046445932628,
        "r4_global": 1439781111919284234,

        "btk": 1439742421880541304,
        "btk_r4": 1439794970000097410,
        "btk_r5": 1439794683034206331,

        "sun": 1439840443830505544,
        "sun_r4": 1439840205518540951,
        "sun_r5": 1439840054964129883,

        "vvv": 1439844354486304871,
        "vvv_r4": 1439844215323492422,
        "vvv_r5": None,  # fill this if you create it

        "eua": 1439847035577827328,
        "eua_r4": 1439846932028588102,
        "eua_r5": 1439846798402392167,

        "fun": 1439850123701129388,
        "fun_r4": 1439850006759608451,
        "fun_r5": 1439849839113277490,

        "wrs": 1439852994983231600,
        "wrs_r4": 1439852887147544626,
        "wrs_r5": 1439852766565765211,

        "tea": 1439853673458176111,
        "tea_r4": 1439853548341825566,
        "tea_r5": 1439853306305581118,

        "age_19plus": 1439742877646192711,
        "age_under19": 1439742932646363146,
        "pending": 1439893449586507786,
    },

    "language_roles": {
        1439732594693509131: "en",  # English
        1439733053550497915: "pl",  # Polish
        1439733487195394148: "fr",  # French
        1439733731534311604: "bs",  # Bosnian
        1439734067955499160: "pt",  # Portuguese (Brazil)
        1439734590632759336: "pt",  # Portuguese (Portugal)
        1439734720610177198: "fa",  # Persian
        1439735048554418227: "ar",  # Arabic
        1439735171061645507: "de",  # German
        1439737062575181966: "ru",  # Russian
        1439737330263916696: "ko",  # Korean
        1439737843445530644: "th",  # Thai
        1439737886348939294: "tr",  # Turkish
        1439737951138353202: "zh",  # Chinese
        1439884540331167775: "es",  # Spanish
    },

    "alliance_name_to_role_key": {
        "BTK": "btk",
        "SUN": "sun",
        "VVV": "vvv",
        "vVv": "vvv",
        "EUA": "eua",
        "FUN": "fun",
        "WRS": "wrs",
        "TEA": "tea",
    },

    # Participation milestones (messages sent)
    "participation_milestones": [50, 200, 500],
}

DATA_DIR = "data"
PLAYER_IDS_FILE = os.path.join(DATA_DIR, "player_ids.json")
LAST_SEEN_FILE = os.path.join(DATA_DIR, "last_seen.json")
PARTICIPATION_FILE = os.path.join(DATA_DIR, "participation.json")


def ensure_data_files():
    os.makedirs(DATA_DIR, exist_ok=True)
    for path in (PLAYER_IDS_FILE, LAST_SEEN_FILE, PARTICIPATION_FILE):
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump({}, f)


def load_json(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_json(path: str, data: Dict[str, Any]):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ------------- TRANSLATOR (FREE API USING LIBRETRANSLATE) -------------

class Translator:
    BASE_URL = "https://libretranslate.de/translate"  # public instance, free but rate-limited

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.cache: Dict[tuple, str] = {}

    async def start(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None

    async def translate(self, text: str, target_lang: str, source_lang: str = "auto") -> str:
        key = (text, target_lang)
        if key in self.cache:
            return self.cache[key]

        await self.start()
        try:
            async with self.session.post(
                self.BASE_URL,
                data={
                    "q": text,
                    "source": source_lang,
                    "target": target_lang,
                    "format": "text",
                },
                timeout=10,
            ) as resp:
                if resp.status != 200:
                    return text
                data = await resp.json()
                translated = data.get("translatedText", text)
                self.cache[key] = translated
                return translated
        except Exception:
            # If translation fails, just return original text
            return text


translator = Translator()

# ------------- BOT SETUP -------------

# Use all intents so joins, members, and slash commands work correctly
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

player_ids: Dict[str, str] = {}
last_seen: Dict[str, str] = {}
participation: Dict[str, int] = {}

guess_games: Dict[int, int] = {}  # user_id -> secret number
blackjack_games: Dict[int, Dict[str, Any]] = {}  # simple game state


async def log_to(channel_id: int, message: str):
    if not channel_id:
        return
    channel = bot.get_channel(channel_id)
    if channel:
        try:
            await channel.send(message)
        except Exception:
            pass


def get_user_language_code(member: discord.Member) -> str:
    for role in member.roles:
        if role.id in CONFIG["language_roles"]:
            return CONFIG["language_roles"][role.id]
    return "en"


def get_alliance_name_from_roles(member: discord.Member) -> Optional[str]:
    role_map = CONFIG["alliance_name_to_role_key"]
    for name, key in role_map.items():
        role_id = CONFIG["roles"].get(key)
        if role_id and any(r.id == role_id for r in member.roles):
            return name
    return None


def furnace_level_from_text(text: str) -> Optional[str]:
    text = text.upper()
    # Try F<number>
    m = re.search(r"\bF(\d{1,2})\b", text)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 30:
            return f"F{n}"
    # Try FC<number>
    m = re.search(r"\bFC(\d{1,2})\b", text)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 10:
            return f"FC{n}"
    # Try "Furnace 12" style
    m = re.search(r"FURNACE\s*(\d{1,2})", text)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 30:
            return f"F{n}"
    return None


# ------------- VERIFICATION UI (BUTTON + MODAL) -------------

class VerificationModal(discord.ui.Modal, title="PapaMike Server Application"):
    server_number = discord.ui.TextInput(
        label="What WOS server are you on?",
        placeholder="Example: 123",
        required=True,
        max_length=10,
    )
    player_id = discord.ui.TextInput(
        label="Your Whiteout Survival Player ID",
        placeholder="Numbers only",
        required=True,
        max_length=30,
    )
    alliance = discord.ui.TextInput(
        label="Alliance (BTK, SUN, vVv, EUA, FUN, WRS, TEA)",
        placeholder="Type one exactly, e.g. BTK",
        required=True,
        max_length=10,
    )
    rank = discord.ui.TextInput(
        label="Rank (R1, R2, R3, R4, R5)",
        placeholder="R1 / R2 / R3 / R4 / R5",
        required=True,
        max_length=5,
    )
    main_language = discord.ui.TextInput(
        label="Main language (English, French, etc.)",
        placeholder="English / French / Portuguese / ...",
        required=True,
        max_length=30,
    )
    age_group = discord.ui.TextInput(
        label="Age group (under 19 or 19+)",
        placeholder="under 19 or 19+",
        required=True,
        max_length=10,
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            member = interaction.user
            guild = interaction.guild

            # Save player ID
            pid = self.player_id.value.strip()
            player_ids[str(member.id)] = pid
            save_json(PLAYER_IDS_FILE, player_ids)

            # Alliance role
            alliance_input = self.alliance.value.strip().upper()
            alliance_key = CONFIG["alliance_name_to_role_key"].get(alliance_input)
            alliance_role = None
            if alliance_key:
                rid = CONFIG["roles"].get(alliance_key)
                if rid:
                    alliance_role = guild.get_role(rid)

            # Rank (just logged for now)
            rank = self.rank.value.strip().upper()

            # Language role
            lang_input = self.main_language.value.strip().lower()
            target_role = None
            language_name_to_id = {
                "english": 1439732594693509131,
                "polish": 1439733053550497915,
                "french": 1439733487195394148,
                "bosnian": 1439733731534311604,
                "portuguese (brazil)": 1439734067955499160,
                "portuguese (portugal)": 1439734590632759336,
                "persian": 1439734720610177198,
                "arabic": 1439735048554418227,
                "german": 1439735171061645507,
                "russian": 1439737062575181966,
                "korean": 1439737330263916696,
                "thai": 1439737843445530644,
                "turkish": 1439737886348939294,
                "chinese": 1439737951138353202,
                "spanish": 1439884540331167775,
            }

            for name, rid in language_name_to_id.items():
                if lang_input == name or lang_input.startswith(name.split()[0]):
                    target_role = guild.get_role(rid)
                    break

            # Age roles
            age_val = self.age_group.value.strip().lower()
            if "under" in age_val:
                age_role_id = CONFIG["roles"]["age_under19"]
            else:
                age_role_id = CONFIG["roles"]["age_19plus"]
            age_role = guild.get_role(age_role_id) if age_role_id else None

            # Apply roles
            to_add = []
            if alliance_role:
                to_add.append(alliance_role)
            if target_role:
                to_add.append(target_role)
            if age_role:
                to_add.append(age_role)

            if to_add:
                try:
                    await member.add_roles(*to_add, reason="Verified via application form")
                except Exception:
                    pass

            # Remove Pending Verification
            pending_role_id = CONFIG["roles"]["pending"]
            pending_role = guild.get_role(pending_role_id)
            if pending_role in member.roles:
                try:
                    await member.remove_roles(pending_role, reason="Verification complete")
                except Exception:
                    pass

            # Log application
            review_channel = guild.get_channel(CONFIG["channels"]["review_inbox"])
            app_log_channel = guild.get_channel(CONFIG["channels"]["application_log"])

            embed = discord.Embed(
                title="New Application",
                color=discord.Color.blurple(),
                timestamp=datetime.datetime.utcnow(),
            )
            embed.add_field(name="User", value=f"{member} ({member.mention})", inline=False)
            embed.add_field(name="Server", value=self.server_number.value, inline=True)
            embed.add_field(name="Player ID", value=self.player_id.value, inline=True)
            embed.add_field(name="Alliance", value=self.alliance.value, inline=True)
            embed.add_field(name="Rank", value=rank, inline=True)
            embed.add_field(name="Language", value=self.main_language.value, inline=True)
            embed.add_field(name="Age Group", value=self.age_group.value, inline=True)

            if review_channel:
                await review_channel.send(embed=embed)
            if app_log_channel:
                await app_log_channel.send(embed=embed)

            # Welcome message after approval
            welcome_channel_id = CONFIG["channels"].get("welcome_channel") or 0
            if welcome_channel_id:
                wc = guild.get_channel(welcome_channel_id)
                if wc:
                    await wc.send(
                        f"Welcome {member.mention}! ✅ Your application has been recorded.\n"
                        f"Alliance: **{self.alliance.value}**, Rank: **{rank}**, Server: **{self.server_number.value}**."
                    )

            await interaction.response.send_message(
                "Thank you! ✅ Your application has been submitted and your roles have been updated.",
                ephemeral=True,
            )
        except Exception as e:
            await log_to(CONFIG["channels"]["bot_errors"], f"Error in VerificationModal.on_submit: `{e}`")
            try:
                await interaction.response.send_message(
                    "⚠️ Something went wrong while processing your application. Please contact an admin.",
                    ephemeral=True,
                )
            except Exception:
                pass


class VerifyView(discord.ui.View):
    """Persistent view with a button to open the verification modal."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Start Verification ✅",
        style=discord.ButtonStyle.primary,
        custom_id="papamike_verify_button"
    )
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.send_modal(VerificationModal())
        except Exception as e:
            await log_to(CONFIG["channels"]["bot_errors"], f"Error opening VerificationModal: `{e}`")
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "⚠️ Could not open the verification form. Please try again or contact an admin.",
                    ephemeral=True,
                )


# ------------- EVENTS -------------

@bot.event
async def on_ready():
    ensure_data_files()
    global player_ids, last_seen, participation
    player_ids = load_json(PLAYER_IDS_FILE)
    last_seen = load_json(LAST_SEEN_FILE)
    participation = load_json(PARTICIPATION_FILE)

    # Register persistent view for button so old messages still work after restart
    bot.add_view(VerifyView())

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} application commands.")
    except Exception as e:
        print(f"Error syncing commands: {e}")
        await log_to(CONFIG["channels"]["bot_errors"], f"Error syncing slash commands: `{e}`")

    if not utc_arena_reminder.is_running():
        utc_arena_reminder.start()
    if not inactivity_check.is_running():
        inactivity_check.start()

    print(f"Logged in as {bot.user} (ID: {bot.user.id})")


@bot.event
async def on_member_join(member: discord.Member):
    # Assign Pending Verification
    pending_role_id = CONFIG["roles"]["pending"]
    pending_role = member.guild.get_role(pending_role_id)
    if pending_role:
        try:
            await member.add_roles(pending_role, reason="New member pending verification")
        except Exception:
            pass

    # Log join
    await log_to(
        CONFIG["channels"]["join_leave_log"],
        f"➡️ {member.mention} joined the server. Assigned **Pending Verification**."
    )

    # Send auto verification message in verify-here channel
    verify_channel_id = CONFIG["channels"].get("verify_channel") or 0
    if verify_channel_id:
        ch = member.guild.get_channel(verify_channel_id)
        if ch:
            try:
                await ch.send(
                    content=(
                        f"Welcome {member.mention}! 👋\n"
                        "Click the button below to start your verification.\n\n"
                        "**You must complete this to see the rest of the server.**"
                    ),
                    view=VerifyView(),
                )
            except Exception as e:
                await log_to(CONFIG["channels"]["bot_errors"], f"Error sending verify message: `{e}`")

    # Optional welcome channel
    welcome_channel_id = CONFIG["channels"].get("welcome_channel") or 0
    if welcome_channel_id:
        wc = member.guild.get_channel(welcome_channel_id)
        if wc:
            try:
                await wc.send(
                    f"Welcome {member.mention}! 🎉\n"
                    "Please go to the verification channel and click **Start Verification ✅** to unlock the server."
                )
            except Exception:
                pass


@bot.event
async def on_member_remove(member: discord.Member):
    # Remove their player ID
    uid = str(member.id)
    if uid in player_ids:
        removed_id = player_ids.pop(uid)
        save_json(PLAYER_IDS_FILE, player_ids)
        await log_to(
            CONFIG["channels"]["giftcode_log"],
            f"🗑 Removed player ID `{removed_id}` for {member} (left server)."
        )

    await log_to(
        CONFIG["channels"]["join_leave_log"],
        f"⬅️ {member} left the server."
    )


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or message.guild is None:
        return

    now_iso = datetime.datetime.utcnow().isoformat()
    uid = str(message.author.id)
    last_seen[uid] = now_iso
    save_json(LAST_SEEN_FILE, last_seen)

    # Participation tracking
    participation[uid] = participation.get(uid, 0) + 1
    save_json(PARTICIPATION_FILE, participation)

    count = participation[uid]
    if count in CONFIG["participation_milestones"]:
        await log_to(
            CONFIG["channels"]["milestone_feed"],
            f"🎉 {message.author.mention} reached **{count} messages** of participation!"
        )

    # Furnace tracking
    if message.channel.id == CONFIG["channels"]["furnace_upgrades"]:
        lvl = furnace_level_from_text(message.content)
        if lvl:
            await log_to(
                CONFIG["channels"]["furnace_upgrades"],
                f"🔥 Congrats {message.author.mention} on reaching **{lvl}**!"
            )

    # Giftcodes – future expansion (for now handled by commands)

    # Auto-translate logs for alliance + global chat
    try:
        important_channels = {CONFIG["channels"]["server_chat"]}
        for data in CONFIG["alliance_channels"].values():
            important_channels.add(data["alliance_chat"])
            important_channels.add(data["leader_chat"])

        if message.channel.id in important_channels:
            lang = get_user_language_code(message.author)
            if lang != "en":
                translated = await translator.translate(message.content, target_lang="en")
                if translated != message.content:
                    await log_to(
                        CONFIG["channels"]["translation_log"],
                        f"🌐 {message.author} in <#{message.channel.id}> (lang {lang}) → EN: {translated}"
                    )
    except Exception as e:
        await log_to(CONFIG["channels"]["bot_errors"], f"Error in auto-translate: `{e}`")

    await bot.process_commands(message)


# ------------- TASKS -------------

@tasks.loop(time=datetime.time(hour=23, minute=55, tzinfo=datetime.timezone.utc))
async def utc_arena_reminder():
    channel_id = CONFIG["channels"]["server_announcements"]
    channel = bot.get_channel(channel_id)
    if channel:
        try:
            await channel.send("⏰ **Arena reset in 5 minutes (00:00 UTC)** – don’t forget to do your fights!")
        except Exception:
            pass


@tasks.loop(hours=24)
async def inactivity_check():
    await bot.wait_until_ready()
    now = datetime.datetime.utcnow()
    threshold = datetime.timedelta(days=30)
    guilds: List[discord.Guild] = bot.guilds

    for guild in guilds:
        for member in guild.members:
            if member.bot:
                continue
            # Skip admins/moderators
            admin_role_id = CONFIG["roles"]["admin"]
            mod_role_id = CONFIG["roles"]["moderator"]
            if any(r.id in (admin_role_id, mod_role_id) for r in member.roles):
                continue

            uid = str(member.id)
            last = last_seen.get(uid)
            if not last:
                # If we've never seen them, start tracking now
                last_seen[uid] = now.isoformat()
                continue
            try:
                last_dt = datetime.datetime.fromisoformat(last)
            except Exception:
                last_dt = now

            if now - last_dt > threshold:
                # Kick for inactivity
                try:
                    await member.kick(reason="Inactive for 30 days")
                    await log_to(
                        CONFIG["channels"]["mod_log"],
                        f"🦵 Kicked {member} for 30 days of inactivity."
                    )
                except Exception:
                    pass

    save_json(LAST_SEEN_FILE, last_seen)


# ------------- SLASH COMMANDS (INCLUDING /verify AS BACKUP) -------------

@bot.tree.command(name="verify", description="Open the PapaMike verification form (backup command).")
async def verify_cmd(interaction: discord.Interaction):
    """User runs /verify to open the application modal."""
    try:
        await interaction.response.send_modal(VerificationModal())
    except Exception as e:
        await log_to(CONFIG["channels"]["bot_errors"], f"Error in /verify: `{e}`")
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "⚠️ Could not open the verification form. Please try again.",
                ephemeral=True,
            )


# ------------- GIFT CODES -------------

async def apply_gift_code_to_all_players(code: str, guild: discord.Guild):
    """
    STUB: This is where you'd implement actual calls to
    https://wos-giftcode.centurygame.com/
    We don't have an official API spec, so this function currently just logs.
    """
    count = len(player_ids)
    await log_to(
        CONFIG["channels"]["giftcode_updates"],
        f"🎁 Gift code `{code}` received. (Stub) Would attempt to apply for **{count}** registered player IDs."
    )
    await log_to(
        CONFIG["channels"]["giftcode_log"],
        f"Gift code `{code}` processing stubbed. You need to implement real HTTP calls if possible."
    )


@bot.tree.command(name="addcode", description="Add a new Whiteout Survival gift code.")
@app_commands.describe(code="The gift code text")
async def addcode_cmd(interaction: discord.Interaction, code: str):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("You don't have permission to add codes.", ephemeral=True)
        return

    await interaction.response.send_message(f"Gift code `{code}` received. Processing...", ephemeral=True)
    await apply_gift_code_to_all_players(code, interaction.guild)


@bot.tree.command(name="addplayerid", description="Register your Whiteout Survival player ID.")
@app_commands.describe(player_id="Your Whiteout Survival player ID")
async def addplayerid_cmd(interaction: discord.Interaction, player_id: str):
    player_ids[str(interaction.user.id)] = player_id.strip()
    save_json(PLAYER_IDS_FILE, player_ids)
    await interaction.response.send_message(
        f"Your player ID `{player_id}` has been saved for automatic gift code claiming (when implemented).",
        ephemeral=True,
    )


# ------------- GAMES -------------

@bot.tree.command(name="guessnumber", description="Play a guess-the-number game (1-100).")
async def guessnumber_cmd(interaction: discord.Interaction):
    import random
    secret = random.randint(1, 100)
    guess_games[interaction.user.id] = secret
    await interaction.response.send_message(
        "I've picked a number between 1 and 100. Use `/guess <number>` to try!",
        ephemeral=True,
    )


@bot.tree.command(name="guess", description="Guess the number for the current game.")
@app_commands.describe(number="Your guess between 1 and 100")
async def guess_cmd(interaction: discord.Interaction, number: int):
    secret = guess_games.get(interaction.user.id)
    if not secret:
        await interaction.response.send_message("You don't have an active game. Use `/guessnumber` first.", ephemeral=True)
        return
    if number < secret:
        await interaction.response.send_message("Too low! Try again.", ephemeral=True)
    elif number > secret:
        await interaction.response.send_message("Too high! Try again.", ephemeral=True)
    else:
        await interaction.response.send_message("🎉 Correct! You guessed the number!", ephemeral=True)
        del guess_games[interaction.user.id]


@bot.tree.command(name="blackjack", description="Play a simple Blackjack game vs the dealer.")
async def blackjack_cmd(interaction: discord.Interaction):
    import random

    def draw_card():
        ranks = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
        return random.choice(ranks)

    def hand_value(cards: List[str]) -> int:
        total = 0
        aces = 0
        for c in cards:
            if c in ["J", "Q", "K"]:
                total += 10
            elif c == "A":
                total += 11
                aces += 1
            else:
                total += int(c)
        while total > 21 and aces > 0:
            total -= 10
            aces -= 1
        return total

    player = [draw_card(), draw_card()]
    dealer = [draw_card(), draw_card()]

    p_val = hand_value(player)
    d_val = hand_value(dealer)

    result_lines = [
        f"Your hand: {', '.join(player)} (total {p_val})",
        f"Dealer hand: {', '.join(dealer)} (total {d_val})",
    ]

    if p_val > 21 and d_val > 21:
        result_lines.append("Both busted. It's a draw.")
    elif p_val > 21:
        result_lines.append("You busted. Dealer wins.")
    elif d_val > 21:
        result_lines.append("Dealer busted. You win! 🎉")
    elif p_val > d_val:
        result_lines.append("You win! 🎉")
    elif p_val < d_val:
        result_lines.append("Dealer wins.")
    else:
        result_lines.append("It's a tie.")

    await interaction.response.send_message("\n".join(result_lines), ephemeral=True)


# ------------- TRANSLATION COMMAND -------------

@bot.tree.command(name="translate", description="Translate text into your language.")
@app_commands.describe(text="The text you want translated")
async def translate_cmd(interaction: discord.Interaction, text: str):
    lang_code = get_user_language_code(interaction.user)
    translated = await translator.translate(text, target_lang=lang_code)
    await interaction.response.send_message(
        f"🌐 Translation to your language ({lang_code}):\n{translated}",
        ephemeral=True,
    )


# ------------- HELP -------------

@bot.tree.command(name="help_papamike", description="Show help for PapaMike Translator bot.")
async def help_cmd(interaction: discord.Interaction):
    desc = (
        "**PapaMike Translator Bot – Help**\n\n"
        "🛂 **Verification & Roles**\n"
        "- Click the **Start Verification ✅** button in the verify channel to open the form.\n"
        "- `/verify` – backup command to open the verification form.\n"
        "- Alliance, language and age roles are auto-assigned from your answers.\n\n"
        "🌐 **Translation**\n"
        "- Auto-logs translations of global and alliance chats into English for leaders.\n"
        "- `/translate <text>` – translate any text into your language.\n\n"
        "🎁 **Gift Codes**\n"
        "- `/addplayerid <id>` – register your WOS player ID.\n"
        "- `/addcode <code>` – (admins only) register a new gift code.\n\n"
        "🔥 **Furnace**\n"
        "- Post your furnace upgrades in 🔥｜furnace-upgrades, bot will celebrate them.\n\n"
        "🎮 **Games**\n"
        "- `/guessnumber` – start a guess-the-number (1–100) game.\n"
        "- `/guess <number>` – make a guess.\n"
        "- `/blackjack` – simple blackjack vs dealer.\n\n"
        "📊 **Participation & Activity**\n"
        "- Bot tracks participation milestones and kicks inactive users after 30 days."
    )
    await interaction.response.send_message(desc, ephemeral=True)


# ------------- GLOBAL ERROR HANDLING -------------

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    await log_to(CONFIG["channels"]["bot_errors"], f"Slash command error: `{error}`")
    if not interaction.response.is_done():
        try:
            await interaction.response.send_message(
                "⚠️ An error occurred while running that command. Please contact an admin.",
                ephemeral=True,
            )
        except Exception:
            pass


# ------------- RUN -------------

async def main():
    token = os.getenv("DISCORD_BOT_TOKEN") or os.getenv("DISCORD_TOKEN")
    if not token:
        print("ERROR: Please set DISCORD_BOT_TOKEN environment variable.")
        return
    async with bot:
        await translator.start()
        try:
            await bot.start(token)
        finally:
            await translator.close()


if __name__ == "__main__":
    ensure_data_files()
    asyncio.run(main())
