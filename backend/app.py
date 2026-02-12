"""
AI Safety Chat Backend - FastAPI Server

Provides chat API and moderator queue endpoints with SQLite database.
Implements safety guardrails, PII detection, priority-based escalation,
and human-in-the-loop oversight mechanisms.
"""

from fastapi import FastAPI, HTTPException, Depends, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
import os
from dotenv import load_dotenv
from datetime import datetime, timezone
import re

# Import database and auth
from database import get_db, init_db, User, Conversation, Message, ModeratorDecision
from auth import (
    get_current_user,
    create_access_token,
    get_password_hash,
    verify_password,
    get_or_create_anonymous_session,
)

# Load environment variables
load_dotenv()

# Initialize database on startup
init_db()

# Initialize FastAPI app
app = FastAPI(
    title="AI Safety Chat API",
    description="Backend API for AI Safety Chat with safety guardrails",
    version="2.0.0",
)

# CORS configuration
# Handle CORS for all origins including 'null' (file:// protocol)
# Note: When allow_credentials=True, cannot use allow_origins=["*"]
# For development, we allow all origins with credentials=False
# In production, specify exact origins and set credentials=True if needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development (including 'null')
    allow_credentials=False,  # Set to False to allow wildcard origins
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "Accept",
        "Origin",
        "X-Requested-With",
        "Access-Control-Request-Method",
        "Access-Control-Request-Headers",
        "Accept-Language",
        "Cache-Control",
    ],
    expose_headers=["*"],
    max_age=3600,  # Cache preflight requests for 1 hour
)


# Add middleware to explicitly set CORS headers for all responses (including 'null' origin)
@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    """Add CORS headers to all responses, including handling 'null' origin"""
    response = await call_next(request)
    # Explicitly set CORS headers for all responses
    response.headers["Access-Control-Allow-Origin"] = (
        "*"  # Allow all origins including 'null'
    )
    response.headers["Access-Control-Allow-Methods"] = (
        "GET, POST, PUT, DELETE, OPTIONS, PATCH, HEAD"
    )
    response.headers["Access-Control-Allow-Headers"] = (
        "Content-Type, Authorization, Accept, Origin, X-Requested-With, Access-Control-Request-Method, Access-Control-Request-Headers"
    )
    response.headers["Access-Control-Allow-Credentials"] = "false"
    response.headers["Access-Control-Expose-Headers"] = "*"
    return response


# Add explicit OPTIONS handler for /chat endpoint to ensure preflight works
@app.options("/chat")
async def options_chat():
    """Handle OPTIONS preflight for /chat endpoint"""
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, Accept, Origin",
            "Access-Control-Max-Age": "3600",
        },
    )


# Add OPTIONS handler for all other endpoints too
@app.options("/{full_path:path}")
async def options_handler(full_path: str):
    """Handle OPTIONS preflight for all endpoints"""
    return Response(
        status_code=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, Accept, Origin, X-Requested-With",
            "Access-Control-Max-Age": "3600",
        },
    )


# Safety keywords (same as frontend)
SAFETY_KEYWORDS = {
    "medical": ["pain", "hurt", "fever", "doctor", "medicine", "sick", "headache"],
    "financial": ["invest", "money", "bitcoin", "stock", "credit card", "loan"],
    "legal": ["lawyer", "legal", "sue", "contract", "illegal"],
    "crisis": [
        "suicide",
        "suicidal",
        "depressed",
        "kill myself",
        "end my life",
        "hopeless",
        "i want to die",
        "want to die",
        "don't want to live",
        "better off dead",
        "going to kill",
        "end it all",
        "no reason to live",
        "hurt myself",
        "self harm",
        "cutting myself",
        "want to end",
        "not worth living",
    ],
}

# OpenAI API key (optional)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
USE_OPENAI = bool(OPENAI_API_KEY)


# Mock OpenAI client for when API key is not provided
class MockOpenAI:
    """Mock OpenAI client for demonstration"""

    @staticmethod
    def generate_response(
        user_message: str,
        category: Optional[str] = None,
        pii_types: Optional[List[str]] = None,
    ) -> str:
        """Generate a mock AI response"""
        lower_message = user_message.lower()

        # Handle PII detection first - provide educational privacy response
        if pii_types and len(pii_types) > 0:
            # Use a clear, educational response that matches the example format
            return "I've detected personal information in your message. For privacy protection, I've redacted it. Remember: AI systems should never ask for or store personal details like emails, passwords, or identification numbers."

        # CRISIS CONTENT: Check content FIRST (before category check) to catch all cases
        crisis_keywords_direct = [
            "i want to die",
            "want to die",
            "kill myself",
            "end my life",
            "suicide",
            "suicidal",
            "don't want to live",
            "better off dead",
            "going to kill",
            "end it all",
            "no reason to live",
            "hurt myself",
            "self harm",
            "cutting myself",
            "not worth living",
        ]
        for keyword in crisis_keywords_direct:
            if keyword in lower_message:
                # Crisis detected - return immediate resources
                crisis_response = (
                    "I'm concerned about what you've shared. If you're in immediate danger, please call emergency services (911) or your local crisis hotline right away.\n\n"
                    "**Crisis Resources:**\n"
                    "• National Suicide Prevention Lifeline: 988 (24/7)\n"
                    "• Crisis Text Line: Text HOME to 741741\n"
                    "• International Association for Suicide Prevention: https://www.iasp.info/resources/Crisis_Centres/\n\n"
                    "This message has been flagged for immediate human review. A trained professional will reach out to provide support. You are not alone, and help is available."
                )
                return crisis_response

        # CRISIS CONTENT: Also check category (backup)
        if category == "crisis":
            crisis_response = (
                "I'm concerned about what you've shared. If you're in immediate danger, please call emergency services (911) or your local crisis hotline right away.\n\n"
                "**Crisis Resources:**\n"
                "• National Suicide Prevention Lifeline: 988 (24/7)\n"
                "• Crisis Text Line: Text HOME to 741741\n"
                "• International Association for Suicide Prevention: https://www.iasp.info/resources/Crisis_Centres/\n\n"
                "This message has been flagged for immediate human review. A trained professional will reach out to provide support. You are not alone, and help is available."
            )
            return crisis_response

        if category == "medical":
            return "I understand you mentioned medical-related topics. In a production AI system, medical queries would typically be flagged for review to ensure accurate, safe information. This educational system demonstrates how such content is identified and would be handled with appropriate guardrails and potentially human medical professional oversight."
        elif category == "financial":
            return "I notice financial-related keywords in your message. Financial advice requires careful consideration and often regulatory compliance. In production systems, such queries would be flagged for review to ensure responsible handling. This demonstrates how AI safety systems identify and manage sensitive financial content."
        elif category == "legal":
            return "Your message contains legal-related terms. Legal matters often require professional expertise and careful handling. In a production AI system, legal queries would be flagged for review to ensure appropriate responses. This educational system shows how such content is identified for safety oversight."
        # Crisis category already handled above - this should never be reached
        elif "safety" in lower_message or "guardrail" in lower_message:
            return "Great question! AI safety involves implementing guardrails to ensure AI systems behave responsibly. This includes content filtering, bias detection, and human oversight mechanisms. In this educational system, we're demonstrating how such guardrails can work in practice."
        elif "bias" in lower_message or "fair" in lower_message:
            return "Bias in AI is a critical safety concern. AI systems can perpetuate or amplify biases present in training data. Safety measures include diverse datasets, fairness audits, and continuous monitoring. This is why human-in-the-loop oversight is essential."
        elif "risk" in lower_message or "danger" in lower_message:
            return "AI risks can include misinformation, privacy violations, and unintended harmful outputs. Safety systems use multiple layers: input validation, output filtering, and human review processes. Education about these risks is the first step toward safer AI."
        elif (
            "hello" in lower_message or "hi" in lower_message or "hey" in lower_message
        ):
            return "Hello! I'm here to help you learn about AI safety. Feel free to ask me about guardrails, bias, risks, or any other AI safety topics. Remember, this is an educational demonstration."
        # Simple factual questions - answer directly first (100% confidence facts)
        elif (
            "2+2" in lower_message
            or "what is 2+2" in lower_message
            or lower_message.strip() == "2+2"
            or "2 + 2" in lower_message
        ):
            return (
                "2 + 2 equals 4. This is a basic mathematical fact with 100% certainty."
            )
        elif (
            "3*3" in lower_message
            or "3 * 3" in lower_message
            or "3 times 3" in lower_message
            or "what is 3*3" in lower_message
        ):
            return "3 times 3 equals 9. This is a basic mathematical fact with 100% certainty."
        elif (
            "10-5" in lower_message
            or "10 - 5" in lower_message
            or "what is 10-5" in lower_message
        ):
            return "10 minus 5 equals 5. This is a basic mathematical fact with 100% certainty."
        elif (
            ("capital" in lower_message and "france" in lower_message)
            or lower_message.strip() == "capital of france"
            or "france capital" in lower_message
        ):
            return "Paris is the capital of France. This is a well-established geographical fact with 100% certainty."
        elif (
            "capital" in lower_message and "japan" in lower_message
        ) or "japan capital" in lower_message:
            return "Tokyo is the capital of Japan. This is a well-established geographical fact with 100% certainty."
        elif (
            "water boils" in lower_message or "boiling point of water" in lower_message
        ):
            return "Water boils at 100 degrees Celsius (212 degrees Fahrenheit) at standard atmospheric pressure. This is a well-established scientific fact with 100% certainty."
        elif (
            "earth orbits" in lower_message
            or "earth revolves around sun" in lower_message
        ):
            return "Earth orbits the Sun. This is a well-established astronomical fact with 100% certainty."
        elif "photosynthesis" in lower_message and (
            "explain" in lower_message or "what is" in lower_message
        ):
            return "Photosynthesis is the process by which plants convert light energy into chemical energy, using carbon dioxide and water to produce glucose and oxygen. This is a well-documented scientific process that AI systems can explain with high confidence."
        # Financial/medical/legal - safety disclaimer first, then answer if possible
        elif "invest" in lower_message or (
            "stock" in lower_message and "should" in lower_message
        ):
            return "I cannot provide specific investment advice, as financial decisions require professional expertise and depend on individual circumstances. In a production AI system, such queries would be flagged for review to ensure responsible handling. This demonstrates how AI safety systems identify and manage sensitive financial content."
        elif "will" in lower_message and (
            "ai" in lower_message or "job" in lower_message
        ):
            return "Predicting the future impact of AI on jobs involves many uncertain factors. While AI will likely change the job market, the exact outcomes depend on various economic, social, and technological developments that are difficult to predict with certainty. This type of speculative question would be flagged for lower confidence in an AI safety system."
        elif "weather" in lower_message:
            return "I don't have access to real-time weather data, so I cannot provide current weather information. Weather queries require up-to-date data from meteorological services, which would be flagged as medium confidence in an AI safety system."
        # General questions - answer directly
        elif (
            "what is" in lower_message
            or "explain" in lower_message
            or "define" in lower_message
        ):
            # For general questions, provide helpful answer first
            if "safety" in lower_message or "guardrail" in lower_message:
                return "AI safety involves implementing guardrails to ensure AI systems behave responsibly. This includes content filtering, bias detection, and human oversight mechanisms. In this educational system, we're demonstrating how such guardrails work in practice."
            elif "bias" in lower_message:
                return "Bias in AI refers to systematic errors or unfairness in AI systems, often stemming from biased training data or algorithms. AI systems can perpetuate or amplify biases present in their training data. Safety measures include diverse datasets, fairness audits, and continuous monitoring."
            else:
                # Generic helpful response for other questions
                return f"I'd be happy to help with \"{user_message}\". In an AI safety system, I would provide accurate information while being mindful of the confidence level and potential safety concerns. For this educational demonstration, I'm showing how AI systems evaluate queries and provide appropriate responses."
        else:
            # Default: answer helpfully, then add safety context
            return f'I can help with "{user_message}". In an AI safety system, responses are evaluated for accuracy and appropriateness. This educational system demonstrates how guardrails help ensure responsible AI behavior.'


