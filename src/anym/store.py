import hashlib
import os
import secrets
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, select
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .classes import Message
from .config import generate_token

def _h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()

class Base(AsyncAttrs, DeclarativeBase):
    pass

class Chat(Base):
    __tablename__ = "chats"
    token: Mapped[str] = mapped_column(primary_key=True)  # sha256 of token
    secret: Mapped[str]  # sha256 of creator secret

class MessageRow(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("messages_token_ts", "token", "timestamp"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(ForeignKey("chats.token", ondelete="CASCADE"))
    name: Mapped[str]
    color: Mapped[str]
    message: Mapped[str]
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class ConversationStore:
    def __init__(self, url: str) -> None:
        self.engine = create_async_engine(url)
        self.session = async_sessionmaker(self.engine, expire_on_commit=False)

    async def open(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        await self.engine.dispose()

    async def create(self) -> tuple[str, str]:
        """Returns (token, secret). Only hashes are stored."""
        token, secret = generate_token(), generate_token()
        async with self.session.begin() as s:
            s.add(Chat(token=_h(token), secret=_h(secret)))
        return token, secret

    async def exists(self, token: str) -> bool:
        async with self.session() as s:
            return await s.get(Chat, _h(token)) is not None

    async def delete(self, token: str, secret: str) -> bool:
        async with self.session.begin() as s:
            chat = await s.get(Chat, _h(token))
            if not chat or not secrets.compare_digest(chat.secret, _h(secret)):
                return False
            await s.delete(chat)  # ponytail: messages removed by DB cascade
            return True

    async def history(self, token: str, before: datetime | None = None, limit: int = 50) -> list[Message]:
        """Newest `limit` messages older than `before`, returned oldest first."""
        q = select(MessageRow).where(MessageRow.token == _h(token))
        if before:
            q = q.where(MessageRow.timestamp < before)
        q = q.order_by(MessageRow.timestamp.desc()).limit(limit)
        async with self.session() as s:
            rows = (await s.scalars(q)).all()
        return [Message.model_validate(r, from_attributes=True) for r in reversed(rows)]

    async def add(self, token: str, msg: Message) -> None:
        async with self.session.begin() as s:
            s.add(MessageRow(**msg.model_dump(exclude={"token"}), token=_h(token)))

store = ConversationStore(os.environ.get("DATABASE_URL", "postgresql+psycopg://localhost/anym"))
