#!/usr/bin/env python3
import asyncio
import fcntl
import json
import os
from pathlib import Path
import sys

from fastapi import HTTPException
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.v1.auth.principal import AuthPrincipal
from models.sql.user import User
from services.database import async_session_maker
from services.enterprise.delivery_center_service import run_all_workspace_delivery_integrity_scans


async def run() -> dict:
    async with async_session_maker() as session:
        admin = await session.scalar(
            select(User).where(User.is_superuser.is_(True), User.is_active.is_(True)).order_by(User.created_at.asc())
        )
        if admin is None:
            raise RuntimeError("An active platform administrator is required")
        principal = AuthPrincipal(user_id=admin.id, username=admin.username, is_admin=True, method="api_key")
        timeout_seconds = int(os.getenv("ENTERPRISE_DELIVERY_INTEGRITY_TIMEOUT_SECONDS", "1800"))
        return await run_all_workspace_delivery_integrity_scans(
            session,
            principal=principal,
            source="cli",
            timeout_seconds=timeout_seconds,
        )


def main() -> int:
    lock_path = os.getenv("ENTERPRISE_DELIVERY_INTEGRITY_LOCK", "/tmp/presenton-delivery-integrity.lock")
    with open(lock_path, "w", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({"status": "skipped", "reason": "already_running"}))
            return 0
        try:
            report = asyncio.run(run())
        except HTTPException as exc:
            if exc.status_code == 409:
                print(json.dumps({"status": "skipped", "reason": "already_running", "detail": exc.detail}))
                return 0
            print(json.dumps({"status": "error", "detail": str(exc.detail)}, ensure_ascii=False), file=sys.stderr)
            return 1
        except Exception as exc:
            print(json.dumps({"status": "error", "detail": str(exc)}, ensure_ascii=False), file=sys.stderr)
            return 1
        print(json.dumps(report, ensure_ascii=False, default=str))
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
