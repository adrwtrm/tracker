import discord
from discord import app_commands
from discord.ext import commands
import requests
import asyncio
import re
import os
import json

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)

OWNER_ID = 1006450046876778566
STATUS_CHANNEL_ID = 1365579583419715604  # Replace with your channel ID
TOKEN = os.getenv("DISCORD_TOKEN") or "YOUR_TOKEN"

PAYMENT_FILE = "payment_data.json"
active_orders = {}

# Load or initialize payment data
if os.path.exists(PAYMENT_FILE):
    with open(PAYMENT_FILE, "r") as f:
        payment_data = json.load(f)
else:
    payment_data = {}

def extract_uuid(input_str):
    match = re.search(r"[a-fA-F0-9\-]{36}", input_str)
    return match.group() if match else None

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"🔄 Synced {len(synced)} global command(s).")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")
    print(f"✅ Logged in as {bot.user}")

@bot.tree.command(name="order", description="Track a customer's Uber Eats order")
@app_commands.describe(order_link_or_uuid="Paste the Uber Eats order link or UUID",
                       ping="Who to ping on updates (leave blank to ping yourself)")
async def order(interaction: discord.Interaction, order_link_or_uuid: str, ping: str = ""):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("⛔ Only the bot owner can use this command.", ephemeral=True)
        return

    order_uuid = extract_uuid(order_link_or_uuid)
    if not order_uuid:
        await interaction.response.send_message("❌ Invalid order link or UUID.", ephemeral=True)
        return

    # Determine ping target
    ping_target = ping if ping else interaction.user.mention

    await interaction.response.send_message(f"🔍 Fetching order `{order_uuid}` status...", ephemeral=True)

    try:
        status_text = await fetch_order_status(order_uuid)
        await interaction.followup.send(f"{ping_target} 📦 Order `{order_uuid}` Status: `{status_text}`")
    except Exception as e:
        await interaction.followup.send(f"{ping_target} ⚠️ Error: `{e}`")

async def fetch_order_status(order_uuid):
    url = "https://www.ubereats.com/_p/api/getActiveOrdersV1"
    headers = {'x-csrf-token': 'x'}
    data = {
        "orderUuid": order_uuid,
        "timezone": "America/New_York",
        "showAppUpsellIllustration": True,
        "isDirectTracking": False
    }

    response = requests.post(url, headers=headers, data=data)
    response.raise_for_status()
    json_data = response.json()
    return json_data['data']['orders'][0]['activeOrderStatus']['titleSummary']['summary']['text']

@bot.tree.command(name="status", description="Set the status of the shop to open or closed")
@app_commands.describe(state="Set to 'open' or 'closed'")
async def status(interaction: discord.Interaction, state: str):
    allowed_roles = {1370517846186004500, 1365562158687060089}
    if not interaction.user.guild_permissions.administrator and not any(role.id in allowed_roles for role in interaction.user.roles):
        await interaction.response.send_message("⛔ You don't have permission to use this command.", ephemeral=True)
        return

    if state.lower() not in ["open", "closed"]:
        await interaction.response.send_message("❌ Invalid state. Use 'open' or 'closed'.", ephemeral=True)
        return

    channel = bot.get_channel(STATUS_CHANNEL_ID)
    if not channel:
        await interaction.response.send_message("❌ Status channel not found.", ephemeral=True)
        return

    new_name = "open 🟢" if state.lower() == "open" else "closed 🔴"
    try:
        await channel.edit(name=new_name)
        await interaction.response.send_message(f"✅ Channel name updated to `{new_name}`.")
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to update channel name: `{e}`", ephemeral=True)

@bot.tree.command(name="info", description="Manage your payment information")
@app_commands.describe(action="Type 'edit' to edit info or 'send' to send your saved info")
async def info(interaction: discord.Interaction, action: str):
    user_id = str(interaction.user.id)

    if action.lower() == "edit":
        modal = PaymentModal(user_id)
        await interaction.response.send_modal(modal)

    elif action.lower() == "send":
        if user_id not in payment_data:
            await interaction.response.send_message("❌ No payment info saved. Use `/info edit` first.", ephemeral=True)
        else:
            await interaction.response.send_message(payment_data[user_id], ephemeral=False)

    else:
        await interaction.response.send_message("❌ Invalid action. Use 'edit' or 'send'.", ephemeral=True)

class PaymentModal(discord.ui.Modal, title="Enter Payment Info"):
    payment = discord.ui.TextInput(label="Enter payment methods here.", style=discord.TextStyle.paragraph)

    def __init__(self, user_id: str):
        super().__init__()
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        payment_data[self.user_id] = self.payment.value
        with open(PAYMENT_FILE, "w") as f:
            json.dump(payment_data, f, indent=2)
        await interaction.response.send_message("✅ Payment information saved!", ephemeral=True)

bot.run(TOKEN)