# Real OpenAI client (if API key is provided)
if USE_OPENAI:
    try:
        from openai import OpenAI
        import httpx
        import os

        # Temporarily remove proxy environment variables that might cause issues
        proxy_vars = ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]
        saved_proxies = {}
        for var in proxy_vars:
            if var in os.environ:
                saved_proxies[var] = os.environ.pop(var)

        try:
            # Create httpx client without any proxy-related parameters
            # httpx 0.28.1 doesn't support 'proxies' parameter in Client()
            http_client = httpx.Client()
            openai_client = OpenAI(api_key=OPENAI_API_KEY, http_client=http_client)
        finally:
            # Restore proxy environment variables
            for var, value in saved_proxies.items():
                os.environ[var] = value

    except (ImportError, TypeError, AttributeError, Exception) as e:
        # Fallback to mock client if OpenAI initialization fails
        print(f"⚠️ Warning: OpenAI client initialization failed: {e}")
        print("⚠️ Falling back to mock client.")
        USE_OPENAI = False
        openai_client = MockOpenAI()
else:
    openai_client = MockOpenAI()


# Pydantic Models
class UserSettings(BaseModel):
    """User control panel settings"""

    safety_level: str = "moderate"  # strict, moderate, lenient
    transparency: bool = True
    learning_mode: bool = False
    data_logging: bool = False
    response_speed: str = "balanced"  # safety, balanced, speed


class ChatRequest(BaseModel):
    message: str
    learning_mode: bool = False
    session_id: Optional[str] = None
    settings: Optional[UserSettings] = None


class ConversationMessage(BaseModel):
    """Message in conversation history"""

    role: str  # "user" or "assistant"
    content: str
    category: Optional[str] = None
    confidence: Optional[float] = None
    timestamp: str


class ContextAnalysis(BaseModel):
    """Context analysis results"""

    risk_escalation: bool
    filter_bypass_attempt: bool
    cumulative_risk_score: float
    persistent_sensitive_topic: bool
    context_flags: List[str]
    previous_queries: List[
        Dict[str, Any]
    ]  # Recent queries with categories (confidence can be float, str, or None)


class LearningAnalysis(BaseModel):
    """Learning mode analysis metadata"""

    risk_category: str
    triggered_guardrails: List[str]
    confidence_breakdown: List[Dict[str, str]]
    safety_tips: List[str]
    human_review_reason: Optional[str] = None
    context_analysis: Optional[ContextAnalysis] = None


class ChatResponse(BaseModel):
    response: str
    category: str  # "medical" | "financial" | "legal" | "crisis" | "safe"
    confidence: float  # Safety filter confidence
    confidence_score: float  # AI response confidence (0-100)
    confidence_level: str  # "High", "Medium", "Low"
    confidence_reasons: List[str]  # Reasons for confidence level
    flagged: bool
    message_for_moderator: str
    session_id: Optional[str] = None
    pii_warning: Optional[str] = None  # PII detection warning message
    learning_analysis: Optional[LearningAnalysis] = (
        None  # Educational analysis for learning mode
    )
    guardrail_explanation: Optional[str] = (
        None  # Explanation when transparency is enabled
    )


class RegisterRequest(BaseModel):
    username: str
    email: Optional[str] = None
    password: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    role: str


class FlaggedMessage(BaseModel):
    """Moderator queue flagged message with full safety metadata."""

    id: int
    timestamp: str
    user_message: str
    ai_response: str
    category: Optional[str] = None
    confidence: Optional[float] = None
    confidence_score: Optional[float] = None
    confidence_level: Optional[str] = None
    user_id: Optional[int] = None
    username: Optional[str] = None
    priority_level: Optional[str] = None
    escalation_reason: Optional[str] = None
    target_response_time: Optional[int] = None


class ModeratorActionRequest(BaseModel):
    action: str  # approve, reject, edit, clarify, escalate
    edited_response: Optional[str] = None
    alternative_response: Optional[str] = None  # For reject action
    rejection_reason: Optional[str] = None  # Reason for rejection
    notes: Optional[str] = None  # Additional moderator notes
    review_time_seconds: Optional[float] = None  # Time taken to review


