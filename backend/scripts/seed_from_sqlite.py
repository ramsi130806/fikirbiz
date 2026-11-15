"""Migrate users from local SQLite (fikirbiz.db) into the configured DATABASE_URL.

Usage:
    python -m scripts.seed_from_sqlite --sqlite ./fikirbiz.db
"""
import argparse
import asyncio
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from app.core.database import async_session_factory  # noqa: E402
from app.models.user import User  # noqa: E402


def _parse_dt(val):
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    try:
        dt = datetime.fromisoformat(str(val))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


async def migrate(sqlite_path: str) -> None:
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM users").fetchall()
    conn.close()

    inserted = 0
    skipped = 0
    async with async_session_factory() as session:
        for r in rows:
            email = r["email"].strip().lower()
            exists = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if exists:
                skipped += 1
                continue
            user = User(
                id=r["id"],
                first_name=r["first_name"],
                last_name=r["last_name"],
                email=email,
                password_hash=r["password_hash"],
                role=r["role"],
                plan=r["plan"] if "plan" in r.keys() and r["plan"] else "basic",
                is_active=bool(r["is_active"]),
                is_approved=bool(r["is_approved"]) if "is_approved" in r.keys() else True,
                failed_attempts=r["failed_attempts"] or 0,
                locked_until=_parse_dt(r["locked_until"]),
                last_login_at=_parse_dt(r["last_login_at"]),
                created_at=_parse_dt(r["created_at"]) or datetime.now(timezone.utc),
                updated_at=_parse_dt(r["updated_at"]) or datetime.now(timezone.utc),
            )
            session.add(user)
            inserted += 1
        await session.commit()
    print(f"Done. Inserted: {inserted}, Skipped (already existed): {skipped}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--sqlite", default="fikirbiz.db", help="Path to source SQLite DB")
    args = p.parse_args()
    asyncio.run(migrate(args.sqlite))
