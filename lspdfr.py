import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.utils import get
from collections import defaultdict
import re
import asyncio
from datetime import datetime, timedelta, date
import os
import random
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import aiohttp
import json
import datetime as dt

#  Set up intents
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.guild_messages = True
intents.guild_reactions = True
intents.bans = True
intents.guild_scheduled_events = True
intents.message_content = True
intents.messages = True
intents.presences = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Configuration constants
MESSAGE_LIMIT = 5
TIME_LIMIT = 5
MENTION_LIMIT = 3
ALERT_CHANNEL_ID = 1295817089835077734
SERVER_ID = 1285673125752864851
RESTRICTED_ROLE_NAME = "Restricted"
#BIRTHDAY_CHANNEL_ID = 1347611607353659432
LEVEL_UP_CHANNEL_ID = 1347611011145793620
invite_log_channel_id = 1293674727264751616
TARGET_GUILD_ID = "1285673125752864851"
ALLOWED_SERVER_ID = 1285673125752864851
ALLOWED_USER_IDS = [1334573917985050805, 1146025667218124853, 792613567189745696]


guild_invites = {}

@bot.command()
async def sendfile(ctx):
    if ctx.guild and ctx.guild.id == ALLOWED_SERVER_ID and ctx.author.id in ALLOWED_USER_IDS:
        try:
            file_path = 'xp.json'  
            await ctx.send(file=discord.File(file_path))
        except Exception as e:
            print(f"Error sending file: {e}")



# File paths
#BIRTHDAY_FILE = "birthday.json"
XP_FILE = "xp.json"


# Initialize variables
join_times = {SERVER_ID: []}
verification_config = {}
tree = bot.tree

# =================== FILE UTILITIES ===================
def ensure_files_exist():
    if not os.path.exists(XP_FILE):
        with open(XP_FILE, "w") as f:
            json.dump({}, f)



