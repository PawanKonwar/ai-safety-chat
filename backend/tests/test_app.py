"""Tests for the FastAPI application - health check, chat endpoint, and safety filter."""

import os

# Force mock OpenAI client for tests (avoid real API calls)
os.environ["OPENAI_API_KEY"] = ""

import pytest
from fastapi.testclient import TestClient

from app import app, check_safety_filter, SAFETY_KEYWORDS


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


# --- Health Check Tests ---


def test_root_endpoint(client):
    """Test that the root endpoint returns API info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "AI Safety Chat" in data["message"]
    assert "version" in data
    assert "openai_enabled" in data


def test_health_check(client):
    """Test the health check endpoint returns healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert "flagged_count" in data
    assert "total_messages" in data
    assert "low_confidence_responses" in data


# --- Chat Endpoint Tests ---


def test_chat_endpoint_success(client):
    """Test chat endpoint with a basic message."""
    response = client.post(
        "/chat",
        json={"message": "Hello, what is AI safety?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "category" in data
    assert "confidence_score" in data
    assert "flagged" in data
    assert "session_id" in data
    assert len(data["response"]) > 0


def test_chat_endpoint_empty_message(client):
    """Test chat endpoint rejects empty message."""
    response = client.post(
        "/chat",
        json={"message": ""},
    )
    assert response.status_code == 400


def test_chat_endpoint_whitespace_message(client):
    """Test chat endpoint rejects whitespace-only message."""
    response = client.post(
        "/chat",
        json={"message": "   "},
    )
    assert response.status_code == 400


def test_chat_endpoint_returns_safety_metadata(client):
    """Test chat response includes safety metadata (category, confidence, flagged)."""
    response = client.post(
        "/chat",
        json={"message": "What is 2+2?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["category"] in ["safe", "medical", "financial", "legal", "crisis"]
    assert isinstance(data["confidence_score"], (int, float))
    assert isinstance(data["flagged"], bool)


def test_chat_endpoint_medical_content_flagged(client):
    """Test chat flags medical content."""
    response = client.post(
        "/chat",
        json={"message": "I have a headache and feel sick. Should I take medicine?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "medical"
    assert data["flagged"] is True


def test_chat_endpoint_crisis_content_flagged(client):
    """Test chat flags crisis content and returns appropriate response."""
    response = client.post(
        "/chat",
        json={"message": "I want to die"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "crisis"
    assert data["flagged"] is True
    assert "988" in data["response"] or "crisis" in data["response"].lower()


# --- Safety Filter Tests ---


def test_safety_filter_safe_message():
    """Test safety filter returns None for safe messages."""
    category, confidence = check_safety_filter("What is the capital of France?")
    assert category is None
    assert confidence == 0.0


def test_safety_filter_medical_keywords():
    """Test safety filter detects medical keywords."""
    category, confidence = check_safety_filter("I have a headache")
    assert category == "medical"
    assert 0.0 < confidence <= 1.0


def test_safety_filter_financial_keywords():
    """Test safety filter detects financial keywords."""
    category, confidence = check_safety_filter("I want to invest in bitcoin")
    assert category == "financial"
    assert 0.0 < confidence <= 1.0


def test_safety_filter_legal_keywords():
    """Test safety filter detects legal keywords."""
    category, confidence = check_safety_filter("I need a lawyer for a contract")
    assert category == "legal"
    assert 0.0 < confidence <= 1.0


def test_safety_filter_crisis_keywords():
    """Test safety filter detects crisis keywords with low confidence."""
    category, confidence = check_safety_filter("I want to die")
    assert category == "crisis"
    assert 0.0 < confidence <= 0.30  # Crisis gets very low confidence


def test_safety_filter_crisis_multiple_keywords():
    """Test safety filter detects various crisis phrases."""
    crisis_phrases = ["suicide", "kill myself", "self harm", "end my life"]
    for phrase in crisis_phrases:
        category, confidence = check_safety_filter(f"Someone said {phrase}")
        assert category == "crisis", f"Failed for phrase: {phrase}"
        assert 0.0 < confidence <= 0.30


def test_safety_filter_case_insensitive():
    """Test safety filter is case insensitive."""
    category, _ = check_safety_filter("I HAVE A HEADACHE")
    assert category == "medical"


def test_safety_filter_keywords_defined():
    """Test that expected safety categories are defined."""
    assert "medical" in SAFETY_KEYWORDS
    assert "financial" in SAFETY_KEYWORDS
    assert "legal" in SAFETY_KEYWORDS
    assert "crisis" in SAFETY_KEYWORDS
    assert len(SAFETY_KEYWORDS["crisis"]) > 0
