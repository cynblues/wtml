import discord
from discord.ext import commands
from discord import option
from datetime import datetime, timezone, timedelta
import re
import database

TZ = timezone(timedelta(hours=7))


def parse_duration(text: str) -> timedelta | None:
    """แปลงข้อความเวลา เช่น 1d2h30m เป็น timedelta"""
    pattern = re.compile(
        r"(?:(\d+)\s*d(?:ays?)?)?"
        r"(?:(\d+)\s*h(?:ours?)?)?"
        r"(?:(\d+)\s*m(?:in(?:utes?)?)?)?"
        r"(?:(\d+)\s*s(?:ec(?:onds?)?)?)?",
        re.IGNORECASE
    )
    m = pattern.fullmatch(text.strip())
    if not m or not any(m.groups()):
        return None
    days = int(m.group(1) or 0)
    hours = int(m.group(2) or 0)
    minutes = int(m.group(3) or 0)
    seconds = int(m.group(4) or 0)
    total = timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
    return total if total.total_seconds() > 0 else None


def format_remaining(expires_at_str: str) -> str:
    """แปลง expires_at → ข้อความเวลาที่เหลือ"""
    try:
        expires = datetime.fromisoformat(expires_at_str).replace(tzinfo=timezone.utc)
    except Exception:
        return "ไม่ทราบ"
    now = datetime.now(timezone.utc)
    remaining = expires - now
    if remaining.total_seconds() <= 0:
        return "หมดแล้ว"
    total_s = int(remaining.total_seconds())
    days, rem = divmod(total_s, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days} วัน")
    if hours:
        parts.append(f"{hours} ชั่วโมง")
    if minutes:
        parts.append(f"{minutes} นาที")
    if seconds and not days:
        parts.append(f"{seconds} วินาที")
    return " ".join(parts) if parts else "น้อยกว่า 1 วินาที"


def format_thai_time(dt_str: str) -> str:
    try:
        dt = datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc).astimezone(TZ)
        return dt.strftime("%d/%m/%Y %H:%M น.")
    except Exception:
        return dt_str


def cooldown_embed(row, guild: discord.Guild, title: str, color: discord.Color) -> discord.Embed:
    """สร้าง embed แสดงข้อมูลคูลดาวน์ 1 คน"""
    # row: id, guild_id, user_id, set_by, expires_at, reason, created_at
    user_id   = row[2]
    set_by    = row[3]
    expires   = row[4]
    reason    = row[5] or "—"
    created   = row[6]

    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="👤  ลูกค้า",           value=f"<@{user_id}>",  inline=True)
    embed.add_field(name="👨‍💼  ตั้งโดย",          value=f"<@{set_by}>",   inline=True)
    embed.add_field(name="\u200b",               value="\u200b",         inline=True)
    embed.add_field(name="📝  เหตุผล",           value=reason,           inline=False)
    embed.add_field(name="🕒  หมดคูลดาวน์",     value=format_thai_time(expires), inline=True)
    embed.add_field(name="⏳  เวลาที่เหลือ",    value=format_remaining(expires), inline=True)
    embed.set_footer(text=f"ตั้งเมื่อ {format_thai_time(created)}")
    return embed


class CooldownSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── /cooldown @user ────────────────────────────────────────────────────
    @discord.slash_command(name="cooldown", description="ดูคูลดาวน์ที่เหลือของลูกค้า")
    @option("user", discord.Member, description="ลูกค้าที่ต้องการตรวจสอบ")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def cooldown_check(self, ctx: discord.ApplicationContext, user: discord.Member):
        row = await database.get_cooldown(ctx.guild_id, user.id)

        if not row:
            embed = discord.Embed(
                description=f"✅ {user.mention} ไม่ติดคูลดาวน์",
                color=discord.Color.green()
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return

        expires_at = row[4]
        now = datetime.now(timezone.utc)
        try:
            expires = datetime.fromisoformat(expires_at).replace(tzinfo=timezone.utc)
        except Exception:
            expires = now

        if expires <= now:
            await database.delete_cooldown(ctx.guild_id, user.id)
            embed = discord.Embed(
                description=f"✅ {user.mention} หมดคูลดาวน์แล้ว",
                color=discord.Color.green()
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return

        embed = cooldown_embed(
            row, ctx.guild,
            title="⏳  ข้อมูลคูลดาวน์",
            color=discord.Color.from_rgb(255, 193, 7)
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        await ctx.respond(embed=embed, ephemeral=True)

    # ── /setcooldown @user <duration> [reason] ─────────────────────────────
    @discord.slash_command(name="setcooldown", description="ตั้งคูลดาวน์ให้ลูกค้า (แอดมิน)")
    @option("user", discord.Member, description="ลูกค้าที่ต้องการตั้งคูลดาวน์")
    @option("duration", str, description="ระยะเวลา เช่น 1d, 2h, 30m, 1h30m")
    @option("reason", str, description="เหตุผล (ไม่บังคับ)", required=False)
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def set_cooldown(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Member,
        duration: str,
        reason: str = None,
    ):
        delta = parse_duration(duration)
        if not delta:
            await ctx.respond(
                "❌ รูปแบบเวลาไม่ถูกต้อง\n"
                "ตัวอย่าง: `30m`, `1h`, `2h30m`, `1d`, `1d12h`",
                ephemeral=True
            )
            return

        max_days = 30
        if delta.total_seconds() > max_days * 86400:
            await ctx.respond(f"❌ คูลดาวน์สูงสุด {max_days} วัน", ephemeral=True)
            return

        expires_at = datetime.now(timezone.utc) + delta
        await database.set_cooldown(
            guild_id=ctx.guild_id,
            user_id=user.id,
            set_by=ctx.author.id,
            expires_at=expires_at,
            reason=reason,
        )

        row = await database.get_cooldown(ctx.guild_id, user.id)
        embed = cooldown_embed(
            row, ctx.guild,
            title="🔒  ตั้งคูลดาวน์สำเร็จ",
            color=discord.Color.from_rgb(220, 53, 69)
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        await ctx.respond(embed=embed)

    # ── /resetcooldown @user ───────────────────────────────────────────────
    @discord.slash_command(name="resetcooldown", description="ล้างคูลดาวน์ของลูกค้า (แอดมิน)")
    @option("user", discord.Member, description="ลูกค้าที่ต้องการล้างคูลดาวน์")
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def reset_cooldown(self, ctx: discord.ApplicationContext, user: discord.Member):
        row = await database.get_cooldown(ctx.guild_id, user.id)
        if not row:
            await ctx.respond(
                f"❌ {user.mention} ไม่ได้ติดคูลดาวน์อยู่",
                ephemeral=True
            )
            return

        await database.delete_cooldown(ctx.guild_id, user.id)
        embed = discord.Embed(
            title="✅  ล้างคูลดาวน์สำเร็จ",
            description=f"ล้างคูลดาวน์ของ {user.mention} เรียบร้อยแล้ว",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"ดำเนินการโดย {ctx.author.display_name}")
        await ctx.respond(embed=embed)

    # ── /cooldownlist ──────────────────────────────────────────────────────
    @discord.slash_command(name="cooldownlist", description="ดูรายชื่อลูกค้าที่กำลังติดคูลดาวน์")
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 10, commands.BucketType.guild)
    async def cooldown_list(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)
        rows = await database.get_active_cooldowns(ctx.guild_id)

        if not rows:
            embed = discord.Embed(
                description="✅ ไม่มีลูกค้าที่ติดคูลดาวน์ในขณะนี้",
                color=discord.Color.green()
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return

        embed = discord.Embed(
            title="⏳  รายชื่อลูกค้าที่ติดคูลดาวน์",
            color=discord.Color.from_rgb(255, 193, 7)
        )

        now = datetime.now(timezone.utc)
        expired_ids = []
        lines = []

        for row in rows:
            user_id   = row[2]
            set_by    = row[3]
            expires   = row[4]
            reason    = row[5] or "—"

            try:
                exp_dt = datetime.fromisoformat(expires).replace(tzinfo=timezone.utc)
            except Exception:
                exp_dt = now

            if exp_dt <= now:
                expired_ids.append((ctx.guild_id, user_id))
                continue

            remaining = format_remaining(expires)
            exp_str   = format_thai_time(expires)
            lines.append(
                f"👤 <@{user_id}> — ⏳ **{remaining}**\n"
                f"　🕒 หมด: {exp_str}　📝 {reason}"
            )

        for guild_id, user_id in expired_ids:
            await database.delete_cooldown(guild_id, user_id)

        if not lines:
            embed.description = "✅ ไม่มีลูกค้าที่ติดคูลดาวน์ในขณะนี้"
            embed.color = discord.Color.green()
        else:
            embed.description = "\n\n".join(lines)
            embed.set_footer(text=f"ติดคูลดาวน์อยู่ {len(lines)} คน")

        await ctx.respond(embed=embed, ephemeral=True)

    @set_cooldown.error
    @reset_cooldown.error
    @cooldown_list.error
    async def admin_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.respond("❌ คุณต้องมีสิทธิ์ **จัดการเซิร์ฟเวอร์** เพื่อใช้คำสั่งนี้", ephemeral=True)
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.respond(
                f"⏳ กรุณารอ **{error.retry_after:.1f} วินาที** ก่อนใช้คำสั่งนี้อีกครั้ง",
                ephemeral=True
            )

    @cooldown_check.error
    async def check_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.respond(
                f"⏳ กรุณารอ **{error.retry_after:.1f} วินาที** ก่อนใช้คำสั่งนี้อีกครั้ง",
                ephemeral=True
            )


def setup(bot):
    bot.add_cog(CooldownSystem(bot))