# =================== XP SYSTEM ===================
def load_xp_data():
    with open(XP_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_xp_data(data):
    with open(XP_FILE, "w") as f:
        json.dump(data, f, indent=4)

# Modified XP calculation with new level requirements
def calculate_level(xp):
    total_xp = xp
    level = 0
    
    # First level requires 25 XP
    if total_xp >= 25:
        total_xp -= 25
        level += 1
        
        # Subsequent levels follow 100 + (level-2)*50 pattern
        while True:
            if level == 1:
                xp_needed = 100  # Level 2 needs 100 XP
            else:
                xp_needed = 100 + ((level-1) * 50)  # Level 3+: 150, 200, 250, etc.
                
            if total_xp >= xp_needed:
                total_xp -= xp_needed
                level += 1
            else:
                break
    
    return level

def calculate_xp_for_next_level(level):
    if level == 0:
        return 25  # First level needs 25 XP
    elif level == 1:
        return 100  # Second level needs 100 XP
    else:
        return 100 + ((level) * 50)  # Level 3+: 150, 200, 250, etc.

async def add_xp(user_id, guild_id, amount):
    # Only process XP for the specific server
    if str(guild_id) != TARGET_GUILD_ID:
        return False, 0
        
    xp_data = load_xp_data()
    
    # Initialize guild data if it doesn't exist
    if str(guild_id) not in xp_data:
        xp_data[str(guild_id)] = {}
    
    # Initialize user data if it doesn't exist
    if str(user_id) not in xp_data[str(guild_id)]:
        xp_data[str(guild_id)][str(user_id)] = {"xp": 0}
    
    # Get current XP and level
    current_xp = xp_data[str(guild_id)][str(user_id)]["xp"]
    current_level = calculate_level(current_xp)
    
    # Add XP
    xp_data[str(guild_id)][str(user_id)]["xp"] = current_xp + amount
    
    # Check if user leveled up
    new_level = calculate_level(xp_data[str(guild_id)][str(user_id)]["xp"])
    
    save_xp_data(xp_data)
    
    if new_level > current_level:
        return True, new_level
    
    return False, 0

def get_user_rank(user_id, guild_id):
    # Only process rank for the specific server
    if str(guild_id) != TARGET_GUILD_ID:
        return 0, 0, 0, 0, 0
        
    xp_data = load_xp_data()
    
    if str(guild_id) not in xp_data:
        return 0, 0, 0, 0, 0
    
    if str(user_id) not in xp_data[str(guild_id)]:
        return 0, 0, 0, 0, 0
    
    # Get user XP
    total_xp = xp_data[str(guild_id)][str(user_id)]["xp"]
    user_level = calculate_level(total_xp)
    
    # Calculate XP for the current level
    xp_spent = 0
    if user_level > 0:
        xp_spent = 25  # First level cost
        
        for level in range(1, user_level):
            if level == 1:
                xp_spent += 100  # Second level cost
            else:
                xp_spent += 100 + ((level-1) * 50)  # Level 3+ costs
    
    # Current level XP progress
    xp_progress = total_xp - xp_spent
    xp_needed = calculate_xp_for_next_level(user_level)
    
    # Calculate user's rank position
    sorted_users = sorted(
        xp_data[str(guild_id)].items(), 
        key=lambda x: x[1]["xp"], 
        reverse=True
    )
    
    rank_position = 0
    for i, (uid, _) in enumerate(sorted_users):
        if uid == str(user_id):
            rank_position = i + 1
            break
    
    return total_xp, user_level, xp_progress, xp_needed, rank_position


async def generate_rank_card(user, guild_id):
    user_xp, user_level, xp_progress, xp_needed, rank_position = get_user_rank(user.id, guild_id)
    
    # ============ CONFIGURABLE VALUES - ADJUST THESE AS NEEDED ============
    # Font sizes
    TITLE_FONT_SIZE = 280     # For rank/level numbers
    REGULAR_FONT_SIZE = 170   # For username
    SMALL_FONT_SIZE = 75      # For XP text
    
    # Avatar settings
    AVATAR_SIZE = 610         # Size of the avatar
    AVATAR_X = 155            # X position of avatar
    AVATAR_Y = 245            # Y position of avatar
    
    # Status circle settings
    STATUS_CIRCLE_SIZE = 150  # Size of the status circle
    STATUS_CIRCLE_X = 650     # X position of status circle (centered with avatar)
    STATUS_CIRCLE_Y = 670     # Y position of status circle (below avatar)
    STATUS_OUTLINE_WIDTH = 8  # Width of the black outline
    
    # Status circle colors
    STATUS_COLORS = {
        discord.Status.online: (67, 181, 129, 255),    # Green
        discord.Status.idle: (250, 166, 26, 255),      # Yellow
        discord.Status.dnd: (240, 71, 71, 255),        # Red
        discord.Status.offline: (116, 127, 141, 255),  # Grey
        None: (116, 127, 141, 255)                     # Default grey
    }
    
    # Username text position
    USERNAME_X = 1000         # X position of username
    USERNAME_Y = 490          # Y position of username
    
    # XP text position (below username)
    XP_TEXT_X = 3000          # X position of XP text
    XP_TEXT_Y = 600           # Y position of XP text
    
    # Rank number position (top right)
    RANK_NUM_X_OFFSET = 1350  # Distance from right edge
    RANK_NUM_Y = 150          # Y position of rank number
    
    # Level number position (below rank)
    LEVEL_NUM_X_OFFSET = 480  # Distance from right edge
    LEVEL_NUM_Y = 150         # Y position of level number
    LEVEL_COLOR = (255, 215, 0, 255)  # Yellow/gold color
    
    # Progress bar settings
    BAR_X = 985               # X position of progress bar
    BAR_Y = 710               # Y position of progress bar
    BAR_WIDTH = 2400          # Width of progress bar
    BAR_HEIGHT = 120          # Height of progress bar
    BAR_RADIUS = 70           # Corner radius of progress bar
    BAR_COLOR = (255, 215, 0, 255)  # Yellow/gold color with transparency
    # ====================================================================
    
    # Load the base image
    try:
        base_image = Image.open("rankcard.png").convert("RGBA")
        card_width, card_height = base_image.size
    except FileNotFoundError:
        print("Error: rankcard.png not found!")
        return None
    
    draw = ImageDraw.Draw(base_image)
    
    # Load fonts
    try:
        title_font = ImageFont.truetype("fonts/montserrat/Montserrat-Bold.ttf", TITLE_FONT_SIZE)
        regular_font = ImageFont.truetype("fonts/montserrat/Montserrat-Medium.ttf", REGULAR_FONT_SIZE)
        small_font = ImageFont.truetype("fonts/montserrat/Montserrat-Medium.ttf", SMALL_FONT_SIZE)
    except IOError:
        # Fallback to default font
        title_font = ImageFont.truetype("arial.ttf", TITLE_FONT_SIZE)
        regular_font = ImageFont.truetype("arial.ttf", REGULAR_FONT_SIZE)
        small_font = ImageFont.truetype("arial.ttf", SMALL_FONT_SIZE)
    
    # Download and process user avatar
    async with aiohttp.ClientSession() as session:
        avatar_url = user.avatar.url if user.avatar else user.default_avatar.url
        async with session.get(str(avatar_url)) as resp:
            if resp.status == 200:
                avatar_data = await resp.read()
                avatar = Image.open(BytesIO(avatar_data))
                
                # Resize avatar
                avatar = avatar.resize((AVATAR_SIZE, AVATAR_SIZE))
                
                # Create circular mask
                mask = Image.new("L", (AVATAR_SIZE, AVATAR_SIZE), 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.ellipse((0, 0, AVATAR_SIZE, AVATAR_SIZE), fill=255)
                
                # Apply mask to make avatar circular
                circle_avatar = Image.new("RGBA", (AVATAR_SIZE, AVATAR_SIZE))
                circle_avatar.paste(avatar, (0, 0), mask)
                
                # Place avatar
                base_image.paste(circle_avatar, (AVATAR_X, AVATAR_Y), circle_avatar)
    
    # Draw the status circle below avatar
    status_color = STATUS_COLORS.get(user.status, STATUS_COLORS[None])
    
    # Create a new image for the status circle with alpha channel
    status_circle = Image.new("RGBA", (STATUS_CIRCLE_SIZE, STATUS_CIRCLE_SIZE), (0, 0, 0, 0))
    status_draw = ImageDraw.Draw(status_circle)
    
    # Draw black outline first (slightly larger circle)
    status_draw.ellipse((0, 0, STATUS_CIRCLE_SIZE, STATUS_CIRCLE_SIZE), fill=(0, 0, 0, 255))
    
    # Draw the inner circle with the status color (slightly smaller to create outline effect)
    inner_offset = STATUS_OUTLINE_WIDTH
    status_draw.ellipse(
        (inner_offset, inner_offset, STATUS_CIRCLE_SIZE - inner_offset, STATUS_CIRCLE_SIZE - inner_offset), 
        fill=status_color
    )
    
    # Place the status circle
    base_image.paste(status_circle, (STATUS_CIRCLE_X, STATUS_CIRCLE_Y), status_circle)
    
    # Draw username
    draw.text((USERNAME_X, USERNAME_Y), user.name.lower(), fill=(255, 255, 255, 255), font=regular_font)
    
    # Draw XP text
    xp_text = f"{xp_progress}/{xp_needed} XP"
    draw.text((XP_TEXT_X, XP_TEXT_Y), xp_text, fill=(220, 220, 220, 255), font=small_font)
    
    # Draw rank number (with # symbol)
    rank_num_x = card_width - RANK_NUM_X_OFFSET
    draw.text((rank_num_x, RANK_NUM_Y), f"#{rank_position}", fill=(255, 255, 255, 255), font=title_font)
    
    # Draw level number
    level_num_x = card_width - LEVEL_NUM_X_OFFSET
    draw.text((level_num_x, LEVEL_NUM_Y), str(user_level), fill=LEVEL_COLOR, font=title_font)
    
    # Draw progress bar
    if xp_needed > 0:
        progress = xp_progress / xp_needed
        progress_width = int(BAR_WIDTH * progress)
        if progress_width > 0:
            draw.rounded_rectangle(
                [BAR_X, BAR_Y, BAR_X + progress_width, BAR_Y + BAR_HEIGHT],
                radius=BAR_RADIUS,
                fill=BAR_COLOR
            )
    
    # Convert to bytes
    buffer = BytesIO()
    base_image.save(buffer, format="PNG")
    buffer.seek(0)
    
    return buffer
    
# =================== COMMANDS ===================
@bot.command()
@commands.has_permissions(administrator=True)
async def unmute(ctx, member: discord.Member):
    muted_role = discord.utils.get(ctx.guild.roles, name="Muted")
    if muted_role in member.roles:
        await member.remove_roles(muted_role)
        await ctx.send(f"{member.mention} has been unmuted.")
    else:
        await ctx.send(f"{member.mention} is not muted.")


@bot.tree.command(name="setup_verification", description="Set up user verification system.")
@app_commands.default_permissions(administrator=True)
async def setup_verification(interaction: discord.Interaction):
    guild_id = interaction.guild.id

    # Check or create the "unverified" role
    unverified_role = discord.utils.get(interaction.guild.roles, name="unverified")
    if unverified_role is None:
        unverified_role = await interaction.guild.create_role(name="unverified", reason="Created unverified role for verification system")

    # Set up permissions for the "verify" channel
    overwrites = {
        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        unverified_role: discord.PermissionOverwrite(view_channel=True),
    }

    # Check or create the "verify" channel
    verify_channel = discord.utils.get(interaction.guild.text_channels, name="verify")
    if verify_channel is None:
        verify_channel = await interaction.guild.create_text_channel('verify', overwrites=overwrites, reason="Created verify channel for verification system")

    # Create the embed message
    embed = discord.Embed(
        title="Welcome to the Server!",
        description="Please verify yourself by clicking the button below.",
        color=discord.Color.blue()
    )

    # Send verification message with persistent button and embed
    verify_button = VerifyButton()
    await verify_channel.send(embed=embed, view=verify_button)

    await interaction.response.send_message("Verification system setup successfully! Users will be verified by removing the 'unverified' role.", ephemeral=True)

@bot.tree.command(name="rank", description="Display your current rank and level")
@app_commands.describe(user="The user whose rank you want to check")
async def rank(interaction: discord.Interaction, user: discord.User = None):
    # Check if command is used in the specific server
    if str(interaction.guild_id) != TARGET_GUILD_ID:
        await interaction.response.send_message("❌ The rank system is not available in this server.", ephemeral=True)
        return
        
    target_user = user or interaction.user
    
    xp_data = load_xp_data()
    if str(interaction.guild_id) not in xp_data or str(target_user.id) not in xp_data[str(interaction.guild_id)]:
        await interaction.response.send_message("❌ This user has no XP records yet.", ephemeral=True)
        return
    
    # Defer the response to prevent timeout
    await interaction.response.defer()
    
    # Get the member object instead of user to access status
    guild = interaction.guild
    target_member = guild.get_member(target_user.id)
    
    # Generate rank card
    rank_card = await generate_rank_card(target_member or target_user, interaction.guild_id)
    
    if rank_card is None:
        await interaction.followup.send("❌ Failed to generate rank card. Make sure the rankcard.png file exists.")
        return
    
    # Send the image as a followup since we already deferred
    await interaction.followup.send(file=discord.File(fp=rank_card, filename="rank.png"))


# =================== BOT EVENTS ===================
@bot.event
async def on_ready():
    print(f"Bot is ready. Logged in as {bot.user}")  
    bot.add_view(VerifyButton())
    try:
        synced = await tree.sync()  # Sync commands again
        print(f"Synced {len(synced)} commands!")
    except Exception as e:
        print(f"Error syncing commands: {e}")
    ensure_files_exist()
    for guild in bot.guilds:
        if guild.id == SERVER_ID:
            try:
                # Fetch all invites for the guild and store them
                guild_invites[guild.id] = await guild.invites()
                print(f'Cached invites for {guild.name}')
            except discord.Forbidden:
                print(f'No permission to fetch invites for {guild.name}')
            except Exception as e:
                print(f'Error caching invites for {guild.name}: {e}')


@bot.event
async def on_invite_create(invite):   
    if invite.guild.id == SERVER_ID:
        guild_invites.setdefault(invite.guild.id, [])
        guild_invites[invite.guild.id].append(invite)

@bot.event
async def on_invite_delete(invite):    
    if invite.guild.id == SERVER_ID and invite.guild.id in guild_invites:
        guild_invites[invite.guild.id] = [inv for inv in guild_invites[invite.guild.id] if inv.code != invite.code]


@bot.event
async def on_guild_channel_delete(channel):
    # Get the audit log entry for channel deletion
    guild = channel.guild
    async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
        if entry.user.guild_permissions.manage_channels:  # Check if the deleter had permission to manage channels
            await ban_member(guild, entry.user, reason=f"Deleted channel: {channel.name}")
            break

@bot.event
async def on_guild_role_delete(role):
    # Get the audit log entry for role deletion
    guild = role.guild
    
    # First check if this role deletion was due to a bot kick/ban
    try:
        # Check recent kick audit logs
        async for kick_entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.kick):
            # If a bot was kicked recently (within 5 seconds)
            if (discord.utils.utcnow() - kick_entry.created_at).total_seconds() < 5:
                if hasattr(kick_entry.target, 'bot') and kick_entry.target.bot:
                    print(f"Role {role.name} was likely deleted due to bot {kick_entry.target} being kicked - not banning anyone")
                    return
        
        # Check recent ban audit logs
        async for ban_entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.ban):
            # If a bot was banned recently (within 5 seconds)
            if (discord.utils.utcnow() - ban_entry.created_at).total_seconds() < 5:
                if hasattr(ban_entry.target, 'bot') and ban_entry.target.bot:
                    print(f"Role {role.name} was likely deleted due to bot {ban_entry.target} being banned - not banning anyone")
                    return
                    
        # Check if the role was an integration role (bot role)
        if role.managed:
            print(f"Role {role.name} was a managed integration role - not banning anyone")
            return
            
        # If we get here, proceed with normal ban logic for manual role deletion
        # But make sure we're banning the actual person who deleted the role
        role_delete_entry = None
        async for entry in guild.audit_logs(limit=1, action=discord.AuditLogAction.role_delete):
            role_delete_entry = entry
            break
            
        if role_delete_entry and role_delete_entry.user.guild_permissions.manage_roles:
            # Double check that this entry is for the current role
            if role_delete_entry.target.id == role.id:
                await ban_member(guild, role_delete_entry.user, reason=f"Deleted role: {role.name}")
            else:
                print(f"Role deletion audit log entry doesn't match the deleted role - not banning anyone")
    except Exception as e:
        print(f"Error in role deletion handler: {e}")

