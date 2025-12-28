import aiosqlite
import datetime
from config import settings

DB_PATH = settings.DB_NAME

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                username TEXT,
                subscription_end_date TIMESTAMP,
                referrer_id INTEGER,
                referral_count INTEGER DEFAULT 0,
                max_devices INTEGER DEFAULT 2,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                public_key TEXT,
                private_key TEXT,
                ip_address TEXT,
                config TEXT,
                device_name TEXT,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        await db.commit()

async def get_user(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)) as cursor:
            return await cursor.fetchone()

async def create_user(telegram_id: int, username: str, referrer_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO users (telegram_id, username, referrer_id) VALUES (?, ?, ?)",
                (telegram_id, username, referrer_id)
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

async def update_subscription(telegram_id: int, days: int):
    async with aiosqlite.connect(DB_PATH) as db:
        user = await get_user(telegram_id)
        current_end = None
        
        if user and user['subscription_end_date']:
            current_end = datetime.datetime.fromisoformat(user['subscription_end_date'])
        
        now = datetime.datetime.now()
        
        if current_end and current_end > now:
            new_end = current_end + datetime.timedelta(days=days)
        else:
            new_end = now + datetime.timedelta(days=days)
            
        await db.execute(
            "UPDATE users SET subscription_end_date = ? WHERE telegram_id = ?",
            (new_end.isoformat(), telegram_id)
        )
        await db.commit()
        return new_end

async def disable_subscription(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.datetime.now()
        await db.execute(
            "UPDATE users SET subscription_end_date = ? WHERE telegram_id = ?",
            (now.isoformat(), telegram_id)
        )
        await db.commit()

async def add_referral_count(referrer_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET referral_count = referral_count + 1 WHERE telegram_id = ?",
            (referrer_id,)
        )
        await db.commit()

async def reset_referral_count(referrer_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET referral_count = 0 WHERE telegram_id = ?",
            (referrer_id,)
        )
        await db.commit()

async def save_key(user_id: int, public_key: str, private_key: str, ip_address: str, config: str, device_name: str = "Device 1"):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO keys (user_id, public_key, private_key, ip_address, config, device_name) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, public_key, private_key, ip_address, config, device_name)
        )
        await db.commit()

async def get_user_keys(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM keys WHERE user_id = ? AND is_active = 1", (user_id,)) as cursor:
            return await cursor.fetchall()

async def count_user_keys(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM keys WHERE user_id = ? AND is_active = 1", (user_id,)) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else 0

async def get_user_key(user_id: int):
    # Deprecated: Use get_user_keys instead. Kept for backward compatibility, returns the first key.
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM keys WHERE user_id = ? AND is_active = 1 LIMIT 1", (user_id,)) as cursor:
            return await cursor.fetchone()

async def get_all_used_ips():
    async with aiosqlite.connect(DB_PATH) as db:
        # Get IPs from active keys
        async with db.execute("SELECT ip_address FROM keys WHERE is_active = 1") as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

async def get_all_active_keys():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT public_key, ip_address FROM keys WHERE is_active = 1") as cursor:
            return await cursor.fetchall()

async def delete_key_by_id(key_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        # Verify ownership and get public key to remove from WG
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT public_key FROM keys WHERE id = ? AND user_id = ?", (key_id, user_id)) as cursor:
            row = await cursor.fetchone()
            if row:
                public_key = row['public_key']
                await db.execute("UPDATE keys SET is_active = 0 WHERE id = ?", (key_id,))
                await db.commit()
                return public_key
            return None


async def get_all_active_subs():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        now = datetime.datetime.now().isoformat()
        async with db.execute("SELECT * FROM users WHERE subscription_end_date > ?", (now,)) as cursor:
            return await cursor.fetchall()

async def get_expired_subs():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        now = datetime.datetime.now().isoformat()
        # Get users who have expired but still have active keys
        query = """
            SELECT u.*, k.public_key 
            FROM users u 
            JOIN keys k ON u.id = k.user_id 
            WHERE u.subscription_end_date < ? AND k.is_active = 1
        """
        async with db.execute(query, (now,)) as cursor:
            return await cursor.fetchall()

async def deactivate_key(public_key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE keys SET is_active = 0 WHERE public_key = ?", (public_key,))
        await db.commit()

async def increment_max_devices(telegram_id: int, count: int = 1):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET max_devices = max_devices + ? WHERE telegram_id = ?",
            (count, telegram_id)
        )
        await db.commit()
