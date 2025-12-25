import sqlalchemy as sa
from sqlalchemy.orm import relationship
from .db import Base

class Bot(Base):
    __tablename__ = "bots"
    id = sa.Column(sa.BigInteger, primary_key=True)
    name = sa.Column(sa.String, unique=True, nullable=False)
    theme = sa.Column(sa.String, nullable=True)
    api_id = sa.Column(sa.Integer, nullable=False)
    api_hash = sa.Column(sa.String, nullable=False)
    session_name = sa.Column(sa.String, nullable=False)
    enabled = sa.Column(sa.Boolean, server_default=sa.text("true"))

    created_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now())
    updated_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now())

    channels = relationship("Channel", back_populates="bot")


class Channel(Base):
    __tablename__ = "channels"
    id = sa.Column(sa.BigInteger, primary_key=True)
    telegram_id = sa.Column(sa.String, unique=True, nullable=False)
    telegram_numeric_id = sa.Column(sa.BigInteger, nullable=True)
    display_name = sa.Column(sa.String, nullable=True)
    dialog_type = sa.Column(sa.String, nullable=True)
    language = sa.Column(sa.String, nullable=False)
    topics = sa.Column(sa.ARRAY(sa.String), nullable=False)
    enabled = sa.Column(sa.Boolean, server_default=sa.text("true"))

    bot_id = sa.Column(sa.BigInteger, sa.ForeignKey("bots.id"), nullable=False)
    bot = relationship("Bot", back_populates="channels")

    name_history = relationship(
        "ChannelNameHistory",
        back_populates="channel",
        cascade="all, delete-orphan",
    )

    messages = relationship(
        "Message", back_populates="channel", cascade="all, delete-orphan"
    )

    last_msg_id = sa.Column(sa.BigInteger, nullable=True)

        # NEW: how sensitive is this source? ("public" or "sensitive")
    sensitivity = sa.Column(sa.String, nullable=False, server_default="public")

    created_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now())
    updated_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now())


class ChannelNameHistory(Base):
    __tablename__ = "channel_name_history"

    id = sa.Column(sa.BigInteger, primary_key=True)
    channel_id = sa.Column(sa.BigInteger, sa.ForeignKey("channels.id"), nullable=False)
    old_name = sa.Column(sa.String, nullable=True)
    new_name = sa.Column(sa.String, nullable=True)
    changed_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now())

    channel = relationship("Channel", back_populates="name_history")

class Message(Base):
    __tablename__ = "messages"
    id = sa.Column(sa.BigInteger, primary_key=True)
    channel_id = sa.Column(sa.BigInteger, sa.ForeignKey("channels.id"), nullable=False)
    channel = relationship("Channel", back_populates="messages")

    telegram_msg_id = sa.Column(sa.BigInteger, nullable=False)
    sent_at = sa.Column(sa.DateTime(timezone=True), nullable=False)
    text = sa.Column(sa.Text, nullable=False)
    url = sa.Column(sa.String, nullable=True)
    raw_json = sa.Column(sa.JSON, nullable=True)

    ingested_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now())

    __table_args__ = (
        sa.UniqueConstraint("channel_id", "telegram_msg_id", name="uq_channel_message"),
    )


class Feed(Base):
    __tablename__ = "feeds"
    id = sa.Column(sa.BigInteger, primary_key=True)
    language = sa.Column(sa.String, nullable=False)
    topic = sa.Column(sa.String, nullable=False)
    slug = sa.Column(sa.String, unique=True, nullable=False)

    last_release_at = sa.Column(sa.DateTime(timezone=True), nullable=True)
    max_items = sa.Column(sa.Integer, nullable=True)

    created_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now())
    updated_at = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now())

    __table_args__ = (
        sa.UniqueConstraint("language", "topic", name="uq_language_topic"),
    )

    items = relationship("FeedItem", back_populates="feed", cascade="all, delete-orphan")


class FeedItem(Base):
    __tablename__ = "feed_items"
    id = sa.Column(sa.BigInteger, primary_key=True)
    feed_id = sa.Column(sa.BigInteger, sa.ForeignKey("feeds.id"), nullable=False)
    message_id = sa.Column(sa.BigInteger, sa.ForeignKey("messages.id"), nullable=False)

    feed = relationship("Feed", back_populates="items")
    message = relationship("Message", back_populates="feed_items")

    published_at = sa.Column(sa.DateTime(timezone=True), nullable=False)

    __table_args__ = (
        sa.UniqueConstraint("feed_id", "message_id", name="uq_feed_message"),
    )


# Back-populates for Message -> FeedItem declared after FeedItem definition to avoid
# referencing FeedItem before it is declared.
Message.feed_items = relationship(
    "FeedItem", back_populates="message", cascade="all, delete-orphan"
)