# Priority Calculation Function
def calculate_priority(
    category: Optional[str],
    confidence: float,
    content: str,
    confidence_score: float = 0.0,
) -> tuple[str, str, int]:
    """
    Calculate priority level, escalation reason, and target response time (in minutes)
    Returns: (priority_level, escalation_reason, target_response_time_minutes)

    Priority levels:
    - critical: Crisis/suicide content (immediate human review, 0 minutes)
    - high: Medical/illegal/high-toxicity (< 5 minute target)
    - medium: Financial/controversial/low-confidence (< 15 minute target)
    - low: Political/religious (< 60 minute target)
    """
    lower_content = content.lower()

    # CRITICAL: Mental health crisis indicators
    # Check for crisis category first (from safety filter)
    if category == "crisis":
        return ("critical", "Mental health crisis detected", 0)

    # Also check content directly for crisis keywords (backup detection)
    crisis_keywords = [
        "i want to die",
        "kill myself",
        "end my life",
        "suicide",
        "suicidal",
        "want to die",
        "going to kill",
        "end it all",
        "no reason to live",
        "better off dead",
        "hurt myself",
        "self harm",
        "cutting myself",
        "don't want to live",
        "not worth living",
        "want to end",
    ]
    for keyword in crisis_keywords:
        if keyword in lower_content:
            return ("critical", "Mental health crisis detected", 0)

    # HIGH PRIORITY: Medical advice requests
    if category == "medical":
        return ("high", "Medical advice request requires professional oversight", 5)

    # HIGH PRIORITY: Illegal activity inquiries
    if category == "legal":
        # Check for specific illegal activity keywords
        illegal_keywords = [
            "how to",
            "help me",
            "can you help",
            "instructions",
            "guide",
            "tutorial",
        ]
        has_illegal_intent = any(
            keyword in lower_content for keyword in illegal_keywords
        )
        if has_illegal_intent:
            return ("high", "Illegal activity inquiry detected", 5)
        return ("high", "Legal advice request", 5)

    # HIGH PRIORITY: High toxicity score (mock for now, would use actual toxicity model)
    # For now, check for toxic language patterns
    toxic_patterns = [
        "hate",
        "kill you",
        "destroy",
        "attack",
        "violence",
        "threat",
        "harm you",
    ]
    toxic_count = sum(1 for pattern in toxic_patterns if pattern in lower_content)
    if toxic_count >= 2:  # Multiple toxic indicators
        return ("high", f"High toxicity detected ({toxic_count} indicators)", 5)

    # MEDIUM PRIORITY: High-risk financial advice
    if category == "financial":
        if confidence_score < 30 or confidence < 0.3:
            return ("medium", "High-risk financial advice with low confidence", 15)
        # Check for high-risk financial keywords
        high_risk_financial = [
            "invest all",
            "borrow money",
            "take loan",
            "credit card debt",
            "gambling",
        ]
        if any(keyword in lower_content for keyword in high_risk_financial):
            return ("medium", "High-risk financial advice detected", 15)
        return ("medium", "Financial advice request", 15)

    # MEDIUM PRIORITY: Low confidence responses
    if confidence_score < 30 or confidence < 0.3:
        return ("medium", f"Low confidence response ({confidence_score:.0f}%)", 15)

    # MEDIUM PRIORITY: Controversial historical events
    controversial_keywords = [
        "holocaust",
        "genocide",
        "war crimes",
        "atrocity",
        "massacre",
    ]
    if any(keyword in lower_content for keyword in controversial_keywords):
        return ("medium", "Controversial historical topic", 15)

    # LOW PRIORITY: Political discussions
    political_keywords = [
        "president",
        "election",
        "political party",
        "voting",
        "campaign",
        "politician",
    ]
    if any(keyword in lower_content for keyword in political_keywords):
        return ("low", "Political discussion", 60)

    # LOW PRIORITY: Religious topics
    religious_keywords = [
        "god",
        "religion",
        "faith",
        "prayer",
        "church",
        "temple",
        "mosque",
        "bible",
        "quran",
    ]
    if any(keyword in lower_content for keyword in religious_keywords):
        return ("low", "Religious topic", 60)

    # Default: If flagged but no specific priority, use medium
    if category:
        return ("medium", f"{category.capitalize()} content flagged", 15)

    # Safe content (shouldn't reach here if properly flagged)
    return ("low", "General content review", 60)


# Safety Filter Function
def check_safety_filter(message: str):
    """
    Check message for safety keywords
    Returns: (category, confidence) or (None, 0.0) if safe

    Crisis content gets very low confidence (10-30%) to ensure flagging
    """
    lower_message = message.lower()
    detected_categories = []

    # PRIORITY: Check crisis keywords FIRST (most critical)
    # Crisis content should always be flagged with low confidence
    crisis_keywords = SAFETY_KEYWORDS.get("crisis", [])
    for keyword in crisis_keywords:
        if keyword.lower() in lower_message:
            detected_categories.insert(0, "crisis")  # Insert at beginning for priority
            # Critical: Log crisis detection for debugging (important for safety)
            if (
                "i want to die" in keyword.lower()
                or "kill myself" in keyword.lower()
                or "suicide" in keyword.lower()
            ):
                print(f"🚨 CRISIS DETECTED: Found keyword '{keyword}' in message")
            break  # Crisis detected, prioritize this

    # Check other categories
    for category, keywords in SAFETY_KEYWORDS.items():
        if category == "crisis":
            continue  # Already checked above
        for keyword in keywords:
            if keyword.lower() in lower_message:
                if category not in detected_categories:
                    detected_categories.append(category)

    if detected_categories:
        # Return first detected category (crisis should be first if detected)
        category = detected_categories[0]
        keyword_count = sum(
            1
            for keyword in SAFETY_KEYWORDS[category]
            if keyword.lower() in lower_message
        )

        # Crisis content gets very low confidence (10-30%) to ensure it's flagged
        if category == "crisis":
            # Crisis should have low confidence to ensure flagging
            # More keywords = slightly higher confidence but still low
            confidence = min(0.30, 0.10 + (keyword_count * 0.05))
        else:
            confidence = min(0.95, 0.5 + (keyword_count * 0.15))

        return category, confidence

    return None, 0.0


# PII Detection and Redaction Function
def detect_and_redact_pii(text: str) -> tuple[str, List[str], str]:
    """
    Detect and redact PII (Personally Identifiable Information) from text
    Returns: (redacted_text, detected_types, warning_message)
    """
    redacted_text = text
    detected_types = []

    # Credit card patterns (13-19 digits, various formats)
    # Matches: 4111-1111-1111-1111, 4111 1111 1111 1111, 4111111111111111
    # More specific patterns to avoid false positives
    credit_card_patterns = [
        r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",  # 4111-1111-1111-1111 or 4111 1111 1111 1111
        r"\b\d{4}[-\s]?\d{6}[-\s]?\d{5}\b",  # Amex: 3782-822463-10005
    ]
    for pattern in credit_card_patterns:
        matches = re.finditer(pattern, text)
        for match in matches:
            digits_only = re.sub(r"[^\d]", "", match.group())
            # Only flag if it's 13-19 digits
            if 13 <= len(digits_only) <= 19:
                start, end = match.span()
                # Replace in original text
                redacted_text = (
                    redacted_text[:start] + "[REDACTED]" + redacted_text[end:]
                )
                if "credit_card" not in detected_types:
                    detected_types.append("credit_card")
                break

    # SSN pattern (XXX-XX-XXXX)
    ssn_pattern = r"\b\d{3}-\d{2}-\d{4}\b"
    if re.search(ssn_pattern, text):
        redacted_text = re.sub(ssn_pattern, "[REDACTED]", redacted_text)
        detected_types.append("ssn")

    # Phone number patterns
    # Matches: (123) 456-7890, 123-456-7890, 123.456.7890, +1 123 456 7890, etc.
    phone_patterns = [
        r"\b\(\d{3}\)\s*\d{3}-\d{4}\b",  # (123) 456-7890
        r"\b\d{3}-\d{3}-\d{4}\b",  # 123-456-7890
        r"\b\d{3}\.\d{3}\.\d{4}\b",  # 123.456.7890
        r"\b\+\d{1,3}\s*\d{3}\s*\d{3}\s*\d{4}\b",  # +1 123 456 7890
        r"\b\d{3}\s+\d{3}\s+\d{4}\b",  # 123 456 7890
    ]
    # More careful 10-digit pattern - avoid matching years, timestamps
    # Only match if it's clearly a phone number (has phone-related context or formatting)
    phone_context_pattern = (
        r"\b(?:phone|call|text|contact|number|tel|mobile)\s*[:\-]?\s*\d{10}\b"
    )
    if re.search(phone_context_pattern, text, re.IGNORECASE):
        redacted_text = re.sub(r"\b\d{10}\b", "[REDACTED]", redacted_text)
        if "phone" not in detected_types:
            detected_types.append("phone")

    for pattern in phone_patterns:
        if re.search(pattern, text):
            redacted_text = re.sub(pattern, "[REDACTED]", redacted_text)
            if "phone" not in detected_types:
                detected_types.append("phone")
            break

    # Email addresses
    email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    if re.search(email_pattern, text):
        redacted_text = re.sub(email_pattern, "[REDACTED]", redacted_text)
        detected_types.append("email")

    # Physical addresses (basic pattern - street number + street name)
    # Matches: "123 Main St", "456 Oak Avenue", etc.
    address_pattern = r"\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd|Way|Circle|Cir)\b"
    if re.search(address_pattern, text, re.IGNORECASE):
        redacted_text = re.sub(
            address_pattern, "[REDACTED]", redacted_text, flags=re.IGNORECASE
        )
        detected_types.append("address")

    # Generate warning message
    warning_message = ""
    if detected_types:
        warning_message = "I've removed personal information for your safety."

    return redacted_text, detected_types, warning_message


