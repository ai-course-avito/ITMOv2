"""Files that come with a message: images, documents, audio, video.

A client sends them as a URL the model provider can fetch, or as base64 data. Only
what the model needs is passed on; the history keeps a note that a file was there
(its type and name), not the file."""

import base64
import binascii
import mimetypes
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, Field, model_validator
from pydantic_ai import AudioUrl, BinaryContent, DocumentUrl, ImageUrl, VideoUrl

_KINDS = ("image", "audio", "video")
# what is not image/audio/video but is a document the models read
_DOCUMENT_TYPES = (
    "application/pdf",
    "text/plain",
    "text/markdown",
    "text/csv",
    "text/html",
)


def kind_of(media_type: str) -> Optional[str]:
    """image | audio | video | document, or None for what cannot be sent to a model."""
    main = media_type.split("/")[0]
    if main in _KINDS:
        return main
    if media_type in _DOCUMENT_TYPES:
        return "document"
    return None


class Attachment(BaseModel):
    """A file for the model: give either `url` or `data` (base64)."""

    url: Optional[str] = Field(
        None, description="http(s) URL the model provider can fetch"
    )
    data: Optional[str] = Field(None, description="the file, base64-encoded")
    media_type: Optional[str] = Field(
        None,
        description="e.g. image/png or application/pdf; required with `data`, "
        "guessed from the URL otherwise",
    )
    name: Optional[str] = Field(None, description="a file name, shown in the history")

    @model_validator(mode="after")
    def check(self) -> "Attachment":
        if (self.url is None) == (self.data is None):
            raise ValueError("give either `url` or `data`")

        if self.data is not None:
            if not self.media_type:
                raise ValueError("`media_type` is required with `data`")
            try:
                base64.b64decode(self.data, validate=True)
            except (binascii.Error, ValueError):
                raise ValueError("`data` is not valid base64")
        else:
            if not self.url.startswith(("http://", "https://")):
                raise ValueError("`url` must be an http(s) URL")
            if not self.media_type:
                self.media_type = mimetypes.guess_type(self.url.split("?")[0])[0]
            if not self.media_type:
                raise ValueError(
                    "`media_type` is required: it cannot be told from the URL"
                )

        if kind_of(self.media_type) is None:
            raise ValueError(
                f"{self.media_type} is not supported: use an image, audio, video, "
                "PDF or text file"
            )
        return self

    @property
    def kind(self) -> str:
        return kind_of(self.media_type)

    def to_content(self):
        """The object pydantic-ai puts in the user prompt."""
        if self.data is not None:
            return BinaryContent(
                data=base64.b64decode(self.data), media_type=self.media_type
            )
        url_type = {
            "image": ImageUrl,
            "audio": AudioUrl,
            "video": VideoUrl,
            "document": DocumentUrl,
        }[self.kind]
        return url_type(url=self.url, media_type=self.media_type)

    def note(self) -> Dict[str, Any]:
        """What the history keeps: no data, no URL (it may carry a secret)."""
        note: Dict[str, Any] = {"media_type": self.media_type, "kind": self.kind}
        if self.name:
            note["name"] = self.name
        return note


def contents_of(attachments: Sequence[Attachment]) -> List[Any]:
    return [attachment.to_content() for attachment in attachments]


def describe(notes: Sequence[Dict[str, Any]]) -> str:
    """The attachments of an old message in words, for the model that reads the history."""
    parts = []
    for note in notes:
        label = note.get("kind", "file")
        detail = note.get("name") or note.get("media_type", "")
        parts.append(
            f"[attached {label}: {detail}]" if detail else f"[attached {label}]"
        )
    return " ".join(parts)
