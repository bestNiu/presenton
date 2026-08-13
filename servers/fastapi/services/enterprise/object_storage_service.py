import asyncio
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
from typing import AsyncIterator
from urllib.parse import quote
import uuid

from fastapi import HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from starlette.responses import Response

from utils.get_env import get_app_data_directory_env


@dataclass(frozen=True)
class StoredObject:
    object_key: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class StoredObjectLocation:
    object_key: str | None = None
    legacy_path: str | None = None


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_object_key(object_key: str) -> str:
    normalized = object_key.strip().replace("\\", "/")
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("Invalid enterprise object key")
    return str(path)


class EnterpriseObjectStorage:
    """Private object storage used by enterprise artifacts.

    Local storage is the development default. The S3 backend supports AWS S3 and
    compatible services such as MinIO without exposing bucket paths to clients.
    """

    def __init__(self) -> None:
        self.backend = os.getenv("ENTERPRISE_OBJECT_STORAGE_BACKEND", "local").strip().lower()
        if self.backend not in {"local", "s3"}:
            raise RuntimeError("ENTERPRISE_OBJECT_STORAGE_BACKEND must be local or s3")

    def _local_root(self) -> Path:
        configured = os.getenv("ENTERPRISE_OBJECT_STORAGE_LOCAL_ROOT", "").strip()
        app_data = get_app_data_directory_env()
        root = configured or (str(Path(app_data) / "enterprise-objects") if app_data else "")
        if not root:
            raise RuntimeError(
                "APP_DATA_DIRECTORY or ENTERPRISE_OBJECT_STORAGE_LOCAL_ROOT is required for local object storage"
            )
        path = Path(root).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _local_path(self, object_key: str) -> Path:
        root = self._local_root()
        path = (root / _normalize_object_key(object_key)).resolve()
        if os.path.commonpath([str(root), str(path)]) != str(root):
            raise ValueError("Invalid enterprise object key")
        return path

    def _s3_settings(self) -> tuple[str, dict]:
        bucket = os.getenv("ENTERPRISE_OBJECT_STORAGE_BUCKET", "").strip()
        if not bucket:
            raise RuntimeError("ENTERPRISE_OBJECT_STORAGE_BUCKET is required for s3 object storage")
        kwargs: dict = {}
        mappings = {
            "endpoint_url": "ENTERPRISE_OBJECT_STORAGE_ENDPOINT_URL",
            "region_name": "ENTERPRISE_OBJECT_STORAGE_REGION",
            "aws_access_key_id": "ENTERPRISE_OBJECT_STORAGE_ACCESS_KEY",
            "aws_secret_access_key": "ENTERPRISE_OBJECT_STORAGE_SECRET_KEY",
        }
        for argument, environment_name in mappings.items():
            value = os.getenv(environment_name, "").strip()
            if value:
                kwargs[argument] = value
        return bucket, kwargs

    def _s3_client(self):
        import boto3
        from botocore.config import Config

        _, kwargs = self._s3_settings()
        addressing_style = os.getenv(
            "ENTERPRISE_OBJECT_STORAGE_ADDRESSING_STYLE", "path"
        ).strip()
        kwargs["config"] = Config(
            signature_version="s3v4", s3={"addressing_style": addressing_style}
        )
        return boto3.client("s3", **kwargs)

    async def put_file(
        self, source_path: str, object_key: str, *, content_type: str
    ) -> StoredObject:
        source = os.path.realpath(source_path)
        if not os.path.isfile(source):
            raise FileNotFoundError(source)
        key = _normalize_object_key(object_key)
        sha256 = await asyncio.to_thread(_sha256, source)
        size_bytes = os.path.getsize(source)
        if self.backend == "local":
            destination = self._local_path(key)
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
            await asyncio.to_thread(shutil.copyfile, source, temporary)
            os.chmod(temporary, 0o640)
            os.replace(temporary, destination)
        else:
            bucket, _ = self._s3_settings()
            client = self._s3_client()
            await asyncio.to_thread(
                client.upload_file,
                source,
                bucket,
                key,
                ExtraArgs={
                    "ContentType": content_type,
                    "Metadata": {"sha256": sha256},
                },
            )
        return StoredObject(object_key=key, sha256=sha256, size_bytes=size_bytes)

    async def verify(
        self,
        location: StoredObjectLocation,
        *,
        expected_sha256: str | None = None,
        expected_size: int | None = None,
    ) -> None:
        if location.object_key:
            key = _normalize_object_key(location.object_key)
            if self.backend == "local":
                path = self._local_path(key)
                if not path.is_file():
                    raise HTTPException(status_code=404, detail="Stored object not found")
                if expected_size is not None and path.stat().st_size != expected_size:
                    raise HTTPException(status_code=409, detail="Stored object integrity check failed")
                if expected_sha256 and await asyncio.to_thread(_sha256, str(path)) != expected_sha256:
                    raise HTTPException(status_code=409, detail="Stored object integrity check failed")
                return
            bucket, _ = self._s3_settings()
            try:
                head = await asyncio.to_thread(self._s3_client().head_object, Bucket=bucket, Key=key)
            except Exception as exc:
                raise HTTPException(status_code=404, detail="Stored object not found") from exc
            if expected_size is not None and int(head.get("ContentLength", -1)) != expected_size:
                raise HTTPException(status_code=409, detail="Stored object integrity check failed")
            remote_hash = (head.get("Metadata") or {}).get("sha256")
            if expected_sha256 and remote_hash != expected_sha256:
                raise HTTPException(status_code=409, detail="Stored object integrity check failed")
            return

        path = os.path.realpath(location.legacy_path or "")
        if not path or not os.path.isfile(path):
            raise HTTPException(status_code=404, detail="Stored object not found")
        if expected_size is not None and os.path.getsize(path) != expected_size:
            raise HTTPException(status_code=409, detail="Stored object integrity check failed")
        if expected_sha256 and await asyncio.to_thread(_sha256, path) != expected_sha256:
            raise HTTPException(status_code=409, detail="Stored object integrity check failed")

    async def download_response(
        self,
        location: StoredObjectLocation,
        *,
        filename: str | None,
        media_type: str,
    ) -> Response:
        if not location.object_key:
            return FileResponse(
                os.path.realpath(location.legacy_path or ""),
                filename=filename,
                media_type=media_type,
            )
        key = _normalize_object_key(location.object_key)
        if self.backend == "local":
            return FileResponse(str(self._local_path(key)), filename=filename, media_type=media_type)

        bucket, _ = self._s3_settings()
        client = self._s3_client()
        try:
            result = await asyncio.to_thread(client.get_object, Bucket=bucket, Key=key)
        except Exception as exc:
            raise HTTPException(status_code=404, detail="Stored object not found") from exc
        body = result["Body"]

        async def chunks() -> AsyncIterator[bytes]:
            try:
                while chunk := await asyncio.to_thread(body.read, 1024 * 1024):
                    yield chunk
            finally:
                await asyncio.to_thread(body.close)

        headers = {}
        if result.get("ContentLength") is not None:
            headers["Content-Length"] = str(result["ContentLength"])
        if filename:
            safe_filename = filename.replace("\r", "").replace("\n", "")
            headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(safe_filename)}"
        return StreamingResponse(chunks(), media_type=media_type, headers=headers)


def get_enterprise_object_storage() -> EnterpriseObjectStorage:
    # Construct per operation so test and deployment configuration changes are explicit.
    return EnterpriseObjectStorage()
