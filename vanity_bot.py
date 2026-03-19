import os
import discord
from discord.ext import commands

#  CONFIG

TOKEN = os.environ.get("DISCORD_TOKEN")

# The vanity string to watch for in statuses (case-insensitive)
VANITY = "/matter"

# ID of the role to give when someone reps the vanity
REP_ROLE_ID = 1476355744851955864

# ID of the channel where the thank-you message is sent
REP_CHANNEL_ID = 1480023034399031429

# Customise the message below.
# Available placeholders:
#   {user}    — mention the member  e.g. @Someone
#   {vanity}  — the vanity string   e.g. /matter
#   {name}    — the member's display name
REP_MESSAGE = "thanks for repping {vanity} {name}!! 🎉"

# ---- BOOST CONFIG ----

# ID of the channel where boost messages are sent
BOOST_CHANNEL_ID = 1480023034399031429  # 🔁 replace with your boost channel ID

# Customise the boost message below.
# Available placeholders:
#   {user}         — mention the member       e.g. @Someone
#   {name}         — the member's display name
#   {boost_count}  — total server boost count
#   {boost_tier}   — current boost tier (0–3)
BOOST_MESSAGE = "thank you for boosting {user}!!  we're now at **{boost_count}** boosts!"

# ---- END BOOST CONFIG ----

#  setup

intents = discord.Intents.default()
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Tracks members who have EVER repped the vanity this session.
# The role itself is the persistent source of truth across restarts.
_already_repped: set[int] = set()


def status_contains_vanity(member: discord.Member) -> bool:
    """Return True if any of the member's activities contain the vanity."""
    for activity in member.activities:
        if isinstance(activity, discord.CustomActivity):
            if activity.name and VANITY.lower() in activity.name.lower():
                return True
        elif hasattr(activity, "name") and activity.name:
            if VANITY.lower() in activity.name.lower():
                return True
    return False


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"Watching for vanity: {VANITY!r}")

    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Activity(type=discord.ActivityType.watching, name=".gg/matter")
    )

    # Pre-populate _already_repped from current role holders so we never
    # re-announce or re-ping someone who already has the role.
    for guild in bot.guilds:
        role = guild.get_role(REP_ROLE_ID)
        if role:
            for member in role.members:
                _already_repped.add(member.id)

    print(f"Pre-loaded {len(_already_repped)} existing rep holders.")


@bot.event
async def on_presence_update(before: discord.Member, after: discord.Member):
    """Fires whenever a guild member's presence changes."""

    # Only react when the vanity status text itself changes,
    # not when someone just comes online/offline with it already set.
    had_vanity = status_contains_vanity(before)
    has_vanity = status_contains_vanity(after)

    # Member just ADDED the vanity — only reward if we haven't already
    if not had_vanity and has_vanity:
        if after.id not in _already_repped:
            await reward_member(after)

    # Member REMOVED the vanity — strip the role
    elif had_vanity and not has_vanity:
        if after.id in _already_repped:
            await remove_reward(after)


@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    """Fires whenever a guild member's profile changes — catches new boosts."""
    if before.premium_since is None and after.premium_since is not None:
        await handle_boost(after)


async def handle_boost(member: discord.Member):
    """Send a thank-you message when a member boosts the server."""
    guild = member.guild
    channel = guild.get_channel(BOOST_CHANNEL_ID)

    if channel:
        msg = BOOST_MESSAGE.format(
            user=member.mention,
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
    else:
        print(f"[WARN] Could not find boost channel ID {BOOST_CHANNEL_ID}")


async def reward_member(member: discord.Member):
    """Give the role and send the thank-you message — only fires once per member."""
    guild = member.guild

    # Add to session set FIRST so no duplicate fires can sneak through
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
            user=member.mention,
            vanity=VANITY,
            name=member.display_name,
        )
        try:
            await channel.send(msg)
        except discord.Forbidden:
            print(f"[WARN] Missing permissions to send message in {channel}")
        except discord.HTTPException as e:
            print(f"[ERROR] Failed to send message: {e}")
    else:
        print(f"[WARN] Could not find channel ID {REP_CHANNEL_ID}")


async def remove_reward(member: discord.Member):
    """Remove the role when the member stops repping."""
    guild = member.guild
    role = guild.get_role(REP_ROLE_ID)

    if role and role in member.roles:
        try:
            await member.remove_roles(role, reason="No longer repping vanity")
        except discord.Forbidden:
            print(f"[WARN] Missing permissions to remove role from {member}")
        except discord.HTTPException as e:
            print(f"[ERROR] Failed to remove role: {e}")

    # Clear from session set — if they re-add the vanity later they'll be
    # welcomed back, but only once per vanity-add, not on every login
    _already_repped.discard(member.id)


# extra cmds (!)

@bot.command()
@commands.has_permissions(administrator=True)
async def sync(ctx):
    """Sync slash commands (run once after adding new slash commands)."""
    synced = await bot.tree.sync()
    await ctx.send(f"Synced {len(synced)} command(s).")


# run

if __name__ == "__main__":
    bot.run(TOKEN)
