import asyncio
import hashlib
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse
import pytest

from services.enterprise.object_storage_service import (
    EnterpriseObjectStorage,
    StoredObjectLocation,
)


def test_local_object_storage_round_trip_and_integrity(tmp_path, monkeypatch):
    root = tmp_path / "objects"
    source = tmp_path / "delivery.pdf"
    source.write_bytes(b"governed-enterprise-delivery")
    monkeypatch.setenv("ENTERPRISE_OBJECT_STORAGE_BACKEND", "local")
    monkeypatch.setenv("ENTERPRISE_OBJECT_STORAGE_LOCAL_ROOT", str(root))

    storage = EnterpriseObjectStorage()
    stored = asyncio.run(
        storage.put_file(
            str(source),
            "presentation-deliveries/workspace/artifact.pdf",
            content_type="application/pdf",
        )
    )
    location = StoredObjectLocation(object_key=stored.object_key)

    assert stored.sha256 == hashlib.sha256(source.read_bytes()).hexdigest()
    assert stored.size_bytes == len(source.read_bytes())
    asyncio.run(
        storage.verify(
            location,
            expected_sha256=stored.sha256,
            expected_size=stored.size_bytes,
        )
    )
    response = asyncio.run(
        storage.download_response(
            location, filename="交付版.pdf", media_type="application/pdf"
        )
    )
    assert isinstance(response, FileResponse)
    response_path = Path(response.path)
    assert root in response_path.resolve().parents
    assert response_path.read_bytes() == source.read_bytes()

    materialized = tmp_path / "materialized" / "delivery.pdf"
    asyncio.run(storage.download_to_file(stored.object_key, str(materialized)))
    assert materialized.read_bytes() == source.read_bytes()

    response_path.write_bytes(b"tampered")
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            storage.verify(
                location,
                expected_sha256=stored.sha256,
                expected_size=stored.size_bytes,
            )
        )
    assert exc_info.value.status_code == 409


def test_local_object_storage_inventory_and_delete(tmp_path, monkeypatch):
    source = tmp_path / "orphan.bin"
    source.write_bytes(b"orphan-object")
    monkeypatch.setenv("ENTERPRISE_OBJECT_STORAGE_BACKEND", "local")
    monkeypatch.setenv("ENTERPRISE_OBJECT_STORAGE_LOCAL_ROOT", str(tmp_path / "objects"))
    storage = EnterpriseObjectStorage()
    stored = asyncio.run(
        storage.put_file(
            str(source), "orphaned/workspace/object.bin", content_type="application/octet-stream"
        )
    )

    inventory = asyncio.run(storage.list_objects("orphaned"))

    assert [item.object_key for item in inventory] == [stored.object_key]
    assert inventory[0].size_bytes == len(b"orphan-object")
    assert asyncio.run(storage.delete_object(stored.object_key)) is True
    assert asyncio.run(storage.delete_object(stored.object_key)) is False
    assert asyncio.run(storage.list_objects()) == []


def test_object_storage_rejects_path_traversal(tmp_path, monkeypatch):
    source = tmp_path / "preview.png"
    source.write_bytes(b"preview")
    monkeypatch.setenv("ENTERPRISE_OBJECT_STORAGE_BACKEND", "local")
    monkeypatch.setenv("ENTERPRISE_OBJECT_STORAGE_LOCAL_ROOT", str(tmp_path / "objects"))

    with pytest.raises(ValueError, match="Invalid enterprise object key"):
        asyncio.run(
            EnterpriseObjectStorage().put_file(
                str(source), "../escaped.png", content_type="image/png"
            )
        )


def test_s3_object_storage_requires_private_bucket_configuration(monkeypatch):
    monkeypatch.setenv("ENTERPRISE_OBJECT_STORAGE_BACKEND", "s3")
    monkeypatch.delenv("ENTERPRISE_OBJECT_STORAGE_BUCKET", raising=False)

    with pytest.raises(RuntimeError, match="ENTERPRISE_OBJECT_STORAGE_BUCKET"):
        EnterpriseObjectStorage()._s3_settings()
