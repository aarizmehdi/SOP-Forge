"""
SOP Forge — Evidence model.
Tracks supporting evidence files uploaded for requests.
"""

import uuid
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class Evidence(BaseModel):
    """Supporting evidence file linked to a request."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    request_id: str
    original_filename: str
    stored_filename: str
    storage_path: str
    content_type: str
    size_bytes: int
    uploaded_by: str
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"from_attributes": True}
