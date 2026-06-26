import time
from typing import Any

import aiosqlite

from app.config import DB_PATH
from app.models.user import UserStatus


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,

                accepted_rules INTEGER DEFAULT 0,
                rules_version TEXT,
                rules_accepted_at INTEGER,

                accepted_letter INTEGER DEFAULT 0,
                letter_version TEXT,
                letter_accepted_at INTEGER,

                surname TEXT,
                given_name TEXT,
                patronymic TEXT,
                phone TEXT,
                city TEXT,
                church_name TEXT,
                questionnaire_completed INTEGER DEFAULT 0,
                questionnaire_completed_at INTEGER,

                accepted_pd INTEGER DEFAULT 0,
                pd_version TEXT,
                pd_accepted_at INTEGER,

                invite_link TEXT,
                joined INTEGER DEFAULT 0,
                joined_at INTEGER,

                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )
        await _migrate_db(db)
        await db.commit()


async def _migrate_db(db: aiosqlite.Connection) -> None:
    cursor = await db.execute("PRAGMA table_info(users)")
    existing = {row[1] for row in await cursor.fetchall()}
    new_columns = [
        ("surname", "TEXT"),
        ("given_name", "TEXT"),
        ("patronymic", "TEXT"),
        ("phone", "TEXT"),
        ("city", "TEXT"),
        ("church_name", "TEXT"),
        ("questionnaire_completed", "INTEGER DEFAULT 0"),
        ("questionnaire_completed_at", "INTEGER"),
    ]
    for name, typedef in new_columns:
        if name not in existing:
            await db.execute(f"ALTER TABLE users ADD COLUMN {name} {typedef}")


async def upsert_user(message_or_callback) -> None:
    user = message_or_callback.from_user
    now = int(time.time())

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO users (
                telegram_id, username, first_name, last_name, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                last_name=excluded.last_name,
                updated_at=excluded.updated_at
            """,
            (
                user.id,
                user.username,
                user.first_name,
                user.last_name,
                now,
                now,
            ),
        )
        await db.commit()


async def set_accepted(
    user_id: int,
    field: str,
    version_field: str,
    accepted_at_field: str,
    version: str,
) -> None:
    allowed = {
        "accepted_rules": ("rules_version", "rules_accepted_at"),
        "accepted_pd": ("pd_version", "pd_accepted_at"),
    }

    if field not in allowed:
        raise ValueError("Invalid field")

    expected_version_field, expected_accepted_at_field = allowed[field]
    if version_field != expected_version_field or accepted_at_field != expected_accepted_at_field:
        raise ValueError("Invalid version/accepted_at field")

    now = int(time.time())

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"""
            UPDATE users
            SET {field}=1,
                {version_field}=?,
                {accepted_at_field}=?,
                updated_at=?
            WHERE telegram_id=?
            """,
            (version, now, now, user_id),
        )
        await db.commit()


async def get_status(user_id: int) -> UserStatus | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        row = await db.execute_fetchall(
            """
            SELECT telegram_id, accepted_rules, questionnaire_completed, accepted_pd
            FROM users
            WHERE telegram_id=?
            """,
            (user_id,),
        )

    if not row:
        return None

    item = row[0]
    return UserStatus(
        telegram_id=item["telegram_id"],
        accepted_rules=bool(item["accepted_rules"]),
        questionnaire_completed=bool(item["questionnaire_completed"]),
        accepted_pd=bool(item["accepted_pd"]),
    )


async def save_invite_link(user_id: int, invite_link: str) -> None:
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE users
            SET invite_link=?, updated_at=?
            WHERE telegram_id=?
            """,
            (invite_link, now, user_id),
        )
        await db.commit()


async def mark_joined(user_id: int) -> None:
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE users
            SET joined=1, joined_at=?, updated_at=?
            WHERE telegram_id=?
            """,
            (now, now, user_id),
        )
        await db.commit()


async def save_name(user_id: int, surname: str, given_name: str, patronymic: str) -> None:
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE users
            SET surname=?, given_name=?, patronymic=?, updated_at=?
            WHERE telegram_id=?
            """,
            (surname, given_name, patronymic or None, now, user_id),
        )
        await db.commit()


