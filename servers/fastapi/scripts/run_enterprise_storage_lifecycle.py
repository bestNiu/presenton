#!/usr/bin/env python3
import argparse
import asyncio
import fcntl
import json
import os
from pathlib import Path
import sys

from sqlalchemy import select


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.v1.auth.principal import AuthPrincipal
from models.sql.user import User
from services.database import async_session_maker
from services.enterprise.storage_lifecycle_service import run_storage_lifecycle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan or clean enterprise object storage lifecycle candidates."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Delete eligible objects. Omit for the safe dry-run default.",
    )
    parser.add_argument("--max-delete", type=int, default=100)
    return parser.parse_args()


async def run(*, execute: bool, max_delete: int) -> dict:
    if not 1 <= max_delete <= 1000:
        raise ValueError("--max-delete must be between 1 and 1000")
    async with async_session_maker() as session:
        admin = await session.scalar(
            select(User)
            .where(User.is_superuser.is_(True), User.is_active.is_(True))
            .order_by(User.created_at.asc())
        )
        if admin is None:
            raise RuntimeError("An active platform administrator is required")
        principal = AuthPrincipal(
            user_id=admin.id,
            username=admin.username,
            is_admin=True,
            method="api_key",
        )
        return await run_storage_lifecycle(
            session,
            principal=principal,
            execute=execute,
            max_delete=max_delete,
        )


def main() -> int:
    args = parse_args()
    lock_path = os.getenv(
        "ENTERPRISE_OBJECT_STORAGE_LIFECYCLE_LOCK",
        "/tmp/presenton-enterprise-storage-lifecycle.lock",
    )
    with open(lock_path, "w", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({"status": "skipped", "reason": "already_running"}))
            return 0
        try:
            report = asyncio.run(run(execute=args.execute, max_delete=args.max_delete))
        except Exception as exc:
            print(
                json.dumps(
                    {"status": "error", "detail": str(exc)}, ensure_ascii=False
                ),
                file=sys.stderr,
            )
            return 1
        print(json.dumps(report, ensure_ascii=False, default=str))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
