import discord
from discord import app_commands
from discord.ext import commands
import requests
import asyncio
import re
import os

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)

GUILD_ID = 1365544739440427120
OWNER_ID = 1006450046876778566
TOKEN = os.getenv("DISCORD_TOKEN")  # Or hardcode your token here
STATUS_CHANNEL_ID = 1365579583419715604  # Channel to rename

active_orders = {}

def extract_uuid(input_str):
    match = re.search(r"[a-fA-F0-9\-]{36}", input_str)
    return match.group() if match else None

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"🔄 Synced {len(synced)} command(s) to guild {GUILD_ID}.")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")
    print(f"✅ Logged in as {bot.user}")

@bot.tree.command(name="order", description="Track a customer's Uber Eats order", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(order_link_or_uuid="Paste the Uber Eats order link or UUID",
                       ping="Who to ping on updates (optional, default: @everyone)")
async def order(interaction: discord.Interaction, order_link_or_uuid: str, ping: str = "@everyone"):
    if interaction.guild and interaction.guild.id != GUILD_ID and interaction.user.id != OWNER_ID:
        await interaction.response.send_message("⛔ This command can only be used in the authorized server.", ephemeral=True)
        return

    order_uuid = extract_uuid(order_link_or_uuid)
    if not order_uuid:
        await interaction.response.send_message("❌ Invalid order link or UUID.", ephemeral=True)
        return

    await interaction.response.send_message(f"🔍 Started tracking order `{order_uuid}`...", ephemeral=True)
    await track_order(order_uuid, interaction.channel, ping)

async def track_order(order_uuid, channel, ping_target):
    session = requests.Session()
    headers = {
        'x-csrf-token': 'x'  # Replace with actual token if needed
    }
    url = "https://www.ubereats.com/_p/api/getActiveOrdersV1"
    data = {
        "orderUuid": order_uuid,
        "timezone": "America/New_York",
        "showAppUpsellIllustration": True,
        "isDirectTracking": False
    }

    last_status_text = None

    while True:
        try:
            response = session.post(url, headers=headers, data=data)
            response.raise_for_status()
            json_data = response.json()

            order = json_data['data']['orders'][0]
            order_phase = order['orderInfo']['orderPhase']

            if order_phase == "COMPLETED":
                await channel.send(f"{ping_target} ✅ Order `{order_uuid}` has been completed!")
                break

            status_text = order['activeOrderStatus']['titleSummary']['summary']['text']
            if status_text != last_status_text:
                await channel.send(f"{ping_target} 📦 Order Update: `{status_text}`")
                last_status_text = status_text

        except Exception as e:
            await asyncio.sleep(10)
            try:
                response = session.post(url, headers=headers, data=data)
                response.raise_for_status()
                continue
            except Exception as e2:
                await channel.send(f"{ping_target} ⚠️ Error tracking order `{order_uuid}`: `{e2}`")
                break

        await asyncio.sleep(10)

@bot.tree.command(name="status", description="Set the status of the shop to open or closed", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(state="Set to 'open' or 'closed'")
async def status(interaction: discord.Interaction, state: str):
    # Role restriction IDs
    allowed_roles = {1370517846186004500, 1365562158687060089}

    # Check if user has at least one allowed role
    if not interaction.user.guild_permissions.administrator and not any(role.id in allowed_roles for role in interaction.user.roles):
        await interaction.response.send_message("⛔ You don't have permission to use this command.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)  # Prevent timeout

    if state.lower() not in ["open", "closed"]:
        await interaction.followup.send("❌ Invalid state. Use 'open' or 'closed'.")
        return

    channel = bot.get_channel(STATUS_CHANNEL_ID)
    if not channel:
        await interaction.followup.send("❌ Status channel not found.")
        return

    new_name = "open 🟢" if state.lower() == "open" else "closed 🔴"
    try:
        await channel.edit(name=new_name)
        await interaction.followup.send(f"✅ Channel name updated to `{new_name}`.")
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to update channel name: `{e}`")

bot.run(TOKEN)
