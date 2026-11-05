import aiosqlite
from cryptography.fernet import Fernet
from .config import DB_PATH, ENCRYPTION_KEY

_cipher = Fernet(ENCRYPTION_KEY)

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS settings
                            (key TEXT PRIMARY KEY, value BLOB NOT NULL)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS destinations
                            (bot_id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
                             first_name TEXT NOT NULL)''')
        await db.commit()

async def set_secret(key: str, value: str):
    encrypted = _cipher.encrypt(value.encode())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",
                         (key, encrypted))
        await db.commit()

async def get_secret(key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key=?", (key,)) as cur:
            row = await cur.fetchone()
    return _cipher.decrypt(row[0]).decode() if row else None

async def delete_secret(key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM settings WHERE key=?", (key,))
        await db.commit()

async def list_destinations():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT bot_id,username,first_name FROM destinations ORDER BY first_name") as cur:
            return await cur.fetchall()

async def add_destination(bot_id: int, username: str, first_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        count = (await (await db.execute("SELECT COUNT(*) FROM destinations")).fetchone())[0]
        if count >= 30:
            return "limit"
        try:
            await db.execute("INSERT INTO destinations(bot_id,username,first_name) VALUES(?,?,?)",
                             (bot_id, username.lower().lstrip("@"), first_name))
            await db.commit()
            return "added"
        except aiosqlite.IntegrityError:
            return "duplicate"

async def remove_destination(username: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM destinations WHERE lower(username)=lower(?)",
                               (username.lstrip("@"),))
        await db.commit()
        return cur.rowcount > 0