async def save_phone(user_id: int, phone: str) -> None:
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET phone=?, updated_at=? WHERE telegram_id=?",
            (phone, now, user_id),
        )
        await db.commit()


async def save_city(user_id: int, city: str) -> None:
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET city=?, updated_at=? WHERE telegram_id=?",
            (city, now, user_id),
        )
        await db.commit()


async def save_church_and_complete(user_id: int, church_name: str) -> None:
    now = int(time.time())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            UPDATE users
            SET church_name=?, questionnaire_completed=1,
                questionnaire_completed_at=?, updated_at=?
            WHERE telegram_id=?
            """,
            (church_name, now, now, user_id),
        )
        await db.commit()


async def fetch_stage_counts(stages: dict[str, dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    async with aiosqlite.connect(DB_PATH) as db:
        for key, meta in stages.items():
            cursor = await db.execute(
                f"SELECT COUNT(*) FROM users WHERE {meta['where']}"
            )
            row = await cursor.fetchone()
            counts[key] = row[0] if row else 0
    return counts


async def fetch_users(
    stage: str,
    stages: dict[str, dict[str, str]],
    page: int,
    per_page: int,
) -> tuple[list[dict[str, Any]], int]:
    if stage not in stages:
        raise ValueError("Unknown stage")

    where = stages[stage]["where"]
    offset = page * per_page

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        count_cursor = await db.execute(f"SELECT COUNT(*) FROM users WHERE {where}")
        count_row = await count_cursor.fetchone()
        total = count_row[0] if count_row else 0

        cursor = await db.execute(
            f"""
            SELECT
                telegram_id, username, first_name, last_name,
                surname, given_name, patronymic,
                accepted_rules, accepted_letter, accepted_pd, joined,
                questionnaire_completed,
                created_at, joined_at
            FROM users
            WHERE {where}
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
            """,
            (per_page, offset),
        )
        rows = await cursor.fetchall()

    return [dict(row) for row in rows], total


async def fetch_form_users(
    filter_key: str,
    form_filters: dict[str, dict[str, Any]],
    page: int,
    per_page: int,
) -> tuple[list[dict[str, Any]], int]:
    if filter_key not in form_filters:
        raise ValueError("Unknown form filter")

    meta = form_filters[filter_key]
    where = meta["where"]
    params: list[Any] = list(meta["params"])
    offset = page * per_page

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        count_cursor = await db.execute(
            f"SELECT COUNT(*) FROM users WHERE {where}",
            params,
        )
        count_row = await count_cursor.fetchone()
        total = count_row[0] if count_row else 0

        cursor = await db.execute(
            f"""
            SELECT
                telegram_id, username, first_name, last_name,
                surname, given_name, patronymic,
                phone, city, church_name,
                accepted_rules, accepted_pd, joined, questionnaire_completed
            FROM users
            WHERE {where}
            ORDER BY
                CASE WHEN questionnaire_completed_at IS NULL THEN 0 ELSE 1 END DESC,
                questionnaire_completed_at DESC,
                updated_at DESC
            LIMIT ? OFFSET ?
            """,
            (*params, per_page, offset),
        )
        rows = await cursor.fetchall()

    return [dict(row) for row in rows], total


async def fetch_user_by_id(telegram_id: int) -> dict[str, Any] | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT
                telegram_id, username, first_name, last_name,
                surname, given_name, patronymic,
                accepted_rules, accepted_letter, accepted_pd, joined,
                questionnaire_completed
            FROM users
            WHERE telegram_id = ?
            """,
            (telegram_id,),
        )
        row = await cursor.fetchone()

    return dict(row) if row else None


async def fetch_all_user_ids() -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT telegram_id FROM users ORDER BY telegram_id")
        rows = await cursor.fetchall()
    return [row[0] for row in rows]
