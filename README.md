# AI Safety Chat - Educational System with Safety Guardrails

[![CI](https://github.com/PawanKonwar/ai-safety-chat/actions/workflows/ci.yml/badge.svg)](https://github.com/PawanKonwar/ai-safety-chat/actions/workflows/ci.yml)

<div align="center">

**Version 2.0.0** — A comprehensive conversational AI system demonstrating safety guardrails, human-in-the-loop oversight, and responsible AI practices.



[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-Educational-yellow.svg)](LICENSE)

</div>

---

## 📋 Table of Contents

- [Overview](#overview)
- [Why This Matters](#why-this-matters)
- [Enterprise Features (v2.0.0)](#enterprise-features-v200)
- [Features](#features)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Setup Instructions](#setup-instructions)
- [Database Schema](#database-schema)
- [API Documentation](#api-documentation)
- [Screenshots](#screenshots)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

---

## 🎯 Overview

**AI Safety Chat** is an educational demonstration system that showcases how AI applications can be built with comprehensive safety mechanisms. The system provides:

- **LLM-Based Intent Classification**: Semantic intent detection (with keyword fallbacks) for medical, financial, legal, and crisis content
- **Contextual PII Handling**: Sensitive values masked with placeholders (e.g. `{{NAME_1}}`) for the model while **fully redacted text** is stored in the database
- **Streaming Safety Pipeline**: Optional NDJSON streaming with a real-time output kill-switch on unsafe assistant text
- **Long-Term Risk Memory**: Cross-session analysis of prior flagged or medium-confidence interactions to detect escalating behavioral patterns
- **Confidence Scoring**: AI response confidence analysis (0-100%)
- **Priority-Based Escalation**: Automatic priority assignment (Critical, High, Medium, Low) with immediate escalation for crisis and contextual-risk cases
- **Human-in-the-Loop Oversight**: Moderator dashboard for reviewing flagged content
- **Multi-turn Context Analysis**: Conversation history tracking and risk escalation detection
- **User Control Panel**: Configurable safety levels, transparency, learning mode, and data preferences

### What It Does

The system acts as a conversational AI assistant with built-in safety guardrails. When users interact with the chat:

1. **Messages are classified** for intent (LLM when configured, keyword-based mock otherwise) and checked against safety rules
2. **PII is detected**: placeholders preserve semantics for the LLM; **persisted message content is redacted** (raw PII is not stored)
3. **Long-term risk patterns** may be evaluated **before** generation to raise priority and moderator context
4. **AI responses are generated** (OpenAI streaming or mock chunks) with optional **stream interception** for unsafe output
5. **Responses receive confidence scoring**; **flagged content is escalated** to human moderators by priority
6. **Moderators can review, edit, approve, or reject** responses through the dashboard

### Why This Matters

In production AI systems, safety guardrails are critical for:
- **Protecting users** from harmful or inaccurate information
- **Preventing misuse** of AI systems for illegal or dangerous purposes
- **Ensuring compliance** with regulations (medical advice, financial advice, etc.)
- **Building trust** through transparency and human oversight
- **Handling crisis situations** with immediate escalation and resources

This educational system demonstrates these principles in a practical, interactive format.

---

## 🏢 Enterprise Features (v2.0.0)

These capabilities represent a **defense-in-depth** safety stack suitable for educational and prototype “enterprise-style” deployments:

| Layer | What it does |
|--------|----------------|
| **LLM-Based Intent Classification** | Replaces pure keyword routing with **semantic intent** classification (JSON via OpenAI when enabled; **keyword-based fallback** when no API key). |
| **Contextual PII Masking** | Builds a **masked view** of the user message for the model using stable placeholders (e.g. `{{NAME_1}}`, `{{PHONE_1}}`) so the LLM keeps context; the **database stores only redacted** content. |
| **Streaming Kill-Switch** | With `stream: true`, assistant tokens are streamed as **NDJSON** (`delta` lines). A rolling buffer runs **lite output safety** checks; on violation the stream **stops**, emits a `safety_violation` event, and logs for moderators. |
| **Long-Term Risk Memory** | Queries prior **flagged** or **medium-confidence-related** user history, then uses an **LLM assessment** (or heuristic fallback) to detect **escalating risk** across time; can force **Critical** priority and **Contextual Risk** moderator notes **before** the model responds. |

---

## ✨ Features

### Core Safety Features

#### 1. **Safety Filtering & Intent**
- **Semantic Intent (primary)**: LLM classifies user intent into medical, financial, legal, crisis, or safe when OpenAI is configured
- **Keyword-Based Fallback**: Same categories via `check_safety_filter` when the LLM path is unavailable
- **Confidence Scoring**: Calculates AI response confidence (0-100%)
- **Auto-Flagging**: Flags content below configurable confidence thresholds

#### 2. **PII Detection, Masking & Redaction (FR-203)**
- **Detects**: Credit cards, SSN, phone numbers, email addresses, physical addresses, and related patterns
- **For the LLM**: **Contextual masking** — replaces spans with placeholders so meaning (e.g. “contact this person”) is preserved without exposing raw values
- **For storage**: **Full redaction** in persisted message content — raw PII is not written to the database; optional **placeholder mapping** is stored for authorized workflows
- **Logs**: Detection metadata (not raw PII) for audit
- **Warns**: User-facing notice when PII is detected

#### 3. **Automatic Escalation Triggers**
- **Critical Priority**: Crisis/suicide content → Immediate human review (0 min target)
- **High Priority**: Medical advice, illegal activity, high toxicity → < 5 min target
- **Medium Priority**: Financial advice, controversial topics, low confidence → < 15 min target
- **Low Priority**: Political/religious discussions → < 60 min target

#### 4. **Multi-turn Context Analysis (FR-102)**
- **Conversation History**: Tracks last 10 messages per conversation
- **Risk Escalation Detection**: Identifies escalating risk patterns (e.g., "headache" → "chest pain")
- **Filter Bypass Detection**: Detects attempts to bypass safety filters
- **Cumulative Risk Scoring**: Calculates risk based on conversation history

#### 5. **Confidence Scoring System**
- **Intelligent Analysis**: Analyzes queries for factual vs. subjective nature
- **Factor-Based Scoring**: Considers verifiability, time-based predictions, personal advice
- **Confidence Levels**: High (80-100%), Medium (50-79%), Low (0-49%)
- **Auto-Flagging**: Flags responses below configurable thresholds

### User Features

#### 6. **User Control Panel**
- **Safety Level**: Strict (70% threshold), Moderate (50%), Lenient (30%)
- **Transparency**: Toggle guardrail explanations
- **Learning Mode**: Educational analysis of AI responses
- **Data Preferences**: Opt-in/out of conversation logging
- **Response Speed**: Safety First, Balanced, Fast Responses

#### 7. **Educational/Learning Mode (FR-402)**
- **Risk Category Analysis**: Shows why content was flagged
- **Confidence Breakdown**: Explains confidence score factors
- **Triggered Guardrails**: Lists which safety layers were activated
- **Safety Tips**: Provides educational guidance
- **Context Analysis**: Shows conversation history analysis

### Moderator Features

#### 8. **Moderator Dashboard**
- **Priority-Based Queue**: Sorted by priority (Critical → High → Medium → Low)
- **Response Modification Workflow (FR-303)**:
  - **Edit & Approve**: Modify AI responses before approval
  - **Reject with Alternative**: Provide completely different response
  - **Request Clarification**: Send follow-up questions to users
  - **Escalate to Admin**: Mark for admin review
- **Edit History**: Stores original and modified responses
- **Statistics**: Total flagged, pending reviews, average review time
- **Real-time Updates**: Auto-refreshes every 5 seconds

#### 9. **Visual Indicators**
- **Priority Badges**: 🔴 Critical, 🟠 High, 🟡 Medium, 🟢 Low
- **Confidence Badges**: Color-coded confidence indicators
- **Category Badges**: Visual category labels
- **Crisis Animation**: Pulsing red badge for critical content

---

## 🏗️ Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (Browser)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  Chat UI      │  │  Moderator   │  │  Settings    │    │
│  │  (index.html) │  │  Dashboard   │  │  Panel       │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
│         │                  │                  │             │
│         └──────────────────┼──────────────────┘             │
│                            │                                 │
│         script.js (JSON or NDJSON stream reader)            │
└────────────────────────────┼─────────────────────────────────┘
                             │ HTTP/REST API (CORS)
┌────────────────────────────┼─────────────────────────────────┐
│                      Backend (FastAPI)                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         API (/chat, /moderator, …)                    │  │
│  └──────────────────────┬───────────────────────────────┘  │
│                         │                                   │
│  ┌──────────────────────┼───────────────────────────────┐  │
│  │ PII: redact (DB) + contextual mask (LLM input)      │  │
│  │ Intent Classifier (LLM JSON) │ keyword fallback      │  │
│  └──────────────────────┼───────────────────────────────┘  │
│  ┌──────────────────────┼───────────────────────────────┐  │
│  │ Risk Memory module │ prior flagged / med-conf. msgs │  │
│  │ Context Analysis   │ conversation history            │  │
│  └──────────────────────┼───────────────────────────────┘  │
│  ┌──────────────────────┼───────────────────────────────┐  │
│  │ OpenAI chat.completions (stream) │ MockOpenAI chunks   │  │
│  │ Streaming Interceptor: output buffer + kill-switch    │  │
│  └──────────────────────┼───────────────────────────────┘  │
│  ┌──────────────────────┼───────────────────────────────┐  │
│  │ Priority │ Confidence scoring │ finalize turn         │  │
│  └──────────────────────┼───────────────────────────────┘  │
│  ┌──────────────────────┼───────────────────────────────┐  │
│  │              SQLAlchemy ORM → SQLite                  │  │
│  └──────────────────────┼───────────────────────────────┘  │
└──────────────────────────┼───────────────────────────────────┘
                           │
┌──────────────────────────┼───────────────────────────────────┐
│                    SQLite Database                           │
│  users │ conversations │ messages │ moderator_decisions      │
└──────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **User sends message** → Frontend (`script.js`)
2. **Frontend sends POST /chat** (JSON body; optional `stream: true` for NDJSON) → Backend (`app.py`)
3. **Backend processes (order matters)**:
   - **PII**: detect → **redact** for persistence → **mask** for LLM
   - **Intent classification** (LLM or keyword mock)
   - **Context analysis** (in-session history)
   - **Long-term Risk Memory** (cross-session DB lookup + escalation assessment) — runs **before** generation
   - **AI generation**: OpenAI **`stream=True`** or mock chunked text
   - **Streaming Interceptor**: rolling buffer + lite safety on assistant text; may emit `safety_violation` and stop
   - **Confidence scoring** and **priority** (including contextual-risk overrides)
4. **Backend stores** → SQLite (redacted user content, assistant reply, flags, priority)
5. **Backend returns** → Single JSON **`ChatResponse`**, or **NDJSON** stream (`delta` / `safety_violation` / final `done` with full metadata)
6. **Frontend displays** → Chat UI with badges, warnings, and streamed text when enabled

### Technology Stack

- **Frontend**: HTML5, CSS3, JavaScript (ES6+), Font Awesome, `ReadableStream` NDJSON client for streaming chat
- **Backend**: Python 3.8+, FastAPI, Uvicorn
- **Database**: SQLite with SQLAlchemy ORM
- **AI**: OpenAI GPT-3.5-turbo (`chat.completions` streaming, intent JSON, risk assessment) or `MockOpenAI` fallback
- **Authentication**: JWT tokens with Passlib/Bcrypt
- **Security**: CORS middleware, PII masking + redaction, stream output safety phrases, input validation

---

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- Modern web browser (Chrome, Firefox, Safari, Edge)
- (Optional) OpenAI API key for real AI responses

### 1. Clone/Download the Project

```bash
cd ai-safety-chat
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# macOS/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialize database
python init_db.py

# (Optional) Set up OpenAI API key
cp .env.example .env
# Edit .env and add: OPENAI_API_KEY=sk-your-key-here

# Start server
python app.py
# Or: uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend Setup

**Option A: Direct File Access**
```bash
# Simply open in browser
open frontend/index.html  # macOS
# or double-click index.html
```

**Option B: Local Web Server (Recommended)**
```bash
cd frontend
python -m http.server 8080
# Then visit: http://localhost:8080
```

### 4. Access the Application

- **Chat Interface**: `http://localhost:8080/index.html` (or open `frontend/index.html`)
- **Moderator Dashboard**: `http://localhost:8080/moderator.html` (or open `frontend/moderator.html`)
- **API Health Check**: `http://localhost:8000/health`

---

## 📖 Setup Instructions

### Detailed Backend Setup

#### Step 1: Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
```

**Dependencies:**
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `sqlalchemy` - ORM for database
- `pydantic` - Data validation
- `python-dotenv` - Environment variables
- `passlib[bcrypt]` - Password hashing
- `python-jose[cryptography]` - JWT tokens
- `openai` - OpenAI API client (optional)

#### Step 2: Database Initialization

```bash
python init_db.py
```

This creates:
- SQLite database (`ai_safety_chat.db`)
- All required tables (users, conversations, messages, moderator_decisions)
- Anonymous user account
- Applies database migrations automatically

#### Step 3: Environment Configuration

Create `.env` file (optional):
```bash
cp .env.example .env
```

Edit `.env`:
```env
OPENAI_API_KEY=sk-your-api-key-here
SECRET_KEY=your-secret-key-for-jwt
```

**Note**: If `OPENAI_API_KEY` is not set, the system uses mock AI responses.

#### Step 4: Start the Server

```bash
# Development mode (with auto-reload)
uvicorn app:app --reload --host 0.0.0.0 --port 8000

# Or using Python directly
python app.py
```

Server runs on: `http://localhost:8000`

### Frontend Configuration

The frontend is pre-configured to connect to `http://localhost:8000`. To change this:

1. Edit `frontend/script.js`:
   ```javascript
   const API_BASE_URL = 'http://localhost:8000';  // Change this
   ```

2. Edit `frontend/moderator.js`:
   ```javascript
   const API_BASE_URL = 'http://localhost:8000';  // Change this
   ```

---

## 🗄️ Database Schema

### Tables

#### `users`
- `id` (Integer, Primary Key)
- `username` (String, Unique)
- `email` (String, Optional)
- `hashed_password` (String, Optional)
- `role` (String: "user", "moderator", "admin")
- `created_at` (DateTime)

#### `conversations`
- `id` (Integer, Primary Key)
- `user_id` (Integer, Foreign Key → users.id)
- `session_id` (String, Indexed) - For anonymous sessions
- `started_at` (DateTime)
- `learning_mode_enabled` (Boolean)
- `user_settings` (JSON) - User preferences

#### `messages`
- `id` (Integer, Primary Key)
- `conversation_id` (Integer, Foreign Key → conversations.id)
- `role` (String: "user" or "assistant")
- `content` (Text) - Redacted if PII detected
- `timestamp` (DateTime, Indexed)
- `category` (String: "medical", "financial", "legal", "crisis", "safe")
- `confidence` (Float) - Safety filter confidence (0-1)
- `confidence_score` (Float) - AI response confidence (0-100)
- `confidence_level` (String: "High", "Medium", "Low")
- `flagged` (Boolean, Indexed)
- `pii_detected` (Boolean, Indexed)
- `pii_types` (JSON) - List of detected PII types
- `pii_placeholder_mapping` (JSON, Optional) - Maps placeholders (e.g. `{{NAME_1}}`) to spans for authorized display workflows; persisted user `content` remains redacted
- `priority_level` (String: "critical", "high", "medium", "low", Indexed)
- `escalation_reason` (Text) - Why it was escalated
- `target_response_time` (Integer) - Target response time in minutes

#### `moderator_decisions`
- `id` (Integer, Primary Key)
- `message_id` (Integer, Foreign Key → messages.id)
- `moderator_id` (Integer, Foreign Key → users.id, Optional)
- `action` (String: "approve", "reject", "edit", "clarify", "escalate")
- `original_response` (Text) - Original AI response
- `edited_response` (Text) - Modified response (if action is "edit" or "reject")
- `rejection_reason` (String) - Reason for rejection
- `notes` (Text) - Moderator notes
- `review_time_seconds` (Float) - Time taken to review
- `timestamp` (DateTime)

### Relationships

```
users (1) ──< (many) conversations
conversations (1) ──< (many) messages
messages (1) ──< (many) moderator_decisions
users (1) ──< (many) moderator_decisions (as moderator)
```

---

## 📡 API Documentation

### POST /chat

Send a chat message and receive an AI response with safety metadata.

**Request:**
```json
{
  "message": "I have a headache",
  "learning_mode": false,
  "session_id": "optional-session-id",
  "stream": false,
  "settings": {
    "safety_level": "moderate",
    "transparency": true,
    "learning_mode": false,
    "data_logging": false,
    "response_speed": "balanced"
  }
}
```

- **`stream`**: If `true`, the response is **`application/x-ndjson`**: newline-delimited JSON events (`{"type":"delta","text":"..."}`, optional `{"type":"safety_violation",...}`, then `{"type":"done",...}` with the same fields as the JSON response below). If `false` or omitted, the response is a single JSON object (default for simple clients and tests).

**Response (when `stream` is false):**
```json
{
  "response": "AI response text...",
  "category": "medical",
  "confidence": 0.85,
  "confidence_score": 75.0,
  "confidence_level": "Medium",
  "confidence_reasons": ["Topic involves medical content requiring professional expertise"],
  "flagged": true,
  "message_for_moderator": "Flagged for: medical content. Message: I have a headache",
  "session_id": "session-id",
  "pii_warning": null,
  "learning_analysis": {
    "risk_category": "Medical",
    "triggered_guardrails": ["medical_advice_detection"],
    "confidence_breakdown": [
      {"factor": "Topic risk", "impact": "-40%"}
    ],
    "safety_tips": ["AI cannot diagnose medical conditions"],
    "human_review_reason": "Medical queries require professional oversight",
    "context_analysis": {
      "risk_escalation": false,
      "filter_bypass_attempt": false,
      "cumulative_risk_score": 0.0,
      "previous_queries": []
    }
  },
  "guardrail_explanation": "Guardrail triggered: Medical content detected..."
}
```

### GET /moderator/queue

Get all flagged messages awaiting review, sorted by priority.

**Response:**
```json
[
  {
    "id": 123,
    "timestamp": "2026-01-24T10:30:00",
    "user_message": "I want to die",
    "ai_response": "Crisis response with resources...",
    "category": "crisis",
    "confidence": 0.20,
    "confidence_score": 15.0,
    "confidence_level": "Low",
    "priority_level": "critical",
    "escalation_reason": "Mental health crisis detected",
    "target_response_time": 0
  }
]
```

### POST /moderator/queue/{message_id}/action

Take moderator action on a flagged message.

**Request:**
```json
{
  "action": "edit",
  "edited_response": "Modified response text",
  "alternative_response": null,
  "rejection_reason": null,
  "notes": "Added clarification",
  "review_time_seconds": 45.5
}
```

**Actions**: `approve`, `edit`, `reject`, `clarify`, `escalate`

### GET /conversation/{session_id}

Get conversation history for a session.

**Response:**
```json
[
  {
    "role": "user",
    "content": "I have a headache",
    "category": "medical",
    "confidence": 0.85,
    "timestamp": "2026-01-24T10:30:00"
  },
  {
    "role": "assistant",
    "content": "AI response...",
    "category": "medical",
    "confidence": 0.85,
    "timestamp": "2026-01-24T10:30:05"
  }
]
```

### POST /auth/register

Register a new user (optional for demo).

### POST /auth/login

Login and get JWT access token.

### GET /health

Health check endpoint.

---

## 📸 Screenshots

### Chat Interface

**Main Features:**
- Dark-themed modern UI
- Real-time safety badges (confidence, category)
- Learning Mode with detailed analysis
- User Control Panel (Settings)
- PII warning bar
- Guardrail explanations

**Key Elements:**
- Confidence badges: 🟢 High, 🟡 Medium, 🔴 Low
- Category badges: Medical, Financial, Legal, Crisis
- Learning Mode analysis with collapsible sections
- Settings modal with 5 configurable options

### Moderator Dashboard

**Main Features:**
- Priority-based queue (Critical → High → Medium → Low)
- Priority badges with color coding
- Response modification workflow
- Edit/Reject/Clarify/Escalate actions
- Statistics panel
- Real-time auto-refresh

**Key Elements:**
- 🔴 Critical priority (pulsing animation)
- 🟠 High priority
- 🟡 Medium priority
- 🟢 Low priority
- Edit modal with original/edited preview
- Reject modal with alternative response

### Database Schema

See [Database Schema](#database-schema) section above for detailed table structures.

---

## 🛠️ Development

### Running in Development Mode

```bash
# Backend with auto-reload
cd backend
uvicorn app:app --reload --host 0.0.0.0 --port 8000

# Frontend (if using web server)
cd frontend
python -m http.server 8080
```

### Testing the API

```bash
# Test chat endpoint
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I have a headache",
    "learning_mode": false
  }'

# Get moderator queue
curl http://localhost:8000/moderator/queue

# Health check
curl http://localhost:8000/health
```

### Code Structure

```
ai-safety-chat/
├── frontend/
│   ├── index.html          # Main chat interface
│   ├── moderator.html      # Moderator dashboard
│   ├── style.css           # Chat styling
│   ├── moderator.css       # Dashboard styling
│   ├── script.js           # Chat functionality & API calls
│   └── moderator.js        # Dashboard functionality
├── backend/
│   ├── app.py              # FastAPI server & main logic
│   ├── database.py         # SQLAlchemy models & migrations
│   ├── auth.py             # Authentication utilities
│   ├── init_db.py          # Database initialization
│   ├── requirements.txt    # Python dependencies
│   └── .env.example        # Environment variables template
├── README.md               # This file
└── UserGuide.md            # User guide (see separate file)
```

---

## 🔧 Troubleshooting

### Backend Won't Start

**Issue**: Port 8000 already in use
```bash
# Find process using port 8000
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Kill the process or use a different port
uvicorn app:app --reload --port 8001
```

**Issue**: Missing dependencies
```bash
pip install -r requirements.txt
```

**Issue**: Database errors
```bash
# Delete and recreate database
rm backend/ai_safety_chat.db
python backend/init_db.py
```

### Frontend Can't Connect to Backend

**Issue**: CORS errors
- Ensure backend CORS middleware is configured (already set up)
- If using `file://` protocol, serve frontend from a web server instead
- Check browser console for specific CORS error messages

**Issue**: Connection refused
- Verify backend is running: `curl http://localhost:8000/health`
- Check `API_BASE_URL` in `frontend/script.js` and `frontend/moderator.js`

### Database Migration Issues

**Issue**: Column doesn't exist errors
- Run database migration: `python backend/init_db.py`
- The migration function automatically adds missing columns

### OpenAI API Errors

**Issue**: API key invalid
- Verify API key in `.env` file
- Check OpenAI account has available credits
- System automatically falls back to mock responses

### Crisis Detection Not Working

**Issue**: Crisis content not being detected
- Check backend logs for `🚨 CRISIS DETECTED` messages
- Verify crisis keywords are in `SAFETY_KEYWORDS["crisis"]` in `backend/app.py`
- Ensure backend server was restarted after code changes

---

## 📚 Additional Resources

- **User Guide**: See [UserGuide.md](UserGuide.md) for v2.0.0 usage (streaming chat, PII masking, moderator queue)
- **API Documentation**: Interactive docs at `http://localhost:8000/docs` (Swagger UI); `GET /` reports `"version": "2.0.0"`
- **FastAPI Documentation**: https://fastapi.tiangolo.com/
- **SQLAlchemy Documentation**: https://docs.sqlalchemy.org/

---

## 🎓 Educational Purpose

This is an **educational demonstration system**. Real AI safety systems require:

- Comprehensive oversight mechanisms
- Continuous monitoring and auditing
- Robust safety guardrails
- Professional human review processes
- Compliance with relevant regulations (HIPAA, GDPR, etc.)
- Regular security audits
- Incident response procedures

---

## 📝 License

This is an educational project for demonstration purposes.

---

## 🙏 Acknowledgments

Built to demonstrate AI safety principles, human-in-the-loop oversight, and responsible AI development practices.
