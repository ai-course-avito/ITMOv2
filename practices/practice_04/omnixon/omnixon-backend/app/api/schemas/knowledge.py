from typing import Optional

from pydantic import BaseModel


class RAGCreate(BaseModel):
    content: str
    embedding_content: Optional[str] = None
    metadata: Optional[dict] = None


class RAGUpdate(BaseModel):
    content: str
    embedding_content: Optional[str] = None
    metadata: Optional[dict] = None