@bot.event
async def on_member_join(member):
    guild = member.guild
    unverified_role = discord.utils.get(member.guild.roles, name="unverified")
    
    # Automatically assign the "unverified" role to new members
    if unverified_role:
        await member.add_roles(unverified_role)

    # Check if the join event is in the specific guild
    if guild.id != SERVER_ID:
        return  # Ignore joins from other servers
    invite_log_channel = member.guild.get_channel(invite_log_channel_id)
    if not invite_log_channel:
        print(f"Couldn't find invite log channel for {member.guild.name}")
        return
    
    # Try to find which invite was used
    inviter_name = "Unknown"
    invite_code = "Unknown"
    invite_uses = 0
    
    try:
        # Get the invites before the user joined
        invites_before = guild_invites.get(member.guild.id, [])
        
        # Get the invites after the user joined
        invites_after = await member.guild.invites()
        
        # Update our cache
        guild_invites[member.guild.id] = invites_after
        
        # Find the invite that was used
        for invite_after in invites_after:
            # Find invite before with the same code
            invite_before = next((inv for inv in invites_before if inv.code == invite_after.code), None)
            
            # If the invite didn't exist before or its uses increased, this is the one used
            if invite_before is None or invite_before.uses < invite_after.uses:
                inviter_name = invite_after.inviter.name if invite_after.inviter else "Unknown"
                invite_code = invite_after.code
                invite_uses = invite_after.uses
                break
    except Exception as e:
        print(f"Error tracking invite for {member.name}: {e}")
    
    # Format the account creation date
    account_created = member.created_at
    # Keep the datetime as offset-aware and ensure both are in UTC
    account_age = dt.datetime.now(dt.timezone.utc) - account_created
    years = account_age.days // 365
    months = (account_age.days % 365) // 30
    account_age_str = f"{years} year{'s' if years != 1 else ''}, {months} month{'s' if months != 1 else ''} ago"
    
    # Format the creation timestamp
    created_timestamp = account_created.strftime('%d/%m/%Y, %H:%M:%S')
    
    # Get total guild members
    total_members = member.guild.member_count
    
    # Create the embed message
    embed = discord.Embed(color=0x00ff00)
    embed.set_author(name="LSPDFR Hangout", icon_url=bot.user.avatar.url if bot.user.avatar else None)
    
    # Format the message similar to the image
    description = f"→ {member.mention} has been invited by {inviter_name} using invite code: {invite_code} ({invite_uses} uses).\n"
    description += f"Total guild members: {total_members}.\n"
    description += f"👤 {member.name} - {member.id} ~ Account created on {created_timestamp} which is {account_age_str}\n"
    
    # Add inviter info if available
    if inviter_name != "Unknown":
        inviter = next((inv.inviter for inv in guild_invites[member.guild.id] if inv.code == invite_code), None)
        if inviter:
            # Count how many people this inviter has invited
            invited_count = sum(1 for inv in guild_invites[member.guild.id] if inv.inviter and inv.inviter.id == inviter.id)
            description += f"👤 {inviter_name} - {inviter.id} has invited {invited_count} people."
    
    embed.description = description
    
    # Send the embed to the invite log channel
    await invite_log_channel.send(embed=embed)

    # Append the current join time to the list for the specific guild
    join_times[guild.id].append(discord.utils.utcnow())  # Only append once!

    # Filter join times within the last minute
    join_times[guild.id] = [
        time for time in join_times[guild.id] 
        if (discord.utils.utcnow() - time).total_seconds() < 60
    ]

    # Trigger alert if there are more than 2 joins within 1 minute
    if len(join_times[guild.id]) > 2:
        alert_channel = bot.get_channel(ALERT_CHANNEL_ID)
        if alert_channel:
            await alert_channel.send(
                f"⚠️ Raid alert! More than 2 users have joined {guild.name} in the past minute. <@&1285678703099117580>"
            )

