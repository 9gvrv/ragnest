from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    uploaded_by: UUID
    filename: str
    content_type: str
    size_bytes: int
    page_count: int | None
    char_count: int
    created_at: datetime


class DocumentDetail(DocumentSummary):
    extracted_text: str