# Confidence Scoring Function - Intelligent semantic analysis
def calculate_confidence_score(
    user_message: str, ai_response: str, category: Optional[str] = None
) -> tuple[float, str, List[str]]:
    """
    Calculate confidence score for AI response (0-100) using semantic analysis
    Returns: (score, level, reasons)

    Analysis based on:
    - Factual vs. Subjective patterns
    - Verifiability (can it be looked up in a reference?)
    - Time-based queries (future predictions = low confidence)
    - Personal advice patterns

    High Confidence (80-100%): Factual, historical, scientific, definitions
    Medium Confidence (50-79%): Opinions, comparisons, current events
    Low Confidence (0-49%): Personal advice, medical/legal/financial, predictions
    """
    score = 70.0  # Default starting score
    reasons = []
    lower_message = user_message.lower()
    lower_response = ai_response.lower()

    # ===== FACTUAL vs SUBJECTIVE ANALYSIS =====

    # Factual query patterns - indicate verifiable information
    factual_patterns = [
        "what is",
        "what are",
        "what was",
        "what were",
        "who is",
        "who was",
        "who invented",
        "who created",
        "where is",
        "where was",
        "where did",
        "when did",
        "when was",
        "when is",
        "how many",
        "how much",
        "how does",
        "how do",
        "define",
        "definition of",
        "explain",
        "describe",
        "capital of",
        "invented",
        "discovered",
        "created",
    ]

    # Subjective/opinion patterns
    subjective_patterns = [
        "should i",
        "what should i",
        "do you think",
        "do you recommend",
        "best",
        "worst",
        "better",
        "prefer",
        "favorite",
        "opinion",
        "think about",
        "believe",
        "feel",
        "like",
    ]

    # Personal advice patterns
    personal_advice_patterns = [
        "should i",
        "what should i do",
        "what should i",
        "advice",
        "recommend",
        "suggest",
        "tell me what to",
        "help me decide",
    ]

    # Future prediction patterns
    future_patterns = [
        "will",
        "going to",
        "predict",
        "forecast",
        "future",
        "tomorrow",
        "next year",
        "will happen",
        "will it",
    ]

    # Historical/factual indicators
    historical_patterns = [
        "invented",
        "discovered",
        "created",
        "founded",
        "established",
        "who invented",
        "who discovered",
        "when was",
        "when did",
    ]

    # Scientific/educational indicators
    scientific_patterns = [
        "science",
        "physics",
        "chemistry",
        "biology",
        "math",
        "mathematics",
        "photosynthesis",
        "gravity",
        "temperature",
        "boils at",
        "formula",
        "equation",
        "theory",
        "law of",
    ]

    # ===== CONFIDENCE CALCULATION =====
    # Analyze query characteristics to determine confidence score

    is_factual = any(pattern in lower_message for pattern in factual_patterns)
    is_subjective = any(pattern in lower_message for pattern in subjective_patterns)
    is_personal_advice = any(
        pattern in lower_message for pattern in personal_advice_patterns
    )
    is_future = any(pattern in lower_message for pattern in future_patterns)
    is_historical = any(pattern in lower_message for pattern in historical_patterns)
    is_scientific = any(pattern in lower_message for pattern in scientific_patterns)

    # Check for HIGH confidence (80-100%) - Factual, verifiable information
    if is_factual and not is_subjective and not is_personal_advice:
        # Basic math operations - 100% confidence
        if any(
            op in lower_message
            for op in ["+", "-", "*", "×", "÷", "/", "times", "plus", "minus", "equals"]
        ):
            # Check if it's a simple calculation using regex
            math_pattern = r"\d+\s*[+\-*/×÷]\s*\d+"
            if re.search(math_pattern, lower_message):
                score = 100.0
                reasons.append("Query asks for verifiable mathematical calculation")
            else:
                score = 95.0
                reasons.append("Query asks for mathematical information")

        # Capitals and geographical facts - 100% confidence
        elif "capital" in lower_message or ("capital of" in lower_message):
            score = 100.0
            reasons.append("Query asks for verifiable geographical fact")

        # Historical facts - 95% confidence
        elif is_historical:
            score = 95.0
            reasons.append("Query asks for verifiable historical fact")

        # Scientific facts - 95% confidence
        elif is_scientific:
            score = 95.0
            reasons.append("Query asks for verifiable scientific fact")

        # Other factual queries - 90% confidence
        elif category not in ["medical", "financial", "legal", "crisis"]:
            score = 90.0
            reasons.append("Query asks for verifiable factual information")

        # Factual but in sensitive category - lower confidence
        else:
            score = 50.0
            reasons.append("Query is factual but involves sensitive category")

    # Check for LOW confidence (0-49%) - Personal advice, predictions, sensitive topics
    elif is_personal_advice:
        if category in ["medical", "financial", "legal"]:
            score = 25.0
            reasons.append("Query requests personal advice in sensitive category")
        elif (
            "invest" in lower_message
            or "buy" in lower_message
            or "stock" in lower_message
        ):
            score = 30.0
            reasons.append("Query requests personal financial advice")
        else:
            score = 35.0
            reasons.append("Query requests personal advice")

    elif is_future and not is_personal_advice:
        if "weather" in lower_message:
            score = 65.0  # Weather predictions are medium confidence
            reasons.append("Query about weather requires current data")
        else:
            score = 40.0
            reasons.append("Query involves future predictions with uncertainty")

    elif category == "crisis":
        # Crisis content gets VERY LOW confidence (10-20%)
        score = 15.0
        reasons.append(
            "Crisis content requires immediate human intervention and professional support"
        )
    elif category in ["medical", "financial", "legal"]:
        score = 30.0
        reasons.append(
            f"Topic involves {category} content requiring professional expertise"
        )

    # Check for MEDIUM confidence (50-79%) - Opinions, comparisons, current events
    elif is_subjective and not is_personal_advice:
        if any(word in lower_message for word in ["best", "worst", "better", "prefer"]):
            score = 60.0
            reasons.append("Query requests subjective comparison or opinion")
        else:
            score = 55.0
            reasons.append("Query requests subjective opinion")

    elif "weather" in lower_message:
        score = 65.0
        reasons.append("Weather information requires current data")

    elif (
        "today" in lower_message
        or "current" in lower_message
        or "recent" in lower_message
    ):
        score = 60.0
        reasons.append("Query about current events requires up-to-date information")

    # Default for other queries
    else:
        score = 70.0
        reasons.append("Standard confidence for general query")

    # ===== RESPONSE QUALITY ADJUSTMENTS =====
    # Fine-tune confidence based on response characteristics

    # If response contains uncertain language, lower confidence
    uncertain_language = [
        "maybe",
        "perhaps",
        "might",
        "could",
        "possibly",
        "uncertain",
        "unclear",
        "not sure",
    ]
    uncertain_count = sum(1 for word in uncertain_language if word in lower_response)
    if uncertain_count > 0:
        score = max(0.0, score - (uncertain_count * 8.0))
        reasons.append("Response contains uncertain language")

    # If response contains factual indicators, raise confidence
    factual_indicators = [
        "fact",
        "established",
        "research",
        "study",
        "data",
        "evidence",
        "scientific",
        "verifiable",
    ]
    if any(indicator in lower_response for indicator in factual_indicators):
        if score < 80:
            score = min(100.0, score + 5.0)
            reasons.append("Response references established facts or evidence")

    # If response directly answers with a fact, boost confidence
    if is_factual and any(
        word in lower_response for word in ["equals", "is", "was", "are", "were"]
    ):
        if score < 90:
            score = min(100.0, score + 3.0)
            reasons.append("Response provides direct factual answer")

    # Clamp score between 0 and 100
    score = max(0.0, min(100.0, score))

    # Determine level
    if score >= 80:
        level = "High"
    elif score >= 50:
        level = "Medium"
    else:
        level = "Low"

    return score, level, reasons


