"""
Database models and connection for AI Safety Chat
Uses SQLAlchemy ORM with SQLite
"""

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    JSON,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timezone
import os

# Database URL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ai_safety_chat.db")

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


# Database Models
class User(Base):
    """User model"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    password_hash = Column(String, nullable=True)  # For future auth
    role = Column(String, default="user")  # user, moderator, admin
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    conversations = relationship(
        "Conversation", back_populates="user", cascade="all, delete-orphan"
    )


class Conversation(Base):
    """Conversation model - represents a chat session"""

    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_id = Column(String, index=True, nullable=True)  # For anonymous sessions
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    learning_mode_enabled = Column(
        Boolean, default=False
    )  # Track learning mode preference
    user_settings = Column(
        JSON, nullable=True
    )  # Store user preferences (safety level, transparency, etc.)

    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    """Message model - stores all chat messages"""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String, nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    category = Column(String, nullable=True)  # medical, financial, legal, crisis, safe
    confidence = Column(Float, nullable=True)  # Safety filter confidence (0-1)
    confidence_score = Column(Float, nullable=True)  # AI response confidence (0-100)
    confidence_level = Column(String, nullable=True)  # "High", "Medium", "Low"
    flagged = Column(Boolean, default=False, index=True)
    pii_detected = Column(Boolean, default=False, index=True)  # PII detection flag
    pii_types = Column(JSON, nullable=True)  # List of detected PII types
    priority_level = Column(
        String, nullable=True, index=True
    )  # critical, high, medium, low
    escalation_reason = Column(Text, nullable=True)  # Why it was escalated
    target_response_time = Column(
        Integer, nullable=True
    )  # Target response time in minutes

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    moderator_decisions = relationship(
        "ModeratorDecision", back_populates="message", cascade="all, delete-orphan"
    )


class ModeratorDecision(Base):
    """Moderator decision model - stores moderator actions on flagged messages"""

    __tablename__ = "moderator_decisions"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)
    moderator_id = Column(
        Integer, ForeignKey("users.id"), nullable=True
    )  # Null for anonymous moderators
    action = Column(String, nullable=False)  # approve, reject, edit, clarify, escalate
    original_response = Column(Text, nullable=True)  # Store original AI response
    edited_response = Column(Text, nullable=True)  # If action is "edit" or "reject"
    rejection_reason = Column(String, nullable=True)  # Reason for rejection
    notes = Column(Text, nullable=True)  # Additional notes from moderator
    review_time_seconds = Column(Float, nullable=True)  # Time taken to review
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    message = relationship("Message", back_populates="moderator_decisions")
    moderator = relationship("User", foreign_keys=[moderator_id])


# Database utility functions
def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully")


def migrate_database():
    """Migrate existing database to add missing columns"""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)

    # Check if messages table exists
    if "messages" in inspector.get_table_names():
        # Get existing columns
        existing_columns = [col["name"] for col in inspector.get_columns("messages")]

        # Add missing columns if they don't exist
        with engine.connect() as conn:
            if "confidence_score" not in existing_columns:
                conn.execute(
                    text("ALTER TABLE messages ADD COLUMN confidence_score REAL")
                )
                conn.commit()
                print("✅ Added confidence_score column to messages table")

            if "confidence_level" not in existing_columns:
                conn.execute(
                    text("ALTER TABLE messages ADD COLUMN confidence_level VARCHAR")
                )
                conn.commit()
                print("✅ Added confidence_level column to messages table")

            # Note: confidence column should already exist, but check just in case
            if "confidence" not in existing_columns:
                conn.execute(text("ALTER TABLE messages ADD COLUMN confidence REAL"))
                conn.commit()
                print("✅ Added confidence column to messages table")

            if "pii_detected" not in existing_columns:
                conn.execute(
                    text(
                        "ALTER TABLE messages ADD COLUMN pii_detected BOOLEAN DEFAULT 0"
                    )
                )
                conn.commit()
                print("✅ Added pii_detected column to messages table")

            if "pii_types" not in existing_columns:
                # SQLite stores JSON as TEXT
                conn.execute(text("ALTER TABLE messages ADD COLUMN pii_types TEXT"))
                conn.commit()
                print("✅ Added pii_types column to messages table")

            # Check conversations table columns
            conv_columns = [
                row[1]
                for row in conn.execute(
                    text("PRAGMA table_info(conversations)")
                ).fetchall()
            ]
            existing_conv_columns = [col.lower() for col in conv_columns]

            if "learning_mode_enabled" not in existing_conv_columns:
                conn.execute(
                    text(
                        "ALTER TABLE conversations ADD COLUMN learning_mode_enabled BOOLEAN DEFAULT 0"
                    )
                )
                conn.commit()
                print("✅ Added learning_mode_enabled column to conversations table")

            if "user_settings" not in existing_conv_columns:
                conn.execute(
                    text("ALTER TABLE conversations ADD COLUMN user_settings TEXT")
                )
                conn.commit()
                print("✅ Added user_settings column to conversations table")

            # Check moderator_decisions table columns
            decision_columns = [
                row[1]
                for row in conn.execute(
                    text("PRAGMA table_info(moderator_decisions)")
                ).fetchall()
            ]
            existing_decision_columns = [col.lower() for col in decision_columns]

            if "original_response" not in existing_decision_columns:
                conn.execute(
                    text(
                        "ALTER TABLE moderator_decisions ADD COLUMN original_response TEXT"
                    )
                )
                conn.commit()
                print("✅ Added original_response column to moderator_decisions table")

            if "rejection_reason" not in existing_decision_columns:
                conn.execute(
                    text(
                        "ALTER TABLE moderator_decisions ADD COLUMN rejection_reason VARCHAR"
                    )
                )
                conn.commit()
                print("✅ Added rejection_reason column to moderator_decisions table")

            if "notes" not in existing_decision_columns:
                conn.execute(
                    text("ALTER TABLE moderator_decisions ADD COLUMN notes TEXT")
                )
                conn.commit()
                print("✅ Added notes column to moderator_decisions table")

            if "review_time_seconds" not in existing_decision_columns:
                conn.execute(
                    text(
                        "ALTER TABLE moderator_decisions ADD COLUMN review_time_seconds REAL"
                    )
                )
                conn.commit()
                print(
                    "✅ Added review_time_seconds column to moderator_decisions table"
                )

            # Check messages table columns for priority fields
            msg_columns = [
                row[1]
                for row in conn.execute(text("PRAGMA table_info(messages)")).fetchall()
            ]
            existing_msg_columns = [col.lower() for col in msg_columns]

            if "priority_level" not in existing_msg_columns:
                conn.execute(
                    text("ALTER TABLE messages ADD COLUMN priority_level VARCHAR")
                )
                conn.commit()
                print("✅ Added priority_level column to messages table")

            if "escalation_reason" not in existing_msg_columns:
                conn.execute(
                    text("ALTER TABLE messages ADD COLUMN escalation_reason TEXT")
                )
                conn.commit()
                print("✅ Added escalation_reason column to messages table")

            if "target_response_time" not in existing_msg_columns:
                conn.execute(
                    text("ALTER TABLE messages ADD COLUMN target_response_time INTEGER")
                )
                conn.commit()
                print("✅ Added target_response_time column to messages table")

            # Create index on priority_level for faster sorting
            try:
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS idx_messages_priority ON messages(priority_level)"
                    )
                )
                conn.commit()
                print("✅ Created index on priority_level")
            except Exception as e:
                print(f"⚠️ Index creation (may already exist): {e}")

    print("✅ Database migration completed")


def init_db():
    """Initialize database with tables and run migrations"""
    create_tables()
    migrate_database()  # Run migrations to add any missing columns

    # Create anonymous user if it doesn't exist
    db = SessionLocal()
    try:
        anonymous_user = db.query(User).filter(User.username == "anonymous").first()
        if not anonymous_user:
            anonymous_user = User(username="anonymous", email=None, role="user")
            db.add(anonymous_user)
            db.commit()
            print("✅ Anonymous user created")
    except Exception as e:
        print(f"⚠️  Error creating anonymous user: {e}")
        db.rollback()
    finally:
        db.close()
