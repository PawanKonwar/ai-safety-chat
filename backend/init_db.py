"""
Database initialization script
Creates tables and adds demo data
"""

from database import create_tables, init_db, SessionLocal, User, Conversation, Message
from datetime import datetime, timedelta, timezone
import secrets

def create_demo_data():
    """Create demo data for testing"""
    db = SessionLocal()
    
    try:
        # Create demo users
        demo_users = [
            User(username="demo_user", email="demo@example.com", role="user"),
            User(username="moderator", email="mod@example.com", role="moderator"),
        ]
        
        for user in demo_users:
            existing = db.query(User).filter(User.username == user.username).first()
            if not existing:
                db.add(user)
                print(f"✅ Created demo user: {user.username}")
        
        db.commit()
        
        # Create demo conversation and messages
        demo_user = db.query(User).filter(User.username == "demo_user").first()
        if demo_user:
            # Create a conversation
            conversation = Conversation(
                user_id=demo_user.id,
                session_id=f"demo_session_{secrets.token_hex(8)}",
                started_at=datetime.now(timezone.utc) - timedelta(hours=1)
            )
            db.add(conversation)
            db.commit()
            
            # Create some demo messages
            demo_messages = [
                {
                    "role": "user",
                    "content": "Hello! What is AI safety?",
                    "category": "safe",
                    "flagged": False
                },
                {
                    "role": "assistant",
                    "content": "AI safety involves implementing guardrails to ensure AI systems behave responsibly...",
                    "category": "safe",
                    "flagged": False
                },
                {
                    "role": "user",
                    "content": "I have a headache. What medicine should I take?",
                    "category": "medical",
                    "flagged": True
                },
                {
                    "role": "assistant",
                    "content": "I understand you mentioned medical-related topics. In a production AI system...",
                    "category": "medical",
                    "flagged": True,
                    "confidence": 0.85
                }
            ]
            
            for msg_data in demo_messages:
                message = Message(
                    conversation_id=conversation.id,
                    role=msg_data["role"],
                    content=msg_data["content"],
                    category=msg_data["category"],
                    flagged=msg_data.get("flagged", False),
                    confidence=msg_data.get("confidence"),
                    timestamp=datetime.now(timezone.utc) - timedelta(minutes=30)
                )
                db.add(message)
            
            db.commit()
            print("✅ Created demo conversation and messages")
        
    except Exception as e:
        print(f"❌ Error creating demo data: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    print("🚀 Initializing database...")
    init_db()
    print("\n📊 Creating demo data...")
    create_demo_data()
    print("\n✅ Database initialization complete!")
