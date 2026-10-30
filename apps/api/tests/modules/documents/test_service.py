from datetime import datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.modules.documents.extraction import UnsupportedType
from app.modules.documents.models import Document
from app.modules.documents.service import (
    can_manage,
    delete_document,
    get_document,
    ingest,
    list_documents,
)
from app.modules.users.models import User
from app.modules.workspaces.models import Workspace, WorkspaceMember, WorkspaceRole


async def seed_workspace(session_factory):
    async with session_factory() as session:
        creator = User(email="creator@example.com", password_hash="not-used")
        admin = User(email="admin@example.com", password_hash="not-used")
        member = User(email="member@example.com", password_hash="not-used")
        session.add_all([creator, admin, member])
        await session.flush()

        workspace = Workspace(name="Acme", created_by=creator.id)
        session.add(workspace)
        await session.flush()

        creator_member = WorkspaceMember(
            workspace_id=workspace.id, user_id=creator.id, role=WorkspaceRole.CREATOR
        )
        admin_member = WorkspaceMember(
            workspace_id=workspace.id, user_id=admin.id, role=WorkspaceRole.ADMIN
        )
        plain_member = WorkspaceMember(
            workspace_id=workspace.id, user_id=member.id, role=WorkspaceRole.MEMBER
        )
        session.add_all([creator_member, admin_member, plain_member])
        await session.commit()

        return {
            "workspace": workspace,
            "creator": creator,
            "admin": admin,
            "member": member,
            "creator_member": creator_member,
            "admin_member": admin_member,
            "plain_member": plain_member,
        }


async def add_document(
    session_factory,
    workspace_id,
    uploaded_by,
    filename="doc.txt",
    text="document text",
    created_at=None,
) -> Document:
    async with session_factory() as session:
        document = Document(
            workspace_id=workspace_id,
            uploaded_by=uploaded_by,
            filename=filename,
            content_type="text/plain",
            size_bytes=len(text),
            page_count=None,
            char_count=len(text),
            extracted_text=text,
        )
        if created_at is not None:
            document.created_at = created_at
        session.add(document)
        await session.commit()
        await session.refresh(document)
        return document


async def test_ingest_stores_extracted_text_and_counts(session_factory):
    seed = await seed_workspace(session_factory)

    async with session_factory() as session:
        document = await ingest(
            session, seed["workspace"].id, seed["member"].id, "notes.txt", b"hello world"
        )

    assert document.filename == "notes.txt"
    assert document.content_type == "text/plain"
    assert document.size_bytes == len(b"hello world")
    assert document.page_count is None
    assert document.extracted_text == "hello world"
    assert document.char_count == len("hello world")
    assert document.created_at is not None


async def test_ingest_uses_safe_basename(session_factory):
    seed = await seed_workspace(session_factory)

    async with session_factory() as session:
        document = await ingest(
            session, seed["workspace"].id, seed["member"].id, "../../etc/passwd.txt", b"root"
        )

    assert document.filename == "passwd.txt"


async def test_ingest_failure_writes_no_row(session_factory):
    seed = await seed_workspace(session_factory)

    with pytest.raises(UnsupportedType):
        async with session_factory() as session:
            await ingest(session, seed["workspace"].id, seed["member"].id, "wrong.bin", b"\x00\x01")

    async with session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(Document))

    assert count == 0


async def test_list_is_newest_first(session_factory):
    seed = await seed_workspace(session_factory)
    older = await add_document(
        session_factory,
        seed["workspace"].id,
        seed["member"].id,
        filename="older.txt",
        created_at=datetime(2026, 1, 1, 12, 0),
    )
    newer = await add_document(
        session_factory,
        seed["workspace"].id,
        seed["member"].id,
        filename="newer.txt",
        created_at=datetime(2026, 1, 2, 12, 0),
    )

    async with session_factory() as session:
        documents = await list_documents(session, seed["workspace"].id)

    assert [d.id for d in documents] == [newer.id, older.id]


async def test_list_mine_filters_by_uploader(session_factory):
    seed = await seed_workspace(session_factory)
    mine = await add_document(
        session_factory, seed["workspace"].id, seed["member"].id, filename="mine.txt"
    )
    await add_document(
        session_factory, seed["workspace"].id, seed["admin"].id, filename="theirs.txt"
    )

    async with session_factory() as session:
        documents = await list_documents(session, seed["workspace"].id, mine=seed["member"].id)

    assert [d.id for d in documents] == [mine.id]


async def test_list_mine_with_no_uploads_returns_empty(session_factory):
    seed = await seed_workspace(session_factory)

    async with session_factory() as session:
        documents = await list_documents(session, seed["workspace"].id, mine=seed["member"].id)

    assert documents == []


async def test_get_document_from_other_workspace_raises_404(session_factory):
    seed = await seed_workspace(session_factory)
    document = await add_document(session_factory, seed["workspace"].id, seed["member"].id)

    async with session_factory() as session:
        other_workspace = Workspace(name="Other", created_by=seed["creator"].id)
        session.add(other_workspace)
        await session.commit()

        with pytest.raises(HTTPException) as excinfo:
            await get_document(session, other_workspace.id, document.id)

    assert excinfo.value.status_code == 404


def test_can_manage_uploader_true():
    seed = _members()
    document = _document(uploaded_by=seed["plain_member"].user_id)

    assert can_manage(seed["plain_member"], document)


def test_can_manage_creator_true():
    seed = _members()
    document = _document(uploaded_by=seed["plain_member"].user_id)

    assert can_manage(seed["creator_member"], document)


def test_can_manage_admin_true():
    seed = _members()
    document = _document(uploaded_by=seed["plain_member"].user_id)

    assert can_manage(seed["admin_member"], document)


def test_can_manage_other_member_false():
    seed = _members()
    document = _document(uploaded_by=seed["admin"].id)

    assert not can_manage(seed["plain_member"], document)


async def test_delete_other_members_document_raises_403(session_factory):
    seed = await seed_workspace(session_factory)
    document = await add_document(
        session_factory, seed["workspace"].id, seed["admin"].id, filename="theirs.txt"
    )

    async with session_factory() as session:
        member = await session.get(WorkspaceMember, seed["plain_member"].id)
        with pytest.raises(HTTPException) as excinfo:
            await delete_document(session, seed["workspace"].id, document.id, member)

    assert excinfo.value.status_code == 403

    async with session_factory() as session:
        assert await session.get(Document, document.id) is not None


async def test_delete_own_document_removes_row(session_factory):
    seed = await seed_workspace(session_factory)
    document = await add_document(session_factory, seed["workspace"].id, seed["member"].id)

    async with session_factory() as session:
        member = await session.get(WorkspaceMember, seed["plain_member"].id)
        await delete_document(session, seed["workspace"].id, document.id, member)

    async with session_factory() as session:
        assert await session.get(Document, document.id) is None


def _members() -> dict:
    """In-memory membership rows; the predicate needs no database."""
    user_ids = [uuid4(), uuid4(), uuid4()]
    return {
        "creator": User(id=user_ids[0]),
        "admin": User(id=user_ids[1]),
        "member": User(id=user_ids[2]),
        "creator_member": WorkspaceMember(user_id=user_ids[0], role=WorkspaceRole.CREATOR),
        "admin_member": WorkspaceMember(user_id=user_ids[1], role=WorkspaceRole.ADMIN),
        "plain_member": WorkspaceMember(user_id=user_ids[2], role=WorkspaceRole.MEMBER),
    }


def _document(uploaded_by) -> Document:
    return Document(uploaded_by=uploaded_by)
