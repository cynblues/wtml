import discord
from discord.ext import commands
import time

START_TIME = time.time()


class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(name="ping", description="ตรวจสอบความหน่วงของบอท")
    async def ping(self, ctx: discord.ApplicationContext):
        latency = round(self.bot.latency * 1000)
        color = discord.Color.green() if latency < 100 else discord.Color.orange()
        embed = discord.Embed(
            title="🏓  Pong!",
            description=f"ความหน่วง: **{latency} ms**",
            color=color
        )
        await ctx.respond(embed=embed)

    @discord.slash_command(name="help", description="ดูคำสั่งทั้งหมดของบอท")
    async def help_cmd(self, ctx: discord.ApplicationContext):
        embed = discord.Embed(
            title="📖  คู่มือการใช้งานบอท",
            color=discord.Color.from_rgb(88, 101, 242)
        )
        embed.add_field(
            name="📋  ระบบคิว",
            value=(
                "`/queue create` — สร้างคิวงานใหม่\n"
                "`/queue list` — ดูรายการคิวทั้งหมด\n"
                "`/queue finish` — มาร์กคิวว่าเสร็จสิ้น\n"
                "`/queue cancel` — ยกเลิกคิว"
            ),
            inline=False
        )
        embed.add_field(
            name="🎫  ระบบตั๋ว",
            value=(
                "`/ticket panel` — โพสต์แผงเปิดตั๋ว\n"
                "`/ticket setlog` — ตั้งห้อง log\n"
                "`/ticket claim` — รับงานตั๋ว\n"
                "`/ticket close` — ปิดตั๋ว"
            ),
            inline=False
        )
        embed.add_field(
            name="💰  ระบบคะแนน",
            value=(
                "`/point balance` — ตรวจสอบคะแนน\n"
                "`/point add` — เพิ่มคะแนน (แอดมิน)\n"
                "`/point remove` — ลดคะแนน (แอดมิน)\n"
                "`/point leaderboard` — อันดับคะแนน"
            ),
            inline=False
        )
        embed.add_field(
            name="🔧  ทั่วไป",
            value="`/ping` — ตรวจสอบความหน่วง\n`/help` — ดูคู่มือนี้",
            inline=False
        )
        embed.set_footer(text="คำสั่งที่มีป้าย (แอดมิน) ต้องมีสิทธิ์จัดการเซิร์ฟเวอร์")
        await ctx.respond(embed=embed, ephemeral=True)


def setup(bot):
    bot.add_cog(General(bot))
