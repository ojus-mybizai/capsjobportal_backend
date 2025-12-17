import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.file import File
from app.models.user import User


class FileService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.media_root = Path(settings.MEDIA_ROOT)
        self.media_root.mkdir(parents=True, exist_ok=True)

    async def save_upload(self, upload: UploadFile, uploaded_by: Optional[User]) -> File:
        ext = os.path.splitext(upload.filename or "")[1]
        generated_name = f"{uuid.uuid4()}{ext}"
        target_path = self.media_root / generated_name

        content = await upload.read()
        with open(target_path, "wb") as f:
            f.write(content)

        db_file = File(
            url=str(target_path),
            filename=upload.filename or generated_name,
            mimetype=upload.content_type,
            size=len(content),
            uploaded_by=uploaded_by.id if uploaded_by else None,
        )
        self.session.add(db_file)
        await self.session.commit()
        await self.session.refresh(db_file)
        return db_file

    async def get_file(self, file_id) -> Optional[File]:
        result = await self.session.get(File, file_id)
        return result