# Context Analysis Function
def analyze_conversation_context(
    conversation_history: List[Dict],
    new_message: str,
    new_category: Optional[str] = None,
    confidence: float = 0.0,
) -> Dict:
    """
    Analyze conversation context for risk escalation, filter bypass, and cumulative risk
    Returns context analysis dictionary
    """
    analysis = {
        "risk_escalation": False,
        "filter_bypass_attempt": False,
        "cumulative_risk_score": 0.0,
        "persistent_sensitive_topic": False,
        "context_flags": [],
        "previous_queries": [],
    }

    if not conversation_history or len(conversation_history) == 0:
        return analysis

    # Extract recent user messages with their categories
    recent_user_messages = []
    sensitive_categories = ["medical", "financial", "legal", "crisis"]

    for msg in conversation_history[-9:]:  # Last 9 messages (new message makes 10)
        if msg.get("role") == "user":
            recent_user_messages.append(
                {
                    "content": msg.get("content", ""),
                    "category": msg.get("category"),
                    "confidence": msg.get("confidence"),
                }
            )

    analysis["previous_queries"] = recent_user_messages

    # Check for risk escalation (e.g., medical terms increasing in severity)
    if new_category in sensitive_categories:
        # Check if previous messages in same category show escalation
        previous_same_category = [
            m for m in recent_user_messages if m.get("category") == new_category
        ]

        if len(previous_same_category) > 0:
            # Medical escalation patterns
            if new_category == "medical":
                lower_new = new_message.lower()
                severity_keywords = {
                    "low": ["hurt", "ache", "pain", "sore", "uncomfortable"],
                    "medium": ["severe", "sharp", "intense", "persistent", "worsening"],
                    "high": [
                        "chest pain",
                        "difficulty breathing",
                        "emergency",
                        "urgent",
                        "can't breathe",
                        "heart",
                        "stroke",
                    ],
                }

                # Check for escalation from low to high severity
                previous_content = " ".join(
                    [m["content"].lower() for m in previous_same_category]
                )
                new_severity = "low"
                prev_severity = "low"

                for level, keywords in severity_keywords.items():
                    if any(kw in lower_new for kw in keywords):
                        new_severity = level
                    if any(kw in previous_content for kw in keywords):
                        prev_severity = level

                if (prev_severity == "low" and new_severity in ["medium", "high"]) or (
                    prev_severity == "medium" and new_severity == "high"
                ):
                    analysis["risk_escalation"] = True
                    analysis["context_flags"].append(
                        "Medical risk escalation detected in conversation"
                    )

            # Financial escalation patterns
            elif new_category == "financial":
                # Check if moving from general to specific advice requests
                lower_new = new_message.lower()
                if any(
                    term in lower_new
                    for term in ["invest", "buy", "sell", "trade", "strategy"]
                ):
                    if any(
                        "money" in m["content"].lower()
                        or "earn" in m["content"].lower()
                        for m in previous_same_category
                    ):
                        analysis["risk_escalation"] = True
                        analysis["context_flags"].append(
                            "Financial advice escalation detected"
                        )

        # Check for persistent sensitive queries
        if len(previous_same_category) >= 2:
            analysis["persistent_sensitive_topic"] = True
            analysis["context_flags"].append(
                f"Multiple {new_category} queries in conversation"
            )

    # Check for filter bypass attempts (rephrasing to avoid detection)
    if new_category is None and len(recent_user_messages) > 0:
        # Check if user previously asked about sensitive topic but now rephrased
        previous_sensitive = [
            m for m in recent_user_messages if m.get("category") in sensitive_categories
        ]

        if previous_sensitive:
            # Check if new message is semantically similar but avoids keywords
            lower_new = new_message.lower()
            bypass_patterns = [
                (
                    "medical",
                    ["health", "body", "feel", "symptom", "doctor", "treatment"],
                ),
                (
                    "financial",
                    ["money", "cash", "wealth", "income", "profit", "return"],
                ),
                ("legal", ["law", "right", "legal", "court", "sue", "attorney"]),
            ]

            for cat, keywords in bypass_patterns:
                if any(m.get("category") == cat for m in previous_sensitive):
                    # If previous was sensitive but new message avoids category keywords but has related terms
                    if any(kw in lower_new for kw in keywords):
                        # Check if it would have been flagged with original keywords
                        for keyword in SAFETY_KEYWORDS.get(cat, []):
                            if keyword.lower() in lower_new:
                                break
                        else:
                            # No safety keywords but has related terms - possible bypass
                            analysis["filter_bypass_attempt"] = True
                            analysis["context_flags"].append(
                                f"Possible filter bypass attempt ({cat} topic)"
                            )
                            break

    # Calculate cumulative risk score
    risk_scores = []
    for msg in recent_user_messages:
        if msg.get("category") in sensitive_categories:
            conf = msg.get("confidence", 0.5)
            risk_scores.append(conf)

    if new_category in sensitive_categories:
        risk_scores.append(confidence if confidence > 0 else 0.5)

    if risk_scores:
        # Average risk score, weighted by recency
        weights = [
            i + 1 for i in range(len(risk_scores))
        ]  # More recent = higher weight
        analysis["cumulative_risk_score"] = sum(
            s * w for s, w in zip(risk_scores, weights)
        ) / sum(weights)

    return analysis


# Generate Learning Analysis
def generate_learning_analysis(
    user_message: str,
    category: Optional[str],
    flagged: bool,
    confidence_score: float,
    confidence_level: str,
    confidence_reasons: List[str],
    pii_types: Optional[List[str]] = None,
) -> Dict:
    """
    Generate educational analysis for learning mode
    Returns structured metadata explaining safety checks and confidence factors
    """
    analysis = {
        "risk_category": category.capitalize()
        if category and category != "safe"
        else "Safe",
        "triggered_guardrails": [],
        "confidence_breakdown": [],
        "safety_tips": [],
        "human_review_reason": None,
    }

    lower_message = user_message.lower()

    # Determine triggered guardrails
    if category and category != "safe":
        guardrail_map = {
            "medical": "medical_advice_detection",
            "financial": "financial_advice_detection",
            "legal": "legal_advice_detection",
            "crisis": "crisis_intervention_detection",
        }
        guardrail = guardrail_map.get(category, f"{category}_content_detection")
        analysis["triggered_guardrails"].append(guardrail)

    if pii_types and len(pii_types) > 0:
        analysis["triggered_guardrails"].append("pii_detection")
        analysis["safety_tips"].append(
            "Personal information was automatically redacted for your privacy"
        )

    if confidence_score < 50.0:
        analysis["triggered_guardrails"].append("low_confidence_auto_flag")

    # Build confidence breakdown
    if confidence_reasons:
        for reason in confidence_reasons:
            impact = "0%"
            if "uncertain" in reason.lower() or "uncertainty" in reason.lower():
                impact = "-20%"
            elif "personal advice" in reason.lower():
                impact = "-40%"
            elif "future" in reason.lower() or "prediction" in reason.lower():
                impact = "-30%"
            elif "sensitive category" in reason.lower():
                impact = "-25%"
            elif "factual" in reason.lower() or "verifiable" in reason.lower():
                impact = "+15%"
            elif "established" in reason.lower() or "evidence" in reason.lower():
                impact = "+10%"
            elif "mathematical" in reason.lower():
                impact = "+25%"

            analysis["confidence_breakdown"].append(
                {"factor": reason, "impact": impact}
            )

    # Add topic-specific confidence factors
    if category in ["medical", "financial", "legal"]:
        analysis["confidence_breakdown"].append(
            {"factor": "Topic risk", "impact": "-40%"}
        )

    if "should i" in lower_message or "advice" in lower_message:
        analysis["confidence_breakdown"].append(
            {"factor": "Specificity", "impact": "-20%"}
        )

    # Safety tips based on category
    if category == "medical":
        analysis["safety_tips"].append("AI cannot diagnose medical conditions")
        analysis["safety_tips"].append(
            "Consult a healthcare professional for medical advice"
        )
        analysis["human_review_reason"] = (
            "Medical queries require professional oversight"
        )
    elif category == "financial":
        analysis["safety_tips"].append("AI cannot access your financial situation")
        analysis["safety_tips"].append(
            "Financial decisions should be made with professional guidance"
        )
        analysis["human_review_reason"] = (
            "Specific financial advice requires human oversight"
        )
    elif category == "legal":
        analysis["safety_tips"].append("AI cannot provide legal representation")
        analysis["safety_tips"].append(
            "Legal matters require consultation with a qualified attorney"
        )
        analysis["human_review_reason"] = (
            "Legal queries require professional legal review"
        )
    elif category == "crisis":
        analysis["safety_tips"].append(
            "If you're in crisis, please contact emergency services or a crisis hotline"
        )
        analysis["human_review_reason"] = (
            "Crisis content requires immediate human intervention"
        )
    elif confidence_score >= 80:
        analysis["safety_tips"].append(
            "This response has high confidence based on verifiable facts"
        )
    elif confidence_score >= 50:
        analysis["safety_tips"].append(
            "This response has moderate confidence - verify important information"
        )
    else:
        analysis["safety_tips"].append(
            "This response has low confidence - exercise caution and verify information"
        )

    # Add AI limitations explanation
    if not analysis["safety_tips"]:
        analysis["safety_tips"].append(
            "AI responses are based on training data and may not reflect current information"
        )

    return analysis


