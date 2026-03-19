import os
import discord
from discord.ext import commands

# ---- CONFIG ----

TOKEN = os.environ.get("DISCORD_TOKEN")

# Vanity config
VANITY = "/matter"
REP_ROLE_ID = 1476355744851955864
REP_CHANNEL_ID = 1480023034399031429
REP_MESSAGE = "thanks for repping {vanity} {name}!! 🎉"  # display name only, no ping

# Boost config
BOOST_CHANNEL_ID = 1480023034399031429
BOOST_MESSAGE = "thank you for boosting {user}!! we're now at **{boost_count}** boosts!"

# ---- BOT SETUP ----

intents = discord.Intents.default()
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Track members who already got the vanity role this session
_already_repped: set[int] = set()


# ---- HELPERS ----

def status_contains_vanity(member: discord.Member) -> bool:
    """Return True if member's activities contain the vanity string."""
    for activity in member.activities:
        if hasattr(activity, "name") and activity.name:
            if VANITY.lower() in activity.name.lower():
                return True
    return False


# ---- EVENTS ----

@bot.event
async def on_ready():
    print(".gg/matter <3 coded by carve!!")

    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Activity(type=discord.ActivityType.watching, name=".gg/matter")
    )

    # Pre-load members who already have the role
    for guild in bot.guilds:
        role = guild.get_role(REP_ROLE_ID)
        if role:
            for member in role.members:
                _already_repped.add(member.id)


@bot.event
async def on_presence_update(before: discord.Member, after: discord.Member):
    """Check for vanity added or removed."""
    had_vanity = status_contains_vanity(before)
    has_vanity = status_contains_vanity(after)

    if not had_vanity and has_vanity and after.id not in _already_repped:
        await reward_member(after)
    elif had_vanity and not has_vanity and after.id in _already_repped:
        await remove_reward(after)


@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    """Check for new server boosts."""
    if before.premium_since is None and after.premium_since is not None:
        await handle_boost(after)


# ---- ACTIONS ----

async def reward_member(member: discord.Member):
    """Give vanity role and post a message (no ping)."""
    guild = member.guild
    _already_repped.add(member.id)

    role = guild.get_role(REP_ROLE_ID)
    if role and role not in member.roles:
        try:
            await member.add_roles(role, reason="Repping vanity in status")
        except discord.Forbidden:
            print(f"[WARN] Missing permissions to add role to {member}")
        except discord.HTTPException as e:
            print(f"[ERROR] Failed to add role: {e}")

    channel = guild.get_channel(REP_CHANNEL_ID)
    if channel:
        msg = REP_MESSAGE.format(
            vanity=VANITY,
            name=member.display_name,  # name only, no ping
        )
        try:
            await channel.send(msg)
        except discord.Forbidden:
            print(f"[WARN] Missing permissions to send message in {channel}")
        except discord.HTTPException as e:
            print(f"[ERROR] Failed to send message: {e}")


async def remove_reward(member: discord.Member):
    """Remove vanity role if user removes vanity from status."""
    guild = member.guild
    role = guild.get_role(REP_ROLE_ID)

    if role and role in member.roles:
        try:
            await member.remove_roles(role, reason="No longer repping vanity")
        except discord.Forbidden:
            print(f"[WARN] Missing permissions to remove role from {member}")
        except discord.HTTPException as e:
            print(f"[ERROR] Failed to remove role: {e}")

    _already_repped.discard(member.id)


async def handle_boost(member: discord.Member):
    """Thank someone for boosting (still pings)."""
    guild = member.guild
    channel = guild.get_channel(BOOST_CHANNEL_ID)

    if channel:
        msg = BOOST_MESSAGE.format(
            user=member.mention,  # still pings
            name=member.display_name,
            boost_count=guild.premium_subscription_count,
            boost_tier=guild.premium_tier,
        )
        try:
            await channel.send(msg)
        except discord.Forbidden:
            print(f"[WARN] Missing permissions to send boost message in {channel}")
        except discord.HTTPException as e:
            print(f"[ERROR] Failed to send boost message: {e}")


# ---- COMMANDS ----

@bot.command()
@commands.has_permissions(administrator=True)
async def sync(ctx):
    """Sync slash commands."""
    synced = await bot.tree.sync()
    await ctx.send(f"Synced {len(synced)} command(s).")


# ---- RUN ----

if __name__ == "__main__":
    bot.run(TOKEN)
