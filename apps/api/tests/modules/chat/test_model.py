import uuid

from app.modules.chat.constants import DEFAULT_TITLE
from app.modules.chat.models import Conversation, Message, MessageRole
from app.modules.users.models import User
from app.modules.workspaces.models import Workspace

CITATION = {
    "n": 1,
    "document_id": str(uuid.uuid4()),
    "chunk_id": str(uuid.uuid4()),
    "filename": "notes.txt",
    "chunk_index": 0,
    "char_start": 0,
    "char_end": 11,
    "excerpt": "hello world",
    "score": 0.75,
}


async def _seed(session) -> tuple[User, Workspace, Conversation]:
    user = User(email=f"{uuid.uuid4()}@example.com", password_hash="not-used")
    session.add(user)
    await session.flush()

    workspace = Workspace(name="Acme", created_by=user.id)
    session.add(workspace)
    await session.flush()

    conversation = Conversation(workspace_id=workspace.id, created_by=user.id)
    session.add(conversation)
    await session.flush()
    return user, workspace, conversation


def _message(conversation: Conversation, **overrides) -> Message:
    values = {
        "conversation_id": conversation.id,
        "role": MessageRole.USER.value,
        "content": "hello",
        "citations": [],
    }
    values.update(overrides)
    return Message(**values)


async def test_conversation_title_defaults(session_factory):
    async with session_factory() as session:
        _, _, conversation = await _seed(session)
        await session.commit()
        conversation_id = conversation.id

    async with session_factory() as session:
        fetched = await session.get(Conversation, conversation_id)

    assert fetched.title == DEFAULT_TITLE


async def test_citations_round_trip_on_sqlite(session_factory):
    async with session_factory() as session:
        _, _, conversation = await _seed(session)
        message = _message(
            conversation,
            role=MessageRole.ASSISTANT.value,
            content="answer [1]",
            citations=[CITATION],
            model="openai/gpt-oss-120b",
            finish_reason="stop",
        )
        session.add(message)
        await session.commit()
        message_id = message.id

    async with session_factory() as session:
        fetched = await session.get(Message, message_id)

    assert fetched is not None
    assert fetched.citations == [CITATION]
    assert fetched.model == "openai/gpt-oss-120b"
    assert fetched.finish_reason == "stop"


async def test_deleting_conversation_cascades_messages(session_factory):
    async with session_factory() as session:
        _, _, conversation = await _seed(session)
        message = _message(conversation)
        session.add(message)
        await session.commit()
        conversation_id = conversation.id
        message_id = message.id

    async with session_factory() as session:
        conversation = await session.get(Conversation, conversation_id)
        await session.delete(conversation)
        await session.commit()

    async with session_factory() as session:
        assert await session.get(Message, message_id) is None


async def test_deleting_workspace_cascades_conversations_and_messages(session_factory):
    async with session_factory() as session:
        _, workspace, conversation = await _seed(session)
        message = _message(conversation)
        session.add(message)
        await session.commit()
        workspace_id = workspace.id
        conversation_id = conversation.id
        message_id = message.id

    async with session_factory() as session:
        workspace = await session.get(Workspace, workspace_id)
        await session.delete(workspace)
        await session.commit()

    async with session_factory() as session:
        assert await session.get(Conversation, conversation_id) is None
        assert await session.get(Message, message_id) is None