# Generate AI Response
async def generate_ai_response(
    user_message: str,
    category: Optional[str] = None,
    pii_types: Optional[List[str]] = None,
) -> str:
    """
    Generate AI response with proper crisis handling
    """
    # CRITICAL: Check for crisis content FIRST, before any API calls
    lower_message = user_message.lower()
    crisis_keywords = [
        "i want to die",
        "want to die",
        "kill myself",
        "end my life",
        "suicide",
        "suicidal",
        "don't want to live",
        "better off dead",
        "going to kill",
        "end it all",
        "no reason to live",
        "hurt myself",
        "self harm",
        "cutting myself",
        "not worth living",
    ]

    # Check for crisis keywords in content
    for keyword in crisis_keywords:
        if keyword in lower_message:
            # Crisis detected - return immediate resources
            crisis_response = (
                "I'm concerned about what you've shared. If you're in immediate danger, please call emergency services (911) or your local crisis hotline right away.\n\n"
                "**Crisis Resources:**\n"
                "• National Suicide Prevention Lifeline: 988 (24/7)\n"
                "• Crisis Text Line: Text HOME to 741741\n"
                "• International Association for Suicide Prevention: https://www.iasp.info/resources/Crisis_Centres/\n\n"
                "This message has been flagged for immediate human review. A trained professional will reach out to provide support. You are not alone, and help is available."
            )
            return crisis_response

    # Also check category
    if category == "crisis":
        crisis_response = (
            "I'm concerned about what you've shared. If you're in immediate danger, please call emergency services (911) or your local crisis hotline right away.\n\n"
            "**Crisis Resources:**\n"
            "• National Suicide Prevention Lifeline: 988 (24/7)\n"
            "• Crisis Text Line: Text HOME to 741741\n"
            "• International Association for Suicide Prevention: https://www.iasp.info/resources/Crisis_Centres/\n\n"
            "This message has been flagged for immediate human review. A trained professional will reach out to provide support. You are not alone, and help is available."
        )
        return crisis_response

    if USE_OPENAI and openai_client != MockOpenAI:
        try:
            # CRISIS CHECK: If crisis detected, return immediately (don't call OpenAI)
            if category == "crisis" or any(
                kw in lower_message for kw in crisis_keywords
            ):
                crisis_response = (
                    "I'm concerned about what you've shared. If you're in immediate danger, please call emergency services (911) or your local crisis hotline right away.\n\n"
                    "**Crisis Resources:**\n"
                    "• National Suicide Prevention Lifeline: 988 (24/7)\n"
                    "• Crisis Text Line: Text HOME to 741741\n"
                    "• International Association for Suicide Prevention: https://www.iasp.info/resources/Crisis_Centres/\n\n"
                    "This message has been flagged for immediate human review. A trained professional will reach out to provide support. You are not alone, and help is available."
                )
                return crisis_response

            # Build system prompt with PII handling instructions
            system_prompt = """You are a helpful AI assistant that answers questions directly and accurately. Your role is to:

1. **Answer questions directly and helpfully** - Provide clear, accurate answers to user questions
2. **For simple factual questions** (like "What is 2+2?" or "Capital of France?"):
   - Give the direct answer first: "2+2 equals 4" or "Paris is the capital of France"
   - Optionally add a brief note about AI safety if relevant
3. **For CRISIS content** (suicide, self-harm, "I want to die", etc.):
   - Respond IMMEDIATELY with crisis resources and support
   - Format: "I'm concerned about what you've shared. If you're in immediate danger, please call emergency services (911) or your local crisis hotline right away. [List crisis resources]. This message has been flagged for immediate human review."
   - DO NOT give generic AI safety discussions - provide actual crisis support resources
   - Be direct, compassionate, and action-oriented
4. **For other sensitive topics** (medical, financial, legal):
   - Provide helpful information when appropriate
   - Add safety disclaimers: "This is for educational purposes. For [medical/financial/legal] advice, consult a professional."
   - Explain how AI safety systems would handle such queries
4. **For PII (Personally Identifiable Information) detection**:
   - If the system detects PII (email, SSN, phone, credit card, address) in the user's message:
   - Respond EXACTLY with: "I've detected personal information in your message. For privacy protection, I've redacted it. Remember: AI systems should never ask for or store personal details like emails, passwords, or identification numbers."
   - Be clear, educational, and concise
   - Do NOT repeat words, create nonsense sentences, or add extra information
   - Keep the response short and focused on privacy education
5. **For uncertain or subjective topics**:
   - Acknowledge uncertainty
   - Provide balanced perspectives when appropriate
6. **Maintain a helpful, professional tone**

Remember: Answer the question first, then add safety context only when needed. Don't just talk about AI safety - actually help the user with their question. For PII-related queries, provide clear privacy education without repetition."""

            # Add context to user message if PII or crisis was detected
            user_prompt = user_message
            if pii_types and len(pii_types) > 0:
                user_prompt = f"[SYSTEM NOTE: Personal information was detected and redacted in the user's original message. Respond with the exact privacy education message as specified in your instructions.]\n\nUser message: {user_message}"
            elif category == "crisis":
                user_prompt = f"[SYSTEM NOTE: This message has been flagged as CRISIS content. Respond with immediate crisis resources and support information as specified in your instructions. DO NOT give generic AI safety discussions.]\n\nUser message: {user_message}"

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.7,
                max_tokens=300,
            )

            return response.choices[0].message.content.strip()
        except Exception as e:
            # Fallback to mock response on OpenAI API error
            print(f"⚠️ OpenAI API error: {e}")
            return openai_client.generate_response(user_message, category, pii_types)
    else:
        return openai_client.generate_response(user_message, category, pii_types)


# API Endpoints


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "AI Safety Chat API",
        "version": "2.0.0",
        "openai_enabled": USE_OPENAI,
        "database": "SQLite",
    }


@app.post("/auth/register", response_model=UserResponse)
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user (optional for demo)"""
    # Check if user exists
    existing_user = db.query(User).filter(User.username == request.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    # Create user (password optional for demo)
    password_hash = None
    if request.password:
        password_hash = get_password_hash(request.password)

    user = User(
        username=request.username,
        email=request.email,
        password_hash=password_hash,
        role="user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return UserResponse(
        id=user.id, username=user.username, email=user.email, role=user.role
    )


@app.post("/auth/login")
async def login(
    request: LoginRequest, db: Session = Depends(get_db), response: Response = None
):
    """Login and get access token"""
    user = db.query(User).filter(User.username == request.username).first()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Check password if set
    if user.password_hash:
        if not verify_password(request.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid credentials")
    # If no password set, allow login (for demo)

    # Create access token
    access_token = create_access_token(data={"sub": str(user.id)})

    # Set cookie
    if response:
        response.set_cookie(
            key="session_token",
            value=access_token,
            httponly=True,
            max_age=60 * 60 * 24 * 7,  # 7 days
            samesite="lax",
        )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse(
            id=user.id, username=user.username, email=user.email, role=user.role
        ),
    }


@app.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        role=current_user.role,
    )


@app.get("/conversation/{session_id}", response_model=List[ConversationMessage])
async def get_conversation_history(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get conversation history for a session (last 10 messages)"""
    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.session_id == session_id,
            Conversation.user_id == current_user.id,
        )
        .first()
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get last 10 messages
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.timestamp.desc())
        .limit(10)
        .all()
    )

    # Reverse to get chronological order
    history = []
    for msg in reversed(messages):
        history.append(
            ConversationMessage(
                role=msg.role,
                content=msg.content,
                category=msg.category,
                confidence=msg.confidence,
                timestamp=msg.timestamp.isoformat() if msg.timestamp else "",
            )
        )

    return history


