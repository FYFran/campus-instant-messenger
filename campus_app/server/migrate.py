"""迁移脚本 — 部署前运行"""
import asyncio, asyncpg, os, sys, logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), 'migrations')

async def main():
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_user = os.getenv("DB_USER", "campus_admin")
    db_pass = os.getenv("DB_PASSWORD", "")
    db_name = os.getenv("DB_NAME", "campus_app")
    dsn = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=1, command_timeout=30)
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                # Ensure migration tracking table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS _migrations (
                        id SERIAL PRIMARY KEY,
                        filename VARCHAR(255) UNIQUE NOT NULL,
                        applied_at TIMESTAMP DEFAULT NOW()
                    )
                """)
                # Run each migration in order
                files = sorted(f for f in os.listdir(MIGRATIONS_DIR)
                              if f.endswith('.sql') and f[0].isdigit())
                for fname in files:
                    applied = await conn.fetchval(
                        "SELECT 1 FROM _migrations WHERE filename=$1", fname)
                    if applied:
                        log.info(f"SKIP {fname} (already applied)")
                        continue
                    sql = open(os.path.join(MIGRATIONS_DIR, fname), encoding='utf-8').read()
                    await conn.execute(sql)
                    await conn.execute(
                        "INSERT INTO _migrations (filename) VALUES ($1)", fname)
                    log.info(f"DONE {fname}")
        log.info("All migrations applied.")
    finally:
        await pool.close()

if __name__ == '__main__':
    asyncio.run(main())
