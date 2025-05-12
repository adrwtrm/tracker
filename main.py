import discord
from discord import app_commands
from discord.ext import commands
import os

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)

OWNER_ID = 1006450046876778566
TOKEN = os.getenv("DISCORD_TOKEN")

# Store payment methods per user ID
payment_data = {}

class PaymentModal(discord.ui.Modal, title="Payment Methods"):
    payment_methods = discord.ui.TextInput(label="Enter payment methods here.", style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        payment_data[interaction.user.id] = self.payment_methods.value
        await interaction.response.send_message("✅ Payment methods saved successfully!", ephemeral=True)

@bot.event
async def on_ready():
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
    if action == "edit":
        await interaction.response.send_modal(PaymentModal())
    elif action == "send":
        user_id = interaction.user.id
        payment = payment_data.get(user_id)
        if payment:
            await interaction.response.send_message(f"💳 Your payment methods:\n```{payment}```", ephemeral=True)
        else:
            await interaction.response.send_message("❌ No payment methods saved. Use `/info edit` to add them.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Invalid action. Use either `edit` or `send`.", ephemeral=True)

bot.run(TOKEN)