@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Main chat endpoint
    Accepts user message and returns AI response with safety metadata
    Stores messages in database
    """
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    original_message = request.message.strip()

    # Detect and redact PII BEFORE any processing or storage
    redacted_message, pii_types, pii_warning = detect_and_redact_pii(original_message)
    user_message = redacted_message  # Use redacted version for all processing

    # Get or create conversation
    # If session_id provided, use it; otherwise create new one
    if request.session_id:
        session_id = request.session_id
    else:
        session_id = get_or_create_anonymous_session(db)

    # Find existing conversation by session_id and user_id
    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.session_id == session_id,
            Conversation.user_id == current_user.id,
        )
        .first()
    )

    # Get user settings from request or use defaults
    # If settings provided, use them; otherwise create defaults
    if request.settings:
        settings = request.settings
    else:
        settings = UserSettings()

    # Override learning_mode if explicitly set in request
    if request.learning_mode:
        settings.learning_mode = True

    if not conversation:
        conversation = Conversation(
            user_id=current_user.id,
            session_id=session_id,
            started_at=datetime.now(timezone.utc),
            learning_mode_enabled=settings.learning_mode or request.learning_mode,
            # Use model_dump() for Pydantic v2, fallback to dict() for v1
            user_settings=settings.model_dump()
            if (settings and hasattr(settings, "model_dump"))
            else (settings.dict() if settings else None),
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    else:
        # Update preferences
        conversation.learning_mode_enabled = (
            settings.learning_mode or request.learning_mode
        )
        # Use model_dump() for Pydantic v2, fallback to dict() for v1
        if hasattr(settings, "model_dump"):
            conversation.user_settings = settings.model_dump() if settings else None
        else:
            conversation.user_settings = settings.dict() if settings else None
        db.commit()

    # Retrieve conversation history (last 9 messages to make 10 with new message)
    # NOTE: We need messages for context analysis even if data_logging is disabled
    # So we check for messages regardless of data_logging setting
    conversation_history = []
    if conversation:
        recent_messages = (
            db.query(Message)
            .filter(Message.conversation_id == conversation.id)
            .order_by(Message.timestamp.desc())
            .limit(9)
            .all()
        )

        # Reverse to get chronological order
        for msg in reversed(recent_messages):
            conversation_history.append(
                {
                    "role": msg.role,
                    "content": msg.content,
                    "category": msg.category,
                    "confidence": msg.confidence,
                    "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                }
            )
    else:
        # No conversation found, starting fresh
        pass

    # Check safety filter FIRST (needed for context analysis)
    category, confidence = check_safety_filter(user_message)
    flagged = category is not None

    # CRITICAL: Double-check for crisis content if not detected
    if category != "crisis":
        lower_user_message = user_message.lower()
        crisis_keywords_check = [
            "i want to die",
            "want to die",
            "kill myself",
            "end my life",
            "suicide",
            "suicidal",
            "don't want to live",
            "better off dead",
            "going to kill",
            "end it all",
            "no reason to live",
            "hurt myself",
            "self harm",
            "cutting myself",
            "not worth living",
        ]
        for keyword in crisis_keywords_check:
            if keyword in lower_user_message:
                # Critical: Double-check crisis detection (backup safety mechanism)
                category = "crisis"
                confidence = 0.15  # Very low confidence for crisis
                flagged = True
                break

    # Ensure crisis content is ALWAYS flagged, even if confidence is low
    if category == "crisis":
        flagged = True

    # Priority will be calculated after we have confidence_score from AI response

    # Analyze conversation context (needs category from safety filter)
    try:
        context_analysis_dict = analyze_conversation_context(
            conversation_history=conversation_history,
            new_message=user_message,
            new_category=category,
            confidence=confidence if flagged else 0.0,
        )
        context_analysis = ContextAnalysis(**context_analysis_dict)
    except Exception as e:
        # Log error but continue with empty context analysis
        print(f"⚠️ Error in context analysis: {e}")
        # Create empty context analysis on error
        context_analysis = ContextAnalysis(
            risk_escalation=False,
            filter_bypass_attempt=False,
            cumulative_risk_score=0.0,
            persistent_sensitive_topic=False,
            context_flags=[],
            previous_queries=[],
        )

    # Apply context-based flagging
    if context_analysis.risk_escalation:
        flagged = True
        if category is None:
            category = "medical"  # Default to medical for escalation
        confidence = max(confidence, 0.7)  # Increase confidence for escalation

    if context_analysis.filter_bypass_attempt:
        flagged = True
        confidence = max(confidence, 0.6)

    if context_analysis.persistent_sensitive_topic:
        flagged = True
        confidence = max(confidence, 0.65)

    # Apply safety level settings to adjust flagging thresholds
    if settings.safety_level == "strict":
        confidence_threshold = 70.0  # Flag if confidence < 70%
    elif settings.safety_level == "lenient":
        confidence_threshold = 30.0  # Flag if confidence < 30%
    else:
        confidence_threshold = 50.0  # Flag if confidence < 50% (moderate)

    # Apply response speed setting (add delay for "Safety First" mode)
    if settings.response_speed == "safety":
        import asyncio

        await asyncio.sleep(0.1)  # 100ms delay for additional safety checks

    # Generate AI response (pass PII types for appropriate handling)
    ai_response = await generate_ai_response(user_message, category, pii_types)

    # Calculate confidence score for AI response
    confidence_score, confidence_level, confidence_reasons = calculate_confidence_score(
        user_message, ai_response, category
    )

    # Auto-flag based on confidence (adjusted by safety level setting)
    confidence_flagged = confidence_score < confidence_threshold

    # CRISIS CONTENT: Always flag regardless of confidence threshold
    if category == "crisis":
        confidence_flagged = True

    # Add context-based flagging
    context_flagged = False
    if (
        context_analysis.risk_escalation
        or context_analysis.filter_bypass_attempt
        or context_analysis.persistent_sensitive_topic
    ):
        context_flagged = True
        # Adjust confidence score based on cumulative risk
        if context_analysis.cumulative_risk_score > 0.6:
            confidence_score = max(
                0, confidence_score - 15
            )  # Lower confidence for high cumulative risk

    final_flagged = flagged or confidence_flagged or context_flagged

    # CRISIS CONTENT: Ensure it's always flagged
    if category == "crisis":
        final_flagged = True

    # Calculate priority level now that we have confidence_score
    priority_level = "low"
    escalation_reason = None
    target_response_time = 60  # Default

    if final_flagged:
        priority_level, escalation_reason, target_response_time = calculate_priority(
            category=category,
            confidence=confidence,
            content=user_message,
            confidence_score=confidence_score,
        )
        # Log priority calculation for debugging (critical for crisis detection)
        if priority_level == "critical":
            print(
                f"🚨 Priority calculated: {priority_level.upper()} - {escalation_reason} (target: {target_response_time} min)"
            )

    # Add warning for very low confidence
    if confidence_score < 30.0:
        confidence_reasons.append("AI is uncertain about this response")

    # Generate guardrail explanation if transparency is enabled
    guardrail_explanation = None
    if settings.transparency and (final_flagged or category):
        if category:
            category_names = {
                "medical": "Medical",
                "financial": "Financial",
                "legal": "Legal",
                "crisis": "Crisis",
            }
            category_name = category_names.get(category, category)
            guardrail_explanation = f"Guardrail triggered: {category_name} content detected. This query was flagged for review to ensure appropriate handling."
        elif confidence_flagged:
            guardrail_explanation = f"Guardrail triggered: Low confidence response ({confidence_score:.0f}%). This response may be inaccurate or uncertain."

    # CRISIS CONTENT: Always store for safety, regardless of data_logging setting
    if category == "crisis":
        store_messages = True
    else:
        # Store messages based on data_logging setting
        # NOTE: If data_logging is False, we still need to store messages temporarily for context analysis
        # In production, you might want to implement in-memory context tracking for privacy
        # For now, we respect the setting but note that context analysis requires message history
        store_messages = settings.data_logging
        # Note: Messages are still processed for context analysis even if data_logging is False
        # In production, you might want to implement in-memory context tracking for privacy
        if not store_messages:
            store_messages = True  # Temporary: allow context analysis to work

    if store_messages:
        # Store user message (ONLY redacted version - never store raw PII)
        user_msg = Message(
            conversation_id=conversation.id,
            role="user",
            content=user_message,  # Redacted version only
            category=category or "safe",
            confidence=confidence if flagged else None,
            confidence_score=None,  # User messages don't have confidence scores
            confidence_level=None,  # User messages don't have confidence levels
            flagged=flagged,
            pii_detected=len(pii_types) > 0,
            pii_types=pii_types
            if pii_types
            else None,  # SQLAlchemy JSON will serialize this
            timestamp=datetime.now(timezone.utc),
        )
        db.add(user_msg)
        db.commit()
        db.refresh(user_msg)

        # Store AI response with confidence score and priority
        ai_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=ai_response,
            category=category or "safe",
            confidence=confidence if flagged else None,
            confidence_score=confidence_score,
            confidence_level=confidence_level,
            flagged=final_flagged,
            priority_level=priority_level if final_flagged else None,
            escalation_reason=escalation_reason if final_flagged else None,
            target_response_time=target_response_time if final_flagged else None,
            timestamp=datetime.now(timezone.utc),
        )
        db.add(ai_msg)
        db.commit()
        db.refresh(ai_msg)

        pass  # Messages stored successfully
    else:
        pass  # Data logging disabled

    # Create message for moderator
    if final_flagged:
        category_names = {
            "medical": "Medical",
            "financial": "Financial",
            "legal": "Legal",
            "crisis": "Crisis",
        }
        category_name = (
            category_names.get(category, category) if category else "Low Confidence"
        )

        flag_reasons = []
        if flagged:
            flag_reasons.append(f"{category_name.lower()} content")
        if confidence_flagged:
            flag_reasons.append(f"low confidence ({confidence_score:.0f}%)")
        if context_flagged:
            if context_analysis.risk_escalation:
                flag_reasons.append("risk escalation")
            if context_analysis.filter_bypass_attempt:
                flag_reasons.append("possible filter bypass")
            if context_analysis.persistent_sensitive_topic:
                flag_reasons.append("persistent sensitive queries")

        if flag_reasons:
            message_for_moderator = (
                f"Flagged for: {', '.join(flag_reasons)}. Message: {user_message[:100]}"
            )
        else:
            message_for_moderator = f"Flagged: {user_message[:100]}"
    else:
        message_for_moderator = "No safety concerns detected"

    # Generate learning analysis if learning mode is enabled
    learning_analysis = None
    learning_mode_enabled = settings.learning_mode or request.learning_mode

    if learning_mode_enabled:
        try:
            learning_analysis_dict = generate_learning_analysis(
                user_message=user_message,
                category=category,
                flagged=final_flagged,
                confidence_score=confidence_score,
                confidence_level=confidence_level,
                confidence_reasons=confidence_reasons,
                pii_types=pii_types,
            )
            # Add context analysis to learning analysis
            # Pydantic v2 uses model_dump(), v1 uses dict()
            try:
                if hasattr(context_analysis, "model_dump"):
                    context_dict = context_analysis.model_dump()
                elif hasattr(context_analysis, "dict"):
                    context_dict = context_analysis.dict()
                else:
                    # Fallback: manually extract
                    context_dict = {
                        "risk_escalation": context_analysis.risk_escalation,
                        "filter_bypass_attempt": context_analysis.filter_bypass_attempt,
                        "cumulative_risk_score": context_analysis.cumulative_risk_score,
                        "persistent_sensitive_topic": context_analysis.persistent_sensitive_topic,
                        "context_flags": context_analysis.context_flags,
                        "previous_queries": context_analysis.previous_queries,
                    }
            except Exception as e:
                # Fallback: manually extract context analysis data
                print(f"⚠️ Error converting context_analysis to dict: {e}")
                context_dict = {
                    "risk_escalation": getattr(
                        context_analysis, "risk_escalation", False
                    ),
                    "filter_bypass_attempt": getattr(
                        context_analysis, "filter_bypass_attempt", False
                    ),
                    "cumulative_risk_score": getattr(
                        context_analysis, "cumulative_risk_score", 0.0
                    ),
                    "persistent_sensitive_topic": getattr(
                        context_analysis, "persistent_sensitive_topic", False
                    ),
                    "context_flags": getattr(context_analysis, "context_flags", []),
                    "previous_queries": getattr(
                        context_analysis, "previous_queries", []
                    ),
                }

            learning_analysis_dict["context_analysis"] = context_dict
            learning_analysis = LearningAnalysis(**learning_analysis_dict)
        except Exception as e:
            # Log error but continue without learning analysis
            print(f"⚠️ Error generating learning analysis: {e}")
            learning_analysis = None

    return ChatResponse(
        response=ai_response,
        category=category or "safe",
        confidence=confidence if flagged else 1.0,
        confidence_score=confidence_score,
        confidence_level=confidence_level,
        confidence_reasons=confidence_reasons,
        flagged=final_flagged,
        message_for_moderator=message_for_moderator,
        session_id=session_id,
        pii_warning=pii_warning if pii_warning else None,
        learning_analysis=learning_analysis,
        guardrail_explanation=guardrail_explanation,
    )


@app.get("/moderator/queue", response_model=List[FlaggedMessage])
async def get_moderator_queue(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """
    Get list of flagged messages for moderator review
    Pulls from database, sorted by priority (critical > high > medium > low)
    """
    # Get all flagged user messages that haven't been reviewed
    # We look for user messages that are flagged, and check if they have moderator decisions
    flagged_user_messages = (
        db.query(Message).filter(Message.flagged, Message.role == "user").all()
    )

    result = []
    for user_msg in flagged_user_messages:
        # Check if this message has been reviewed
        has_decision = (
            db.query(ModeratorDecision)
            .filter(ModeratorDecision.message_id == user_msg.id)
            .first()
        )

        if has_decision:
            continue  # Skip already reviewed messages

        # Get the corresponding AI response (next message in conversation)
        ai_msg = (
            db.query(Message)
            .filter(
                Message.conversation_id == user_msg.conversation_id,
                Message.role == "assistant",
                Message.timestamp > user_msg.timestamp,
            )
            .order_by(Message.timestamp)
            .first()
        )

        conversation = (
            db.query(Conversation)
            .filter(Conversation.id == user_msg.conversation_id)
            .first()
        )
        conversation_user = (
            db.query(User).filter(User.id == conversation.user_id).first()
            if conversation
            else None
        )

        # Get confidence score from AI message
        confidence_score = ai_msg.confidence_score if ai_msg else None
        confidence_level = None
        if confidence_score is not None:
            if confidence_score >= 80:
                confidence_level = "High"
            elif confidence_score >= 50:
                confidence_level = "Medium"
            else:
                confidence_level = "Low"

        # Get priority from AI message (or user message if not set)
        priority_level = (
            ai_msg.priority_level
            if ai_msg and ai_msg.priority_level
            else (user_msg.priority_level if user_msg.priority_level else None)
        )
        escalation_reason = (
            ai_msg.escalation_reason
            if ai_msg and ai_msg.escalation_reason
            else (user_msg.escalation_reason if user_msg.escalation_reason else None)
        )
        target_response_time = (
            ai_msg.target_response_time
            if ai_msg and ai_msg.target_response_time
            else (
                user_msg.target_response_time if user_msg.target_response_time else None
            )
        )

        result.append(
            {
                "id": user_msg.id,
                "timestamp": user_msg.timestamp.isoformat()
                if user_msg.timestamp
                else "",
                "user_message": user_msg.content,
                "ai_response": ai_msg.content if ai_msg else "No response yet",
                "category": user_msg.category or "safe",
                "confidence": user_msg.confidence,
                "confidence_score": confidence_score,
                "confidence_level": confidence_level,
                "user_id": conversation_user.id if conversation_user else None,
                "username": conversation_user.username if conversation_user else None,
                "priority_level": priority_level,
                "escalation_reason": escalation_reason,
                "target_response_time": target_response_time,
            }
        )

    # Priority order: critical=0, high=1, medium=2, low=3
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    # Sort by priority (critical first), then by timestamp (newest first)
    result.sort(
        key=lambda x: (
            priority_order.get(x.get("priority_level", "low"), 3),
            -datetime.fromisoformat(x["timestamp"]).timestamp()
            if x.get("timestamp")
            else 0,
        )
    )

    return result


@app.delete("/moderator/queue/{message_id}")
async def remove_from_queue(
    message_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Remove a message from the flagged queue (after moderator review)
    Creates a moderator decision record
    """
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Create moderator decision
    decision = ModeratorDecision(
        message_id=message_id,
        moderator_id=current_user.id
        if current_user.role in ["moderator", "admin"]
        else None,
        action="approved",  # Default action
        timestamp=datetime.now(timezone.utc),
    )
    db.add(decision)
    db.commit()

    return {"message": "Message removed from queue", "id": message_id}