@bot.event
async def on_message(message):
    # Ignore messages from bots
    if message.author.bot:
        return

    # ----- Spam Detection: Mention Spam -----
    total_mentions = message.content.count('@')
    if total_mentions > MENTION_LIMIT:
        print(f"User {message.author} is spamming mentions. Proceeding to mute.")
        muted_role = discord.utils.get(message.guild.roles, name="Muted")
        if muted_role is None:
            print("Muted role not found, creating one...")
            muted_role = await message.guild.create_role(
                name="Muted",
                permissions=discord.Permissions(send_messages=False, speak=False)
            )
            # Set permissions in all channels
            for channel in message.guild.channels:
                await channel.set_permissions(muted_role, send_messages=False, speak=False)
            print("Muted role created and permissions set for all channels.")
        
        if muted_role not in message.author.roles:
            try:
                await message.author.add_roles(muted_role)
                await message.channel.send(f"{message.author.mention} has been muted for 2 hours due to spamming mentions.")
                print(f"Muted role applied to user {message.author}.")
                bot.loop.call_later(2 * 60 * 60, lambda: asyncio.create_task(unmute_member(message.author, muted_role)))
            except discord.Forbidden:
                print(f"Bot doesn't have permission to assign roles to {message.author}.")
            except discord.HTTPException as e:
                print(f"Failed to assign muted role due to HTTP error: {e}")
        else:
            print(f"User {message.author} is already muted.")

    # ----- Spam Detection: Message Spam -----
    time_frame = discord.utils.utcnow() - timedelta(seconds=TIME_LIMIT)
    recent_messages = [msg async for msg in message.channel.history(limit=100, after=time_frame)]
    user_message_count = sum(1 for msg in recent_messages if msg.author == message.author)
    
    if user_message_count > MESSAGE_LIMIT:
        print(f"User {message.author} is spamming. Proceeding to mute.")
        muted_role = discord.utils.get(message.guild.roles, name="Muted")
        if muted_role is None:
            print("Muted role not found, creating one...")
            muted_role = await message.guild.create_role(
                name="Muted",
                permissions=discord.Permissions(send_messages=False, speak=False)
            )
            # Set permissions in all channels
            for channel in message.guild.channels:
                await channel.set_permissions(muted_role, send_messages=False, speak=False)
            print("Muted role created and permissions set for all channels.")
        
        if muted_role not in message.author.roles:
            try:
                await message.author.add_roles(muted_role)
                await message.channel.send(f"{message.author.mention} has been muted for 2 hours due to spamming.")
                print(f"Muted role applied to user {message.author}.")
                bot.loop.call_later(2 * 60 * 60, lambda: asyncio.create_task(unmute_member(message.author, muted_role)))
            except discord.Forbidden:
                print(f"Bot doesn't have permission to assign roles to {message.author}.")
            except discord.HTTPException as e:
                print(f"Failed to assign muted role due to HTTP error: {e}")
        else:
            print(f"User {message.author} is already muted.")

    # ----- XP System (only for the specific server) -----
    if str(message.guild.id) == TARGET_GUILD_ID:
        leveled_up, new_level = await add_xp(message.author.id, message.guild.id, 5)
        if leveled_up:
            level_up_channel = bot.get_channel(LEVEL_UP_CHANNEL_ID)
            if level_up_channel:
                await level_up_channel.send(f"GG {message.author.mention}, you just advanced to level {new_level}!")
            else:
                await message.channel.send(f"GG {message.author.mention}, you just advanced to level {new_level}!")

    # Allow commands to be processed
    await bot.process_commands(message)

