"""unit attachments tests"""

import pytest
from ai.attachments import Attachment, contents_of, describe

from shared import (
    NOW,
    PNG_B64,
)


def test_an_attachment_is_a_url_or_data_and_never_both():
    assert (
        Attachment(url="https://example.com/cat.png").media_type == "image/png"
    )  # guessed
    assert Attachment(url="https://example.com/doc.pdf?sig=abc").kind == "document"
    assert Attachment(data=PNG_B64, media_type="image/png").kind == "image"
    assert Attachment(data=PNG_B64, media_type="audio/mpeg").kind == "audio"
    assert Attachment(data=PNG_B64, media_type="video/mp4").kind == "video"
    assert Attachment(data=PNG_B64, media_type="application/pdf").kind == "document"

    bad = [
        {},  # nothing
        {
            "url": "https://x.test/a.png",
            "data": PNG_B64,
            "media_type": "image/png",
        },  # both
        {"data": PNG_B64},  # no media type
        {"data": "not base64!!", "media_type": "image/png"},
        {"url": "ftp://x.test/a.png"},  # not http(s)
        {"url": "https://x.test/noextension"},  # type cannot be told
        {"data": PNG_B64, "media_type": "application/x-msdownload"},  # not for a model
    ]
    for fields in bad:
        with pytest.raises(ValueError):
            Attachment(**fields)


def test_attachments_become_what_pydantic_ai_sends():
    from pydantic_ai import AudioUrl, BinaryContent, DocumentUrl, ImageUrl

    contents = contents_of(
        [
            Attachment(url="https://x.test/cat.png"),
            Attachment(url="https://x.test/paper.pdf"),
            Attachment(url="https://x.test/talk.mp3"),
            Attachment(data=PNG_B64, media_type="image/png"),
        ]
    )
    assert [type(c) for c in contents] == [
        ImageUrl,
        DocumentUrl,
        AudioUrl,
        BinaryContent,
    ]
    assert contents[0].url == "https://x.test/cat.png"
    assert contents[3].is_image and contents[3].data.startswith(b"\x89PNG")


def test_the_history_keeps_a_note_of_a_file_not_the_file_or_its_url():
    secret_url = "https://x.test/cat.png?token=secret"
    note = Attachment(url=secret_url, name="cat.png").note()
    assert note == {"media_type": "image/png", "kind": "image", "name": "cat.png"}
    assert "secret" not in str(note)

    note = Attachment(data=PNG_B64, media_type="image/png").note()
    assert PNG_B64 not in str(note) and "name" not in note
    assert describe(
        [
            {"kind": "image", "name": "cat.png"},
            {"kind": "document", "media_type": "application/pdf"},
        ]
    ) == ("[attached image: cat.png] [attached document: application/pdf]")
