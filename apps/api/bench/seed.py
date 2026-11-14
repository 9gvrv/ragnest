"""Seed a disposable benchmark workspace and index the Tarnwick corpus.

Retrieval experiments run in-process (spec D1), so documents are inserted
directly instead of uploaded: the product upload path is already covered by
``tests/modules/documents``, and this is the only way to swap the chunk target
per run without restarting a server.

Run from ``apps/api``:

    uv run python -m bench.seed --size 800
"""

import argparse
import asyncio
import time
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db import models as _models  # noqa: F401  (registers every mapper)
from app.db.session import SessionLocal, dispose_engine
from app.modules.documents.models import Document
from app.modules.retrieval import chunking
from app.modules.retrieval.constants import EMBEDDING_MODEL
from app.modules.retrieval.embeddings import GeminiEmbeddingProvider
from app.modules.retrieval.models import DocumentChunk
from app.modules.retrieval.service import index_document
from app.modules.users.models import User
from app.modules.workspaces.models import Workspace, WorkspaceMember, WorkspaceRole
from bench import common

BENCH_EMAIL = "bench@tarnwick.example"
OVERLAP_RATIO = 0.15  # spec D5: overlap scales with the target (120/800)
SEED_STATUSES = ("ready",)


async def get_or_create_user(session: AsyncSession) -> User:
    user = await session.scalar(select(User).where(User.email == BENCH_EMAIL))
    if user is None:
        user = User(email=BENCH_EMAIL, password_hash=None)
        session.add(user)
        await session.commit()
    return user


async def get_or_create_workspace(session: AsyncSession, name: str, user: User) -> Workspace:
    workspace = await session.scalar(select(Workspace).where(Workspace.name == name))
    if workspace is not None:
        return workspace
    workspace = Workspace(name=name, created_by=user.id)
    session.add(workspace)
    await session.flush()
    session.add(
        WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=WorkspaceRole.CREATOR)
    )
    await session.commit()
    return workspace


async def get_or_create_document(
    session: AsyncSession,
    workspace: Workspace,
    user: User,
    filename: str,
    text: str,
) -> Document:
    document = await session.scalar(
        select(Document).where(
            Document.workspace_id == workspace.id,
            Document.filename == filename,
        )
    )
    if document is not None:
        return document
    document = Document(
        workspace_id=workspace.id,
        uploaded_by=user.id,
        filename=filename,
        content_type="text/markdown",
        size_bytes=len(text.encode()),
        page_count=None,
        char_count=len(text),
        extracted_text=text,
    )
    session.add(document)
    await session.commit()
    return document


async def chunk_count(session: AsyncSession, document_id) -> int:
    return (
        await session.scalar(
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
        )
        or 0
    )


async def main(size: int, label: str | None) -> None:
    overlap = int(size * OVERLAP_RATIO)
    chunking.CHUNK_TARGET_CHARS = size
    chunking.CHUNK_OVERLAP_CHARS = overlap

    started = time.perf_counter()
    embeddings = GeminiEmbeddingProvider(settings.GEMINI_API)
    workspace_name = f"bench-{datetime.now(UTC):%Y-%m-%d}-{size}"

    async with SessionLocal() as session:
        user = await get_or_create_user(session)
        workspace = await get_or_create_workspace(session, workspace_name, user)

        rows = []
        for path in common.corpus_files():
            text = path.read_text()
            document = await get_or_create_document(session, workspace, user, path.name, text)
            reused = document.embedding_status in SEED_STATUSES
            if not reused:
                await index_document(document.id, SessionLocal, embeddings)
                await session.refresh(document)
            count = await chunk_count(session, document.id)
            rows.append(
                {
                    "filename": path.name,
                    "document_id": str(document.id),
                    "chars": len(text),
                    "chunks": count,
                    "status": document.embedding_status,
                    "reused": reused,
                }
            )
            print(f"{path.name:48s} {count:3d} chunks  {document.embedding_status}")

    elapsed = round(time.perf_counter() - started, 2)
    failed = [row["filename"] for row in rows if row["status"] != "ready"]
    payload = {
        "mode": "in_process",
        "git_sha": common.git_sha(),
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "corpus_hash": common.corpus_hash(),
        "workspace_id": str(workspace.id),
        "workspace_name": workspace_name,
        "embedding_model": EMBEDDING_MODEL,
        "chunk_target": size,
        "chunk_overlap": overlap,
        "documents": rows,
        "totals": {
            "documents": len(rows),
            "chunks": sum(row["chunks"] for row in rows),
            "failed": failed,
            "seconds": elapsed,
        },
    }
    out = common.run_dir(label) / "seed.json"
    # A rerun that reused every document must not overwrite the original
    # indexing time: that number cannot be re-measured without re-embedding.
    reused_all = all(row["reused"] for row in rows)
    if not reused_all:
        common.write_json(out, payload)

    print()
    print(f"workspace   {workspace_name}  ({workspace.id})")
    print(f"documents   {len(rows)}  failed={failed or 'none'}")
    print(f"chunks      {payload['totals']['chunks']}  in {elapsed}s")
    if reused_all:
        print(f"reused      everything already indexed; {out.name} left untouched")
    else:
        print(f"written     {out.relative_to(common.API_ROOT)}")
    await dispose_engine()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=int, default=800, help="chunk target characters")
    parser.add_argument("--label", default=None, help="run directory name")
    args = parser.parse_args()
    asyncio.run(main(args.size, args.label))
