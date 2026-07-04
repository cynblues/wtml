import aiosqlite

DB_PATH = "bot.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                guild_id INTEGER PRIMARY KEY,
                ticket_log_channel INTEGER,
                ticket_category INTEGER,
                queue_counter INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS queues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                queue_number TEXT NOT NULL,
                customer_id INTEGER NOT NULL,
                product TEXT NOT NULL,
                admin_id INTEGER,
                ticket_channel_id INTEGER,
                status TEXT DEFAULT 'รอดำเนินการ',
                message_id INTEGER,
                channel_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                finished_at TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                customer_id INTEGER NOT NULL,
                claimed_by INTEGER,
                subject TEXT NOT NULL,
                details TEXT,
                status TEXT DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ticket_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                author_id INTEGER NOT NULL,
                author_name TEXT NOT NULL,
                content TEXT NOT NULL,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS points (
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                points INTEGER DEFAULT 0,
                UNIQUE(user_id, guild_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cooldowns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                set_by INTEGER NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(guild_id, user_id)
            )
        """)
        await db.commit()


# ─── Settings ───────────────────────────────────────────────────────────────

async def get_setting(guild_id: int, key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            f"SELECT {key} FROM settings WHERE guild_id = ?", (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def set_setting(guild_id: int, key: str, value):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings (guild_id) VALUES (?) ON CONFLICT(guild_id) DO NOTHING",
            (guild_id,)
        )
        await db.execute(
            f"UPDATE settings SET {key} = ? WHERE guild_id = ?", (value, guild_id)
        )
        await db.commit()


# ─── Queue ───────────────────────────────────────────────────────────────────

async def get_next_queue_number(guild_id: int) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings (guild_id, queue_counter) VALUES (?, 1) "
            "ON CONFLICT(guild_id) DO UPDATE SET queue_counter = queue_counter + 1",
            (guild_id,)
        )
        await db.commit()
        async with db.execute(
            "SELECT queue_counter FROM settings WHERE guild_id = ?", (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()
            num = row[0] if row else 1
    return f"Q{num:03d}"


async def create_queue(guild_id: int, queue_number: str, customer_id: int,
                       product: str, admin_id: int = None,
                       ticket_channel_id: int = None) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO queues (guild_id, queue_number, customer_id, product, admin_id, ticket_channel_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (guild_id, queue_number, customer_id, product, admin_id, ticket_channel_id))
        await db.commit()
        return cursor.lastrowid


async def update_queue_message(queue_id: int, message_id: int, channel_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE queues SET message_id = ?, channel_id = ? WHERE id = ?",
            (message_id, channel_id, queue_id)
        )
        await db.commit()


async def get_queue(queue_id: int = None, queue_number: str = None, guild_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        if queue_id:
            async with db.execute("SELECT * FROM queues WHERE id = ?", (queue_id,)) as cursor:
                return await cursor.fetchone()
        elif queue_number and guild_id:
            async with db.execute(
                "SELECT * FROM queues WHERE guild_id = ? AND queue_number = ?",
                (guild_id, queue_number)
            ) as cursor:
                return await cursor.fetchone()
    return None


async def get_queues(guild_id: int, status: str = None, limit: int = 10):
    async with aiosqlite.connect(DB_PATH) as db:
        if status:
            async with db.execute(
                "SELECT * FROM queues WHERE guild_id = ? AND status = ? ORDER BY id DESC LIMIT ?",
                (guild_id, status, limit)
            ) as cursor:
                return await cursor.fetchall()
        else:
            async with db.execute(
                "SELECT * FROM queues WHERE guild_id = ? ORDER BY id DESC LIMIT ?",
                (guild_id, limit)
            ) as cursor:
                return await cursor.fetchall()


async def update_queue_status(queue_id: int, status: str, admin_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        if status in ("เสร็จสิ้น", "ยกเลิก"):
            await db.execute(
                "UPDATE queues SET status = ?, finished_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, queue_id)
            )
        else:
            await db.execute(
                "UPDATE queues SET status = ? WHERE id = ?", (status, queue_id)
            )
        if admin_id:
            await db.execute(
                "UPDATE queues SET admin_id = ? WHERE id = ?", (admin_id, queue_id)
            )
        await db.commit()


# ─── Tickets ─────────────────────────────────────────────────────────────────

async def create_ticket(guild_id: int, channel_id: int, customer_id: int,
                        subject: str, details: str = None) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO tickets (guild_id, channel_id, customer_id, subject, details)
            VALUES (?, ?, ?, ?, ?)
        """, (guild_id, channel_id, customer_id, subject, details))
        await db.commit()
        return cursor.lastrowid