# Helper functions
async def ban_member(guild, member, reason):
    # Send DM to the member with reason before banning
    embed = discord.Embed(
        title="⚠️You Have Been temporarily Banned⚠️",
        description="You have been temporarily banned from the server due to suspicious actions. Please contact Truekid to discuss this matter further.",
        color=discord.Color.red()
    )
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.set_footer(text="Contact An Admin For More Information.")

    try:
        await member.send(embed=embed)
    except discord.Forbidden:
        print(f"Could not send DM to {member.name}")

    # Attempt to ban the member
    try:
        await guild.ban(member, reason=reason, delete_message_seconds=0)

        # Send notification to the specific channel in the server
        notification_channel = guild.get_channel(ALERT_CHANNEL_ID)
        if notification_channel:
            await notification_channel.send(f"⚠️**{member}** has been banned for: {reason}")
        else:
            print("Ban notification channel not found.")

    except discord.Forbidden:
        print(f"Failed to ban {member}. Lacking permissions.")

async def unmute_member(member, muted_role):
    if muted_role in member.roles:
        try:
            await member.remove_roles(muted_role)
            await member.send("You have been unmuted after 2 hours.")
            print(f"Unmuted {member}.")
        except discord.Forbidden:
            print(f"Bot doesn't have permission to remove roles from {member}.")
        except discord.HTTPException as e:
            print(f"Failed to remove muted role due to HTTP error: {e}")

# Commands


# Verification system
class VerifyButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Make the view persistent

    @discord.ui.button(label="Verify", style=discord.ButtonStyle.primary, custom_id="verify_button")  # custom_id to make button persistent
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        unverified_role = discord.utils.get(interaction.guild.roles, name="unverified")
        
        # Verify the user by removing the "unverified" role
        if unverified_role in interaction.user.roles:
            await interaction.user.remove_roles(unverified_role)
            await interaction.response.send_message("You have been verified!", ephemeral=True)
        else:
            await interaction.response.send_message("You are already verified.", ephemeral=True)





# Initialize bot with token
bot.run('')
