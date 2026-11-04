import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.db.session import get_db
from app.modules.chat import schemas, service
from app.modules.chat.constants import CHAT_MAX_OUTPUT_TOKENS, NO_CONTEXT_REPLY
from app.modules.chat.deps import get_llm_provider
from app.modules.chat.llm import LLMDelta, LLMFinish, LLMProvider, LLMProviderError
from app.modules.chat.prompts import parse_cited
from app.modules.retrieval.deps import get_embedding_provider, get_session_factory
from app.modules.retrieval.embeddings import EmbeddingProvider, EmbeddingProviderError
from app.modules.workspaces.deps import require_workspace_member
from app.modules.workspaces.models import WorkspaceMember

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/workspaces/{workspace_id}/conversations",
    tags=["chat"],
)

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def _event(name: str, data: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(data)}\n\n"


@router.post("", response_model=schemas.ConversationSummary, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    workspace_id: UUID,
    body: schemas.ConversationCreate,
    member: Annotated[WorkspaceMember, Depends(require_workspace_member)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> schemas.ConversationSummary:
    conversation = await service.create_conversation(
        session, workspace_id, member.user_id, body.title
    )
    return schemas.ConversationSummary.model_validate(conversation)


@router.get("", response_model=list[schemas.ConversationSummary])
async def list_conversations(
    workspace_id: UUID,
    member: Annotated[WorkspaceMember, Depends(require_workspace_member)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[schemas.ConversationSummary]:
    conversations = await service.list_conversations(session, workspace_id, member.user_id)
    return [schemas.ConversationSummary.model_validate(item) for item in conversations]


@router.get("/{conversation_id}", response_model=schemas.ConversationDetail)
async def get_conversation(
    workspace_id: UUID,
    conversation_id: UUID,
    member: Annotated[WorkspaceMember, Depends(require_workspace_member)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> schemas.ConversationDetail:
    conversation = await service.get_conversation(
        session, workspace_id, conversation_id, member.user_id
    )
    messages = await service.list_messages(session, conversation.id)
    summary = schemas.ConversationSummary.model_validate(conversation)
    return schemas.ConversationDetail(
        **summary.model_dump(),
        messages=[schemas.MessageOut.model_validate(message) for message in messages],
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    workspace_id: UUID,
    conversation_id: UUID,
    member: Annotated[WorkspaceMember, Depends(require_workspace_member)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await service.delete_conversation(session, workspace_id, conversation_id, member.user_id)


@router.post("/{conversation_id}/messages")
async def send_message(
    workspace_id: UUID,
    conversation_id: UUID,
    body: schemas.MessageCreate,
    member: Annotated[WorkspaceMember, Depends(require_workspace_member)],
    session: Annotated[AsyncSession, Depends(get_db)],
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    embeddings: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
    llm: Annotated[LLMProvider, Depends(get_llm_provider)],
) -> StreamingResponse:
    conversation = await service.get_conversation(
        session, workspace_id, conversation_id, member.user_id
    )
    try:
        exchange = await service.prepare_exchange(
            session, workspace_id, conversation, body.content, embeddings
        )
    except EmbeddingProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Embedding provider unavailable",
        ) from exc

    source_payload = {
        "user_message_id": str(exchange.user_message.id),
        "assistant_message_id": str(exchange.assistant_message_id),
        "sources": service.citations_from_hits(exchange.sources),
        "no_context": exchange.no_context,
    }

    if exchange.no_context:

        async def no_context() -> AsyncIterator[str]:
            yield _event("sources", source_payload)
            yield _event("token", {"delta": NO_CONTEXT_REPLY})
            yield _event(
                "done",
                {
                    "assistant_message_id": str(exchange.assistant_message_id),
                    "finish_reason": "no_context",
                    "cited": [],
                },
            )

        return StreamingResponse(no_context(), media_type="text/event-stream", headers=SSE_HEADERS)

    assert exchange.plan is not None
    stream: AsyncIterator[object] | None = None
    try:
        stream = llm.stream(exchange.plan.messages, max_output_tokens=CHAT_MAX_OUTPUT_TOKENS)
        first = await anext(stream)
    except LLMProviderError as exc:
        if stream is not None:
            await _close_quietly(stream)
        rate_limited = exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        raise HTTPException(
            status_code=(
                status.HTTP_429_TOO_MANY_REQUESTS
                if rate_limited
                else status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail="Answer model is rate limited" if rate_limited else "Answer model unavailable",
        ) from exc
    except StopAsyncIteration as exc:
        if stream is not None:
            await _close_quietly(stream)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Answer model unavailable",
        ) from exc

    if not isinstance(first, LLMDelta):
        await stream.aclose()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Answer model unavailable",
        )

    async def answer() -> AsyncIterator[str]:
        chunks: list[str] = []
        finish_reason = "stop"
        try:
            yield _event("sources", source_payload)
            chunks.append(first.text)
            yield _event("token", {"delta": first.text})

            async for event in stream:
                if isinstance(event, LLMDelta):
                    chunks.append(event.text)
                    yield _event("token", {"delta": event.text})
                elif isinstance(event, LLMFinish):
                    finish_reason = event.finish_reason

            text = "".join(chunks)
            await service.persist_assistant(
                session_factory,
                exchange.assistant_message_id,
                exchange.conversation_id,
                content=text,
                sources=exchange.sources,
                finish_reason=finish_reason,
                model=settings.LLM_MODEL,
            )
            yield _event(
                "done",
                {
                    "assistant_message_id": str(exchange.assistant_message_id),
                    "finish_reason": finish_reason,
                    "cited": parse_cited(text, len(exchange.sources)),
                },
            )
        except LLMProviderError:
            text = "".join(chunks)
            if text:
                await service.persist_assistant(
                    session_factory,
                    exchange.assistant_message_id,
                    exchange.conversation_id,
                    content=text,
                    sources=exchange.sources,
                    finish_reason="error",
                    model=settings.LLM_MODEL,
                )
            yield _event("error", {"detail": "Answer model failed"})
        except asyncio.CancelledError:
            text = "".join(chunks)
            if text:
                try:
                    await asyncio.shield(
                        service.persist_assistant(
                            session_factory,
                            exchange.assistant_message_id,
                            exchange.conversation_id,
                            content=text,
                            sources=exchange.sources,
                            finish_reason="cancelled",
                            model=settings.LLM_MODEL,
                        )
                    )
                except Exception:  # best effort on disconnect
                    logger.warning("failed to save a cancelled answer", exc_info=True)
            raise
        finally:
            await stream.aclose()

    return StreamingResponse(answer(), media_type="text/event-stream", headers=SSE_HEADERS)


async def _close_quietly(stream: object | None) -> None:
    close = getattr(stream, "aclose", None)
    if close is not None:
        await close()