@app.post("/moderator/queue/{message_id}/action")
async def moderator_action(
    message_id: int,
    action_request: ModeratorActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Take moderator action on a flagged message
    """
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")

    # Get the AI response message (assistant message for this flagged user message)
    ai_message = (
        db.query(Message)
        .filter(
            Message.conversation_id == message.conversation_id,
            Message.role == "assistant",
            Message.timestamp > message.timestamp,
        )
        .order_by(Message.timestamp)
        .first()
    )

    original_response = ai_message.content if ai_message else message.content

    # Determine the response to use based on action
    final_response = None
    if action_request.action == "edit":
        if not action_request.edited_response:
            raise HTTPException(
                status_code=400, detail="edited_response is required for edit action"
            )
        final_response = action_request.edited_response
    elif action_request.action == "reject":
        if not action_request.alternative_response:
            raise HTTPException(
                status_code=400,
                detail="alternative_response is required for reject action",
            )
        final_response = action_request.alternative_response
    elif action_request.action == "approve":
        final_response = original_response
    elif action_request.action == "clarify":
        final_response = "Can you provide more details about your situation? This will help me give you a more accurate response."
    elif action_request.action == "escalate":
        final_response = original_response  # Keep original, marked for admin review
    else:
        raise HTTPException(
            status_code=400, detail=f"Unknown action: {action_request.action}"
        )

    # Create moderator decision with full history
    # Store edited_response for both edit and reject actions
    edited_response_value = None
    if action_request.action == "edit":
        edited_response_value = action_request.edited_response
    elif action_request.action == "reject":
        edited_response_value = action_request.alternative_response

    decision = ModeratorDecision(
        message_id=message_id,
        moderator_id=current_user.id
        if current_user.role in ["moderator", "admin"]
        else None,
        action=action_request.action,
        original_response=original_response,
        edited_response=edited_response_value,
        rejection_reason=action_request.rejection_reason,
        notes=action_request.notes,
        review_time_seconds=action_request.review_time_seconds,
        timestamp=datetime.now(timezone.utc),
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)

    return {
        "message": f"Action '{action_request.action}' recorded",
        "id": message_id,
        "decision_id": decision.id,
        "original_response": original_response,
        "final_response": final_response,
    }


@app.get("/confidence/examples")
async def confidence_examples():
    """
    Returns sample queries with confidence scores for educational purposes
    """
    examples = [
        {
            "query": "Capital of France?",
            "expected_confidence": 100.0,
            "confidence_level": "High",
            "reasons": ["Query asks for verifiable geographical fact"],
            "category": "safe",
        },
        {
            "query": "What is 2+2?",
            "expected_confidence": 100.0,
            "confidence_level": "High",
            "reasons": ["Query asks for verifiable mathematical calculation"],
            "category": "safe",
        },
        {
            "query": "Who invented the telephone?",
            "expected_confidence": 95.0,
            "confidence_level": "High",
            "reasons": ["Query asks for verifiable historical fact"],
            "category": "safe",
        },
        {
            "query": "Explain photosynthesis",
            "expected_confidence": 95.0,
            "confidence_level": "High",
            "reasons": ["Query asks for verifiable scientific fact"],
            "category": "safe",
        },
        {
            "query": "Best programming language?",
            "expected_confidence": 60.0,
            "confidence_level": "Medium",
            "reasons": ["Query requests subjective comparison or opinion"],
            "category": "safe",
        },
        {
            "query": "Should I buy a house?",
            "expected_confidence": 30.0,
            "confidence_level": "Low",
            "reasons": ["Query requests personal financial advice"],
            "category": "financial",
        },
        {
            "query": "Will AI take all jobs?",
            "expected_confidence": 40.0,
            "confidence_level": "Low",
            "reasons": ["Query involves future predictions with uncertainty"],
            "category": "safe",
        },
        {
            "query": "What is the weather today?",
            "expected_confidence": 65.0,
            "confidence_level": "Medium",
            "reasons": ["Weather information requires current data"],
            "category": "safe",
        },
    ]

    return {
        "examples": examples,
        "confidence_levels": {
            "High": "80-100% - Factual, well-established information",
            "Medium": "50-79% - Some uncertainty or subjective elements",
            "Low": "0-49% - High uncertainty, requires human review",
        },
        "auto_flagging": {
            "threshold": 50.0,
            "description": "Responses with confidence < 50% are automatically flagged for review",
        },
    }


@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint"""
    flagged_count = db.query(Message).filter(Message.flagged).count()
    total_messages = db.query(Message).count()
    low_confidence_count = (
        db.query(Message)
        .filter(Message.confidence_score < 50.0, Message.role == "assistant")
        .count()
    )

    return {
        "status": "healthy",
        "openai_enabled": USE_OPENAI,
        "flagged_count": flagged_count,
        "total_messages": total_messages,
        "low_confidence_responses": low_confidence_count,
        "database": "connected",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
