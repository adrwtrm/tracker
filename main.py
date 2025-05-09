import discord
from discord.ext import commands
import asyncio
import requests
import re
import os

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# Server and User IDs for restrictions
ALLOWED_SERVER_ID = 1365544739440427120  # Your server ID
ALLOWED_USER_ID = 1006450046876778566  # Your user ID

# Keep track of tasks per channel
order_tracking_tasks = {}

# === Extract UUID from link or direct input ===
def extract_uuid(input_str):
    match = re.search(r"([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})", input_str, re.IGNORECASE)
    return match.group(1) if match else None

# === Ready Event ===
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    
    # Sync commands globally to all guilds (servers) and DMs
    try:
        synced = await bot.tree.sync()
        print(f"🔄 Synced {len(synced)} command(s) globally.")
    except Exception as e:
        print(f"❌ Sync error: {e}")

# === /order Slash Command ===
@bot.tree.command(name="order", description="Track an Uber Eats order by UUID or link.")
async def order(interaction: discord.Interaction, input: str, ping_user: discord.User = None):
    # Check if the command is used in the allowed server and by the allowed user
    if interaction.guild.id != ALLOWED_SERVER_ID:
        await interaction.response.send_message("❌ This command can only be used in the designated server.", ephemeral=True)
        return

    if interaction.user.id != ALLOWED_USER_ID:
        await interaction.response.send_message("❌ You do not have permission to use this command.", ephemeral=True)
        return

    await interaction.response.send_message("🔍 Processing order tracking...", ephemeral=True)

    order_uuid = extract_uuid(input)
    if not order_uuid:
        await interaction.followup.send("❌ Could not find a valid UUID. Please check your input.")
        return

    # Default to pinging @everyone if no user is specified
    ping_message = "@everyone" if ping_user is None else f"<@{ping_user.id}>"

    channel_id = interaction.channel_id
    if channel_id in order_tracking_tasks:
        await interaction.followup.send("⚠️ An order is already being tracked in this channel. Please use a different ticket.")
        return

    await interaction.followup.send(f"📦 Started tracking order: `{order_uuid}`")

    task = asyncio.create_task(track_order(interaction.channel, order_uuid, ping_message))
    order_tracking_tasks[channel_id] = task

# === Order Tracking Task ===
async def track_order(channel, order_uuid, ping_message):
    session = requests.Session()
    headers = {
        'x-csrf-token': 'x',  # Replace with actual CSRF token if needed
        'Content-Type': 'application/json'
    }

    data = {
        "orderUuid": order_uuid,
        "timezone": "America/New_York",
        "showAppUpsellIllustration": True,
        "isDirectTracking": False
    }

    last_status = None

    try:
        while True:
            response = session.post(
                "https://www.ubereats.com/_p/api/getActiveOrdersV1",
                headers=headers,
                json=data
            ).json()

            order = response['data']['orders'][0]
            order_phase = order['orderInfo']['orderPhase']

            if order_phase == "COMPLETED":
                await channel.send(f"{ping_message} ✅ Order `{order_uuid}` has been completed!")
                break

            try:
                current_status = order['activeOrderStatus']['titleSummary']['summary']['text']
            except KeyError:
                current_status = "No status available."

            if current_status != last_status:
                await channel.send(f"{ping_message} 🔔 Update for `{order_uuid}`: **{current_status}**")
                last_status = current_status

            await asyncio.sleep(10)

    except Exception as e:
        await channel.send(f"{ping_message} ⚠️ Error tracking order `{order_uuid}`: `{e}`")

    finally:
        order_tracking_tasks.pop(channel.id, None)

# === Run Bot ===
bot.run(os.getenv("DISCORD_TOKEN"))  # Replace with your actual bot token
