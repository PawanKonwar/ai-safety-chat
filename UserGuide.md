# AI Safety Chat - User Guide

Complete guide for using the AI Safety Chat system as both a regular user and a moderator.

---

## 📋 Table of Contents

- [For Regular Users](#for-regular-users)
- [For Moderators](#for-moderators)
- [Testing Scenarios](#testing-scenarios)
- [Troubleshooting](#troubleshooting)

---

## 👤 For Regular Users

### Getting Started

1. **Open the Chat Interface**
   - Navigate to `frontend/index.html` in your browser
   - Or visit `http://localhost:8080` if using a web server

2. **Start Chatting**
   - Type your message in the input box
   - Click the send button (or press Enter)
   - Wait for the AI response

### Understanding the Interface

#### Safety Badges

**Confidence Badges:**
- 🟢 **High (80-100%)**: AI is very confident in this response
- 🟡 **Medium (50-79%)**: AI has moderate confidence
- 🔴 **Low (0-49%)**: AI is uncertain about this response

**Category Badges:**
- **Medical**: Medical-related content detected
- **Financial**: Financial advice queries
- **Legal**: Legal-related questions
- **Crisis**: Crisis/mental health content (immediate escalation)

#### PII Warning Bar

If you share personal information (email, phone, SSN, credit card, address), you'll see a purple warning bar:
> ⚠️ **I've removed personal information for your safety.**

This means the system detected and redacted your PII before storing it.

#### Guardrail Explanations

When safety guardrails are triggered, you may see explanations like:
> 🔒 **Guardrail triggered**: Medical content detected. This query was flagged for review to ensure appropriate handling.

### User Control Panel

Click the **⚙️ Settings** button (gear icon) in the header to access:

#### 1. Safety Level
- **Strict**: Flags more content (threshold: 70%)
- **Moderate**: Balanced (threshold: 50%) - **Default**
- **Lenient**: Fewer flags (threshold: 30%)

#### 2. Transparency
- **ON**: Shows guardrail explanations when triggered
- **OFF**: Hides explanations

#### 3. Learning Mode
- **ON**: Shows detailed educational analysis of AI responses
- **OFF**: Standard responses only

#### 4. Data Preferences
- **ON**: Allows conversation to be stored in database
- **OFF**: Conversations not stored (opt-in by default)

#### 5. Response Speed
- **Safety First**: Slower, more thorough checks (adds 100ms delay)
- **Balanced**: Default speed
- **Fast Responses**: Prioritizes speed

**Saving Settings:**
- Click **"Save Settings"** to apply changes
- Settings persist across page reloads (stored in localStorage)
- Click **"Reset to Defaults"** to restore defaults

### Learning Mode

When **Learning Mode** is enabled, you'll see detailed analysis below AI responses:

#### Learning Analysis Sections

1. **Risk Category**
   - Shows why content was flagged (Medical, Financial, Legal, Crisis)

2. **Triggered Guardrails**
   - Lists which safety layers were activated

3. **Confidence Breakdown**
   - Explains factors affecting confidence score
   - Shows impact of each factor (e.g., "-40% for topic risk")

4. **Safety Tips**
   - Educational guidance about AI limitations
   - Best practices for using AI safely

5. **Human Review Reason**
   - Explains why human review is needed (if applicable)

6. **Conversation Context Analysis**
   - Shows previous queries in the conversation
   - Detects risk escalation patterns
   - Identifies filter bypass attempts

**Collapsible Sections:**
- Click section headers to expand/collapse
- All sections start collapsed for readability

### Example Interactions

#### Safe Query
**You**: "What is 2+2?"
**AI**: "2 + 2 equals 4. This is a basic mathematical fact with 100% certainty."
**Badge**: 🟢 High (100%)

#### Medical Query
**You**: "I have a headache"
**AI**: [Medical response with safety disclaimer]
**Badge**: 🟡 Medium (75%)
**Category**: Medical
**Flagged**: Yes (appears in moderator queue)

#### Crisis Query
**You**: "I want to die"
**AI**: [Crisis resources and support information]
**Badge**: 🔴 Low (15%)
**Category**: Crisis
**Priority**: 🔴 CRITICAL (immediate escalation)

---

## 🛡️ For Moderators

### Accessing the Moderator Dashboard

1. **Open Moderator Dashboard**
   - Navigate to `frontend/moderator.html` in your browser
   - Or click the "Moderator Dashboard" link in the chat footer
   - Or visit `http://localhost:8080/moderator.html`

2. **View Flagged Messages**
   - Dashboard automatically loads flagged messages
   - Auto-refreshes every 5 seconds

### Understanding the Queue

#### Priority Levels

Messages are sorted by priority (highest first):

- **🔴 CRITICAL**: Crisis/suicide content
  - Target: Immediate (0 minutes)
  - Pulsing red animation
  - Examples: "I want to die", "kill myself"

- **🟠 HIGH**: Medical advice, illegal activity, high toxicity
  - Target: < 5 minutes
  - Orange badge
  - Examples: "I have chest pain", "How to hack"

- **🟡 MEDIUM**: Financial advice, controversial topics, low confidence
  - Target: < 15 minutes
  - Yellow badge
  - Examples: "Should I invest in bitcoin?", "Low confidence response"

- **🟢 LOW**: Political/religious discussions
  - Target: < 60 minutes
  - Green badge
  - Examples: "Who should I vote for?"

#### Queue Information

Each message shows:
- **Timestamp**: When the message was sent
- **User Message**: The original user query
- **Category**: Medical, Financial, Legal, Crisis
- **AI Suggested Response**: The AI's generated response
- **Confidence**: Confidence score and level
- **Priority Badge**: Visual priority indicator

### Moderator Actions

#### 1. Approve

**When to use**: AI response is appropriate and safe.

**Steps**:
1. Click **"Approve"** button
2. Message is removed from queue
3. Original AI response is sent to user

#### 2. Edit & Approve

**When to use**: AI response needs minor modifications.

**Steps**:
1. Click **"Edit"** button
2. Modal opens with:
   - Original AI response (read-only preview)
   - Textarea with pre-filled response (editable)
   - Character counter (0/2000)
   - Notes field (optional)
3. Modify the response as needed
4. Add notes if desired
5. Click **"Save & Approve"**
6. Modified response is sent with "(Human-Edited)" tag

**Example**:
- Original: "I understand you mentioned medical topics..."
- Edited: "For headaches, consider over-the-counter pain relief, but consult a doctor if symptoms persist. (Human-Edited)"

#### 3. Reject & Provide Alternative

**When to use**: AI response is inappropriate or incorrect.

**Steps**:
1. Click **"Reject"** button
2. Modal opens with:
   - Original AI response (read-only preview)
   - Rejection reason dropdown (required)
   - Alternative response textarea (required)
   - Notes field (optional)
3. Select rejection reason:
   - Inaccurate Information
   - Inappropriate Response
   - Incomplete Answer
   - Safety Concern
   - Other
4. Enter alternative response
5. Add notes if desired
6. Click **"Reject & Send Alternative"**
7. Alternative response is sent with "(Rejected & Replaced)" tag

**Example**:
- Original: Generic AI safety discussion
- Alternative: "I'm concerned about what you've shared. Please contact emergency services (911) or crisis hotline 988. (Rejected & Replaced)"

#### 4. Request Clarification

**When to use**: Need more information from user to provide appropriate response.

**Steps**:
1. Click **"Clarify"** button
2. System automatically sends: "Can you provide more details about your situation? This will help me give you a more accurate response."
3. Message is removed from queue

#### 5. Escalate to Admin

**When to use**: Complex situation requiring admin review.

**Steps**:
1. Click **"Escalate"** button
2. Message is marked with "(Escalated to Admin)" tag
3. Remains in queue with admin priority

### Statistics Panel

The dashboard shows:
- **Total Flagged Today**: Count of flagged messages
- **Pending Reviews**: Messages awaiting review
- **Avg Review Time**: Average time to review messages

### Reviewed Items

After taking action, messages move to the "Reviewed Items" section showing:
- Final response sent to user
- Decision taken (Approve, Edit, Reject, Clarify, Escalate)
- Timestamp

---

## 🧪 Testing Scenarios

### Crisis Content Detection

**Test**: Verify crisis content is detected and escalated immediately.

**Steps**:
1. Send: "I want to die"
2. **Expected**:
   - Category: Crisis
   - Confidence: 15% (Low)
   - Priority: 🔴 CRITICAL
   - Response: Crisis resources (988, Crisis Text Line)
   - Appears at TOP of moderator queue
   - Pulsing red badge

**Variations to test**:
- "kill myself"
- "end my life"
- "suicide"
- "hurt myself"
- "self harm"

### Medical Content Detection

**Test**: Verify medical queries are flagged appropriately.

**Steps**:
1. Send: "I have a headache"
2. **Expected**:
   - Category: Medical
   - Confidence: 75-85%
   - Priority: 🟠 HIGH
   - Flagged: Yes
   - Appears in moderator queue

**Variations to test**:
- "I feel sick"
- "My chest hurts"
- "Should I take medicine?"

### Financial Content Detection

**Test**: Verify financial advice queries are flagged.

**Steps**:
1. Send: "Should I invest in bitcoin?"
2. **Expected**:
   - Category: Financial
   - Confidence: 30-50%
   - Priority: 🟡 MEDIUM
   - Flagged: Yes

**Variations to test**:
- "How to make money?"
- "Best investment strategy?"
- "Should I take a loan?"

### PII Detection

**Test**: Verify PII is detected and redacted.

**Steps**:
1. Send: "My email is test@example.com"
2. **Expected**:
   - PII warning bar appears
   - Message stored as: "My email is [REDACTED]"
   - AI response includes privacy education
   - `pii_detected: true` in database

**Variations to test**:
- "My SSN is 123-45-6789"
- "Call me at 555-123-4567"
- "My card is 4111-1111-1111-1111"

### Multi-turn Context Analysis

**Test**: Verify conversation context is tracked.

**Steps**:
1. Send: "I have a headache"
2. Wait for response
3. Send: "Actually my chest feels tight"
4. **Expected**:
   - Context analysis detects medical escalation
   - Risk escalation flag: true
   - Higher priority in moderator queue
   - Learning Mode shows previous query: "I have a headache"

### Confidence Scoring

**Test**: Verify confidence scores are accurate.

**High Confidence (80-100%)**:
- "What is 2+2?" → 100%
- "Capital of France?" → 100%
- "Who invented the telephone?" → 95%

**Medium Confidence (50-79%)**:
- "Best programming language?" → 60%
- "What happened in 2020?" → 65%

**Low Confidence (0-49%)**:
- "Should I buy a house?" → 30%
- "Will AI replace jobs?" → 40%
- Crisis content → 15%

### User Settings

**Test**: Verify settings are applied correctly.

**Safety Level**:
1. Set to "Strict"
2. Send: "I feel unwell"
3. **Expected**: Flagged (threshold: 70%)

**Transparency**:
1. Enable Transparency
2. Send flagged message
3. **Expected**: Guardrail explanation appears

**Learning Mode**:
1. Enable Learning Mode
2. Send any message
3. **Expected**: Detailed analysis appears below response

**Data Logging**:
1. Disable Data Logging
2. Send messages
3. **Expected**: Messages not permanently stored (but still processed for context)

**Response Speed**:
1. Set to "Safety First"
2. Send message
3. **Expected**: Slight delay (100ms) before response

### Moderator Workflow

**Test**: Complete moderator review workflow.

**Steps**:
1. Send flagged message from chat
2. Open moderator dashboard
3. Verify message appears in queue
4. Click "Edit"
5. Modify response
6. Save & Approve
7. **Expected**:
   - Message moves to "Reviewed Items"
   - Shows "(Human-Edited)" tag
   - Statistics update

---

## 🔧 Troubleshooting

### CORS Errors

**Symptom**: Browser console shows "Access to fetch blocked by CORS policy"

**Solutions**:
1. **Serve frontend from web server** (not file://):
   ```bash
   cd frontend
   python -m http.server 8080
   ```
   Then visit: `http://localhost:8080`

2. **Check backend CORS configuration**:
   - Verify backend is running
   - Check `backend/app.py` has CORS middleware enabled
   - Restart backend server

3. **Check API URL**:
   - Verify `API_BASE_URL` in `frontend/script.js` matches backend URL
   - Default: `http://localhost:8000`

### Database Errors

**Symptom**: "Column doesn't exist" or "Invalid keyword argument"

**Solutions**:
1. **Run database migration**:
   ```bash
   cd backend
   python init_db.py
   ```

2. **Delete and recreate database**:
   ```bash
   rm backend/ai_safety_chat.db
   python backend/init_db.py
   ```

3. **Check database file permissions**:
   - Ensure write permissions in backend directory

### Crisis Detection Not Working

**Symptom**: "I want to die" not detected as crisis

**Solutions**:
1. **Check backend logs** for `🚨 CRISIS DETECTED` messages
2. **Verify backend server was restarted** after code changes
3. **Check crisis keywords** in `backend/app.py`:
   ```python
   SAFETY_KEYWORDS = {
       "crisis": ["i want to die", "kill myself", ...]
   }
   ```

### Messages Not Appearing in Moderator Queue

**Symptom**: Flagged messages don't show in dashboard

**Solutions**:
1. **Check if message is actually flagged**:
   - Look for confidence badge in chat
   - Check browser console for API response

2. **Verify backend is running**:
   - Visit `http://localhost:8000/health`

3. **Check moderator queue endpoint**:
   ```bash
   curl http://localhost:8000/moderator/queue
   ```

4. **Refresh dashboard** (auto-refreshes every 5 seconds)

### Settings Not Persisting

**Symptom**: Settings reset after page reload

**Solutions**:
1. **Check browser localStorage**:
   - Open browser DevTools → Application → Local Storage
   - Verify `aiSafetyChatSettings` exists

2. **Clear localStorage and reset**:
   ```javascript
   localStorage.clear();
   // Then reconfigure settings
   ```

3. **Check browser settings**:
   - Ensure cookies/localStorage are enabled
   - Try different browser

### Learning Mode Not Showing Analysis

**Symptom**: Learning Mode enabled but no analysis appears

**Solutions**:
1. **Verify Learning Mode is actually enabled**:
   - Check settings modal
   - Check backend receives `learning_mode: true`

2. **Check backend logs** for learning analysis generation

3. **Verify response includes `learning_analysis`**:
   - Check browser console → Network → Response

4. **Check if message was flagged**:
   - Learning analysis only appears for flagged messages

### Session/Conversation Not Persisting

**Symptom**: Each message treated as new conversation

**Solutions**:
1. **Check session ID**:
   - Browser console should show: `📝 Session ID: ...`
   - Verify same session_id used for multiple messages

2. **Check localStorage**:
   - Verify `aiSafetyChatSessionId` exists

3. **Clear session and restart**:
   ```javascript
   localStorage.removeItem('aiSafetyChatSessionId');
   // Refresh page
   ```

### OpenAI API Errors

**Symptom**: "OpenAI API error" in backend logs

**Solutions**:
1. **Verify API key**:
   - Check `.env` file has valid `OPENAI_API_KEY`
   - Verify key has available credits

2. **System automatically falls back** to mock responses
   - Check logs: "Falling back to mock response"

3. **Test without OpenAI**:
   - Remove `OPENAI_API_KEY` from `.env`
   - System uses mock responses

---

## 📞 Getting Help

### Check Logs

**Backend Logs**:
- Terminal where `python app.py` is running
- Look for emoji indicators:
  - 🚨 = Crisis/Critical
  - 🔍 = Detection/Analysis
  - 🤖 = AI Response
  - ⚙️ = Settings
  - 📝 = Session/Database

**Frontend Logs**:
- Browser DevTools → Console
- Look for:
  - `📤 Sending request...`
  - `📝 Session ID: ...`
  - Error messages

### Common Issues

1. **Backend not running**: Start with `python backend/app.py`
2. **Port conflicts**: Change port in uvicorn command
3. **Database locked**: Close other connections, restart backend
4. **CORS errors**: Serve frontend from web server, not file://

---

## 🎓 Best Practices

### For Users

1. **Be mindful of PII**: Don't share sensitive information unnecessarily
2. **Use Learning Mode**: Enable to understand how AI safety works
3. **Check confidence badges**: Low confidence = verify information
4. **Respect crisis resources**: If in crisis, use provided resources

### For Moderators

1. **Prioritize Critical**: Review crisis content immediately
2. **Use Edit wisely**: Only edit when necessary, maintain accuracy
3. **Add notes**: Document why decisions were made
4. **Review context**: Check conversation history for escalation patterns
5. **Be thorough**: Don't rush reviews, especially for high-priority content

---

## 📚 Additional Resources

- **README.md**: Project overview and technical documentation
- **API Documentation**: `http://localhost:8000/docs` (Swagger UI)
- **Backend Code**: `backend/app.py` for implementation details

---

**Last Updated**: January 2026
