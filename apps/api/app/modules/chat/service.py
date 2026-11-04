import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.chat.constants import (
    CHAT_EXCERPT_CHARS,
    CHAT_HISTORY_MESSAGES,
    CHAT_TOP_K,
    DEFAULT_TITLE,
    NO_CONTEXT_REPLY,
)
from app.modules.chat.models import Conversation, Message, MessageRole
from app.modules.chat.prompts import PromptPlan, build_prompt, make_title
from app.modules.chat.schemas import Citation
from app.modules.retrieval.embeddings import EmbeddingProvider
from app.modules.retrieval.service import SearchHit, search

logger = logging.getLogger(__name__)


@dataclass
class PreparedExchange:
    conversation_id: UUID
    user_message: Message
    assistant_message_id: UUID
    plan: PromptPlan | None
    sources: list[SearchHit]
    no_context: bool


def _utcnow_naive() -> datetime:
    """TimestampMixin columns are TIMESTAMP WITHOUT TIME ZONE on Postgres.

    asyncpg rejects aware datetimes for them, so conversation timestamps stay
    naive UTC; message timestamps live in a timezone-aware column and keep UTC.
    """
    return datetime.now(UTC).replace(tzinfo=None)


async def create_conversation(
    session: AsyncSession,
    workspace_id: UUID,
    created_by: UUID,
    title: str | None = None,
) -> Conversation:
    now = _utcnow_naive()
    conversation = Conversation(
        workspace_id=workspace_id,
        created_by=created_by,
        title=title or DEFAULT_TITLE,
        created_at=now,
        updated_at=now,
    )
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def list_conversations(
    session: AsyncSession,
    workspace_id: UUID,
    created_by: UUID,
) -> list[Conversation]:
    stmt = (
        select(Conversation)
        .where(
            Conversation.workspace_id == workspace_id,
            Conversation.created_by == created_by,
        )
        .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_conversation(
    session: AsyncSession,
    workspace_id: UUID,
    conversation_id: UUID,
    created_by: UUID,
) -> Conversation:
    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.workspace_id == workspace_id,
        Conversation.created_by == created_by,
    )
    conversation = (await session.execute(stmt)).scalar_one_or_none()
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return conversation


async def delete_conversation(
    session: AsyncSession,
    workspace_id: UUID,
    conversation_id: UUID,
    created_by: UUID,
) -> None:
    conversation = await get_conversation(session, workspace_id, conversation_id, created_by)
    await session.delete(conversation)
    await session.commit()


async def list_messages(session: AsyncSession, conversation_id: UUID) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at, Message.id)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def prepare_exchange(
    session: AsyncSession,
    workspace_id: UUID,
    conversation: Conversation,
    question: str,
    embeddings: EmbeddingProvider,
) -> PreparedExchange:
    """Embed, retrieve, persist the question and (when empty) the refusal.

    The user row is committed before the model is called so a provider failure
    never loses the question. History is loaded before that insert, so the
    current question is not repeated to the model.
    """
    history = await _load_history(session, conversation.id)
    query_vector = await embeddings.embed_query(question)
    hits = await search(session, workspace_id, query_vector, CHAT_TOP_K)

    now = datetime.now(UTC)
    user_message = Message(
        id=uuid4(),
        conversation_id=conversation.id,
        role=MessageRole.USER.value,
        content=question,
        citations=[],
        created_at=now,
    )
    session.add(user_message)

    if conversation.title == DEFAULT_TITLE:
        conversation.title = make_title(question)
    conversation.updated_at = _utcnow_naive()

    assistant_message_id = uuid4()
    if not hits:
        session.add(
            Message(
                id=assistant_message_id,
                conversation_id=conversation.id,
                role=MessageRole.ASSISTANT.value,
                content=NO_CONTEXT_REPLY,
                citations=[],
                model=None,
                finish_reason="no_context",
                created_at=datetime.now(UTC),
            )
        )
        await session.commit()
        await session.refresh(user_message)
        return PreparedExchange(
            conversation_id=conversation.id,
            user_message=user_message,
            assistant_message_id=assistant_message_id,
            plan=None,
            sources=[],
            no_context=True,
        )

    plan = build_prompt(question, hits, history)
    await session.commit()
    await session.refresh(user_message)
    return PreparedExchange(
        conversation_id=conversation.id,
        user_message=user_message,
        assistant_message_id=assistant_message_id,
        plan=plan,
        sources=plan.sources,
        no_context=False,
    )


async def persist_assistant(
    session_factory: async_sessionmaker[AsyncSession],
    assistant_message_id: UUID,
    conversation_id: UUID,
    *,
    content: str,
    sources: list[SearchHit],
    finish_reason: str,
    model: str | None,
) -> None:
    now = datetime.now(UTC)
    async with session_factory() as session:
        session.add(
            Message(
                id=assistant_message_id,
                conversation_id=conversation_id,
                role=MessageRole.ASSISTANT.value,
                content=content,
                citations=citations_from_hits(sources),
                model=model,
                finish_reason=finish_reason,
                created_at=now,
            )
        )
        conversation = await session.get(Conversation, conversation_id)
        if conversation is not None:
            conversation.updated_at = _utcnow_naive()
        await session.commit()


def citations_from_hits(hits: list[SearchHit]) -> list[dict]:
    return [
        Citation(
            n=number,
            document_id=hit.document_id,
            chunk_id=hit.chunk_id,
            filename=hit.filename,
            chunk_index=hit.chunk_index,
            char_start=hit.char_start,
            char_end=hit.char_end,
            excerpt=excerpt(hit.content),
            score=hit.score,
        ).model_dump(mode="json")
        for number, hit in enumerate(hits, start=1)
    ]


def excerpt(text: str) -> str:
    if len(text) <= CHAT_EXCERPT_CHARS:
        return text
    return f"{text[:CHAT_EXCERPT_CHARS]}…"


async def _load_history(session: AsyncSession, conversation_id: UUID) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(CHAT_HISTORY_MESSAGES)
    )
    messages = list((await session.execute(stmt)).scalars().all())
    messages.reverse()
    return messages