async def get_ticket_by_channel(channel_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM tickets WHERE channel_id = ?", (channel_id,)
        ) as cursor:
            return await cursor.fetchone()


async def get_open_ticket_by_user(guild_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM tickets WHERE guild_id = ? AND customer_id = ? AND status != 'closed'",
            (guild_id, user_id)
        ) as cursor:
            return await cursor.fetchone()


async def claim_ticket(ticket_id: int, staff_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE tickets SET claimed_by = ?, status = 'claimed' WHERE id = ?",
            (staff_id, ticket_id)
        )
        await db.commit()


async def close_ticket(ticket_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE tickets SET status = 'closed', closed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (ticket_id,)
        )
        await db.commit()


async def save_ticket_message(ticket_id: int, author_id: int, author_name: str, content: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO ticket_messages (ticket_id, author_id, author_name, content) VALUES (?, ?, ?, ?)",
            (ticket_id, author_id, author_name, content)
        )
        await db.commit()


async def get_ticket_messages(ticket_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT author_name, content, sent_at FROM ticket_messages WHERE ticket_id = ? ORDER BY sent_at ASC",
            (ticket_id,)
        ) as cursor:
            return await cursor.fetchall()


# ─── Points ──────────────────────────────────────────────────────────────────

async def get_points(user_id: int, guild_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT points FROM points WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def add_points(user_id: int, guild_id: int, amount: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT points FROM points WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id)
        ) as cursor:
            row = await cursor.fetchone()
        if row:
            await db.execute(
                "UPDATE points SET points = points + ? WHERE user_id = ? AND guild_id = ?",
                (amount, user_id, guild_id)
            )
        else:
            await db.execute(
                "INSERT INTO points (user_id, guild_id, points) VALUES (?, ?, ?)",
                (user_id, guild_id, amount)
            )
        await db.commit()


async def remove_points(user_id: int, guild_id: int, amount: int) -> bool:
    current = await get_points(user_id, guild_id)
    if current < amount:
        return False
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE points SET points = points - ? WHERE user_id = ? AND guild_id = ?",
            (amount, user_id, guild_id)
        )
        await db.commit()
    return True


# ─── Cooldown System ─────────────────────────────────────────────────────────

async def set_cooldown(guild_id: int, user_id: int, set_by: int,
                       expires_at, reason: str = None):
    expires_str = expires_at.strftime("%Y-%m-%d %H:%M:%S") if hasattr(expires_at, "strftime") else str(expires_at)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO cooldowns (guild_id, user_id, set_by, expires_at, reason)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, user_id) DO UPDATE SET
                set_by = excluded.set_by,
                expires_at = excluded.expires_at,
                reason = excluded.reason,
                created_at = CURRENT_TIMESTAMP
        """, (guild_id, user_id, set_by, expires_str, reason))
        await db.commit()


async def get_cooldown(guild_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM cooldowns WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        ) as cursor:
            return await cursor.fetchone()


async def delete_cooldown(guild_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM cooldowns WHERE guild_id = ? AND user_id = ?",
            (guild_id, user_id)
        )
        await db.commit()


async def get_active_cooldowns(guild_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT * FROM cooldowns WHERE guild_id = ? ORDER BY expires_at ASC",
            (guild_id,)
        ) as cursor:
            return await cursor.fetchall()


async def get_leaderboard(guild_id: int, limit: int = 10):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id, points FROM points WHERE guild_id = ? ORDER BY points DESC LIMIT ?",
            (guild_id, limit)
        ) as cursor:
            return await cursor.fetchall()
