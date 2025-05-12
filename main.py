import discord
from discord import app_commands
from discord.ext import commands
import os
import json

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)

OWNER_ID = 1006450046876778566
TOKEN = os.getenv("DISCORD_TOKEN")

PAYMENT_FILE = "payments.txt"
payment_data = {}

# Load saved payment data from file
def load_payments():
    global payment_data
    if os.path.exists(PAYMENT_FILE):
        with open(PAYMENT_FILE, "r", encoding="utf-8") as f:
            try:
                payment_data = json.load(f)
            except json.JSONDecodeError:
                payment_data = {}

# Save payment data to file
def save_payments():
    with open(PAYMENT_FILE, "w", encoding="utf-8") as f:
        json.dump(payment_data, f, ensure_ascii=False, indent=2)

class PaymentModal(discord.ui.Modal, title="Payment Methods"):
    payment_methods = discord.ui.TextInput(label="Enter payment methods here.", style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        payment_data[user_id] = self.payment_methods.value
        save_payments()
        await interaction.response.send_message("✅ Payment methods saved successfully!", ephemeral=True)

@bot.event
async def on_ready():
    load_payments()
    try:
        synced = await bot.tree.sync()
        print(f"🔄 Synced {len(synced)} global command(s).")
    except Exception as e:
        print(f"❌ Sync failed: {e}")
    print(f"✅ Logged in as {bot.user}")

@bot.tree.command(name="info", description="Edit or send your payment methods")
@app_commands.describe(action="Choose 'edit' to enter methods or 'send' to display them")
async def info(interaction: discord.Interaction, action: str):
    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("⛔ Only the bot owner can use this command.", ephemeral=True)
        return

    action = action.lower()
    user_id = str(interaction.user.id)

    if action == "edit":
        await interaction.response.send_modal(PaymentModal())
    elif action == "send":
        payment = payment_data.get(user_id)
        if payment:
            await interaction.response.send_message(f"💳 Your payment methods:\n```{payment}```", ephemeral=True)
        else:
            await interaction.response.send_message("❌ No payment methods saved. Use `/info edit` to add them.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Invalid action. Use either `edit` or `send`.", ephemeral=True)

bot.run(TOKEN)
