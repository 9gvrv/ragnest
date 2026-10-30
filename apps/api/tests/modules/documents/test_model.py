from sqlalchemy import text

from app.modules.documents.models import Document
from app.modules.users.models import User
from app.modules.workspaces.models import Workspace


async def test_sqlite_foreign_keys_are_on(session_factory):
    async with session_factory() as session:
        result = await session.execute(text("PRAGMA foreign_keys"))

    assert result.scalar() == 1


async def test_document_round_trip(session_factory):
    async with session_factory() as session:
        user = User(email="uploader@example.com", password_hash="not-used")
        session.add(user)
        await session.flush()

        workspace = Workspace(name="Acme", created_by=user.id)
        session.add(workspace)
        await session.flush()

        document = Document(
            workspace_id=workspace.id,
            uploaded_by=user.id,
            filename="notes.txt",
            content_type="text/plain",
            size_bytes=5,
            page_count=None,
            char_count=5,
            extracted_text="hello",
        )
        session.add(document)
        await session.commit()
        await session.refresh(document)
        document_id = document.id

    async with session_factory() as session:
        fetched = await session.get(Document, document_id)

    assert fetched is not None
    assert fetched.filename == "notes.txt"
    assert fetched.content_type == "text/plain"
    assert fetched.size_bytes == 5
    assert fetched.page_count is None
    assert fetched.char_count == 5
    assert fetched.extracted_text == "hello"
    assert fetched.created_at is not None
    assert fetched.updated_at is not None


async def test_deleting_workspace_cascades_documents(session_factory):
    async with session_factory() as session:
        user = User(email="uploader@example.com", password_hash="not-used")
        session.add(user)
        await session.flush()

        workspace = Workspace(name="Acme", created_by=user.id)
        session.add(workspace)
        await session.flush()

        document = Document(
            workspace_id=workspace.id,
            uploaded_by=user.id,
            filename="notes.txt",
            content_type="text/plain",
            size_bytes=3,
            page_count=None,
            char_count=3,
            extracted_text="bye",
        )
        session.add(document)
        await session.commit()
        document_id = document.id

    async with session_factory() as session:
        workspace = await session.get(Workspace, workspace.id)
        await session.delete(workspace)
        await session.commit()

    async with session_factory() as session:
        assert await session.get(Document, document_id) is None
