"""api attachments tests"""

import base64
import struct
import zlib
import json
import pytest

from shared import (
    collect_sse,
    history_of,
)


def solid_png(rgb, size=16) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    rows = b"".join(b"\x00" + bytes(rgb) * size for _ in range(size))
    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def png_attachment(rgb, name="square.png") -> dict:
    return {
        "data": base64.b64encode(solid_png(rgb)).decode(),
        "media_type": "image/png",
        "name": name,
    }


@pytest.mark.asyncio
@pytest.mark.order(20)
async def test_the_model_sees_an_attached_image(client, vision_model):
    user_id = "attachment_user"
    ask = "What colour is this image? Answer with one word, in English."
    try:
        res = await client.post(
            "/api/v1/request",
            json={
                "user_id": user_id,
                "request": ask,
                "attachments": [png_attachment((255, 0, 0))],
            },
        )
        assert res.status_code == 200
        assert "red" in res.json()["response"].lower()

        res = await client.post(
            "/api/v1/request",
            json={
                "user_id": user_id,
                "request": ask,
                "attachments": [png_attachment((0, 0, 255))],
                "use_memo": False,
            },
        )
        assert "blue" in res.json()["response"].lower()
    finally:
        await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(20)
async def test_the_model_sees_an_attached_image_in_a_stream(client, vision_model):
    user_id = "attachment_stream_user"
    try:
        result = await collect_sse(
            client,
            user_id,
            "What colour is this image? Answer with one word, in English.",
            attachments=[png_attachment((0, 160, 0))],
        )
        assert result["error"] is None
        assert "green" in "".join(result["chunks"]).lower()
    finally:
        await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(20)
async def test_the_history_notes_the_file_but_does_not_keep_it(client, vision_model):
    user_id = "attachment_history_user"
    attachment = png_attachment((255, 0, 0), name="red.png")
    try:
        await client.post(
            "/api/v1/request",
            json={
                "user_id": user_id,
                "request": "What colour? One word.",
                "attachments": [attachment],
            },
        )
        stored = (await history_of(client, user_id))[0]["content"]
        assert stored["attachments"] == [
            {"media_type": "image/png", "kind": "image", "name": "red.png"}
        ]
        assert attachment["data"] not in json.dumps(stored)

        # a follow-up works: the model is told that a file was there
        res = await client.post(
            "/api/v1/request",
            json={
                "user_id": user_id,
                "request": "Was there a picture in my first message? Yes or no.",
            },
        )
        assert res.status_code == 200
    finally:
        await client.delete(f"/api/v1/users/{user_id}")


@pytest.mark.asyncio
@pytest.mark.order(20)
async def test_bad_attachments_are_rejected(client):
    good = png_attachment((255, 0, 0))
    bad = [
        {},
        {**good, "url": "https://example.com/a.png"},  # both
        {"data": good["data"]},  # no media type
        {"data": "###", "media_type": "image/png"},
        {"url": "ftp://example.com/a.png"},
        {"data": good["data"], "media_type": "application/x-msdownload"},
    ]
    for attachment in bad:
        res = await client.post(
            "/api/v1/request",
            json={
                "user_id": "bad_attachment_user",
                "request": "hi",
                "attachments": [attachment],
            },
        )
        assert res.status_code == 422, attachment
    assert (
        await client.get("/api/v1/users/bad_attachment_user")
    ).status_code == 404  # nothing was created


@pytest.mark.asyncio
@pytest.mark.order(20)
async def test_a_model_that_cannot_see_gives_a_provider_error_not_a_crash(client):
    # a text-only model: the answer is 502 with the provider's reason, or the model
    # ignores the picture; either way the service stays healthy
    agent_id = (await client.get("/api/v1/agents/self")).json()["id"]
    res = await client.post(
        "/api/v1/admin/models",
        json={
            "name": "test",
            "request_json": {"model": "openai/gpt-6-luna"},
        },
    )
    model_id = res.json()["id"]
    await client.patch(f"/api/v1/admin/agents/{agent_id}", json={"model_id": model_id})
    user_id = "blind_model_user"
    try:
        res = await client.post(
            "/api/v1/request",
            json={
                "user_id": user_id,
                "request": "What colour?",
                "attachments": [png_attachment((255, 0, 0))],
                "save_message": False,
            },
        )
        assert res.status_code in (200, 502)
        assert (await client.get("/api/v1/")).status_code == 200
    finally:
        await client.patch(f"/api/v1/admin/agents/{agent_id}", json={"model_id": 0})
        await client.delete(f"/api/v1/admin/models/{model_id}")
        await client.delete(f"/api/v1/users/{user_id}")
