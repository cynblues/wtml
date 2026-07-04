import os
import discord
from discord.ext import commands
import database

TOKEN = os.environ.get("DISCORD_TOKEN")

intents = discord.Intents.default()

bot = discord.Bot(intents=intents)

COGS = [
    "cogs.general",
    "cogs.queue",
    "cogs.ticket",
    "cogs.points",
    "cogs.cooldown_system",
]

for cog in COGS:
    bot.load_extension(cog)


@bot.event
async def on_ready():
    await database.init_db()
    print(f"✅ เข้าสู่ระบบในฐานะ {bot.user} (ID: {bot.user.id})")
    print(f"🌐 เชื่อมต่อกับ {len(bot.guilds)} เซิร์ฟเวอร์")
    print("─────────────────────────────")
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="ระบบคิวร้านค้า | /help"
        )
    )


@bot.event
async def on_application_command_error(ctx: discord.ApplicationContext, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.respond(
            f"⏳ กรุณารอ **{error.retry_after:.1f} วินาที** ก่อนใช้คำสั่งนี้อีกครั้ง",
            ephemeral=True
        )
    elif isinstance(error, commands.MissingPermissions):
        await ctx.respond("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้", ephemeral=True)
    elif isinstance(error, commands.BotMissingPermissions):
        await ctx.respond(
            f"❌ บอทขาดสิทธิ์: {', '.join(error.missing_permissions)}",
            ephemeral=True
        )
    else:
        print(f"[ERROR] {error}")
        try:
            await ctx.respond("❌ เกิดข้อผิดพลาด กรุณาลองใหม่อีกครั้ง", ephemeral=True)
        except Exception:
            pass


if __name__ == "__main__":
    if not TOKEN:
        print("❌ ไม่พบ DISCORD_TOKEN กรุณาตั้งค่าใน Secrets")
        exit(1)
    bot.run(TOKEN)
