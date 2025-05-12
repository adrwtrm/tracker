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
TOKEN = os.getenv("DISCORD_TOKEN")
STATUS_CHANNEL_ID = 1365579583419715604

# In-memory and persistent storage for payment info
payment_data = {}
PAYMENT_FILE = "payment_data.json"

# Load payment data from file if exists
if os.path.exists(PAYMENT_FILE):
    with open(PAYMENT_FILE, "r") as f:
        payment_data = json.load(f)

# Emoji mapping for various payment methods and their variations
payment_emojis = {
    "paypal": "<:paypal:1371538769332670534>",
    "apple pay": "<:applepay:1371538798659375266>",
    "applepay": "<:applepay:1371538798659375266>",
    "venmo": "<:venmo:1371538828581408778>",
    "zelle": "<:zelle:1371539328706281763>",
    "cashapp": "<:cashapp:1371539498881519756>",
    "cash app": "<:cashapp:1371539498881519756>",
    "litecoin": "<:litecoin:1371539402232434840>",
    "ltc": "<:litecoin:1371539402232434840>",
    "bitcoin": "<:bitcoin:1371540263981551616>",
    "btc": "<:bitcoin:1371540263981551616>",
    "solana": "<:solana:1371539374453293198>",
    "sol": "<:solana:1371539374453293198>",
    "stripe": "<:stripe:1371539802528153601>"
}

def extract_uuid(input_str):
    match = re.search(r"[a-fA-F0-9\-]{36}", input_str)
    return match.group() if match else None

def format_payment_text(user_id):
    text = payment_data.get(str(user_id), "No payment methods provided.")
    lines = text.split("\n")
    formatted = ""
    for line in lines:
        for keyword, emoji in payment_emojis.items():
            if keyword.lower() in line.lower():
                line = f"{emoji} {line}"
                break
        formatted += line + "\n"
    return formatted

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"🔄 Synced {len(synced)} global command(s).")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")
    print(f"✅ Logged in as {bot.user}")

@bot.tree.command(name="order", description="Track a customer's Uber Eats order")
@app_commands.describe(order_link_or_uuid="Paste the Uber Eats order link or UUID", ping="Who to ping (default: you)")
async def order(interaction: discord.Interaction, order_link_or_uuid: str, ping: str = ""):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("⛔ Only the bot owner can use this command.", ephemeral=True)
        return

    order_uuid = extract_uuid(order_link_or_uuid)
    if not order_uuid:
        await interaction.response.send_message("❌ Invalid order link or UUID.", ephemeral=True)
        return

    mention_target = ping if ping else interaction.user.mention
    await interaction.response.send_message(f"🔍 Started tracking order `{order_uuid}`...", ephemeral=True)
    await track_order(order_uuid, interaction.channel, mention_target)

async def track_order(order_uuid, channel, ping_target):
    session = requests.Session()
    headers = {'x-csrf-token': 'x'}
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
                await channel.send(f"{ping_target} 📦 Order Update `{order_uuid}`: `{status_text}`")
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

@bot.tree.command(name="status", description="Set the shop status to open or closed")
@app_commands.describe(state="Type 'open' or 'closed'")
async def status(interaction: discord.Interaction, state: str):
    allowed_roles = {1370517846186004500, 1365562158687060089}

    if not interaction.user.guild_permissions.administrator and not any(role.id in allowed_roles for role in interaction.user.roles):
        await interaction.response.send_message("⛔ You don't have permission to use this command.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

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

class PaymentModal(discord.ui.Modal, title="Payment Methods"):
    payment = discord.ui.TextInput(label="Enter payment methods here.", style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        payment_data[user_id] = self.payment.value

        with open(PAYMENT_FILE, "w") as f:
            json.dump(payment_data, f)

        await interaction.response.send_message("✅ Payment methods saved.", ephemeral=True)

@bot.tree.command(name="info", description="Edit or send your payment info")
@app_commands.describe(action="Choose 'edit' or 'send'")
async def info(interaction: discord.Interaction, action: str):
    if action.lower() == "edit":
        await interaction.response.send_modal(PaymentModal())
    elif action.lower() == "send":
        formatted = format_payment_text(interaction.user.id)
        await interaction.response.send_message(formatted)
    else:
        await interaction.response.send_message("❌ Invalid option. Use 'edit' or 'send'.", ephemeral=True)

bot.run(TOKEN)
