// DOM Elements
const chatMessages = document.getElementById('chatMessages');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const clearChatBtn = document.getElementById('clearChatBtn');
const learningModeBtn = document.getElementById('learningModeBtn');
const warningBar = document.getElementById('warningBar');
const inputWarningBar = document.getElementById('inputWarningBar');
const inputWarningText = document.getElementById('inputWarningText');
const piiWarningBar = document.getElementById('piiWarningBar');
const piiWarningText = document.getElementById('piiWarningText');

// State
let learningMode = false;
let messageCount = 0;
let currentSessionId = null;  // Track session ID for conversation continuity
const API_BASE_URL = 'http://localhost:8000';

// Safety Filter Keywords (kept for frontend warning display)
const safetyKeywords = {
    medical: ["pain", "hurt", "fever", "doctor", "medicine", "sick", "headache"],
    financial: ["invest", "money", "bitcoin", "stock", "credit card", "loan"],
    legal: ["lawyer", "legal", "sue", "contract", "illegal"],
    crisis: ["suicide", "depressed", "kill myself", "end my life", "hopeless"]
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Load session_id from localStorage if available
    const savedSessionId = localStorage.getItem('aiSafetyChatSessionId');
    if (savedSessionId) {
        currentSessionId = savedSessionId;
    }
    
    // Focus input on load
    messageInput.focus();
    
    // Add click handlers for hint examples
    const hintExamples = document.querySelectorAll('.hint-example');
    hintExamples.forEach(example => {
        example.addEventListener('click', () => {
            messageInput.value = example.textContent.replace(/"/g, '');
            messageInput.focus();
        });
    });
});

// Safety Filter Function
function checkSafetyFilter(message) {
    const lowerMessage = message.toLowerCase();
    const detectedCategories = [];
    
    // Check each category
    for (const [category, keywords] of Object.entries(safetyKeywords)) {
        for (const keyword of keywords) {
            if (lowerMessage.includes(keyword.toLowerCase())) {
                if (!detectedCategories.includes(category)) {
                    detectedCategories.push(category);
                }
            }
        }
    }
    
    return detectedCategories.length > 0 ? detectedCategories[0] : null;
}

// Log Safety Event
function logSafetyEvent(userMessage, category, action) {
    const timestamp = new Date().toISOString();
    const logEntry = {
        timestamp,
        userMessage,
        detectedCategory: category || 'None',
        actionTaken: action
    };
    
    // Safety filter check (for frontend warning display)
    return logEntry;
}

// Show Input Warning Bar
function showInputWarning(category) {
    const categoryNames = {
        medical: 'Medical',
        financial: 'Financial',
        legal: 'Legal',
        crisis: 'Crisis'
    };
    
    const categoryName = categoryNames[category] || category;
    inputWarningText.textContent = `⚠️ This message contains ${categoryName} content. It will be reviewed for safety.`;
    inputWarningBar.classList.remove('hidden');
}

// Hide Input Warning Bar
function hideInputWarning() {
    inputWarningBar.classList.add('hidden');
}

// Show PII Warning Bar
function showPIIWarning(message) {
    piiWarningText.textContent = message;
    piiWarningBar.classList.remove('hidden');
}

// Hide PII Warning Bar
function hidePIIWarning() {
    piiWarningBar.classList.add('hidden');
}

// Send Message
async function sendMessage() {
    const messageText = messageInput.value.trim();
    
    if (!messageText) {
        return;
    }

    // Add user message immediately
    addMessage(messageText, 'user', false);
    messageInput.value = '';
    messageInput.focus();
    
    // Show typing indicator
    showTypingIndicator();
    
    try {
        // Prepare request with all settings
        const requestBody = {
            message: messageText,
            learning_mode: userSettings.learning_mode || learningMode,
            settings: userSettings,
            session_id: currentSessionId  // Send existing session_id to continue conversation
        };
        
        // Send request with user settings
        
        // Call backend API
        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Store session_id from response to maintain conversation continuity
        if (data.session_id) {
            currentSessionId = data.session_id;
            localStorage.setItem('aiSafetyChatSessionId', currentSessionId);
        }
        
        // Remove typing indicator
        removeTypingIndicator();
        
        // Handle safety metadata from backend
        const isRisky = data.flagged;
        const detectedCategory = data.category !== 'safe' ? data.category : null;
        
        // Show warning if risky content detected
        if (isRisky) {
            showInputWarning(detectedCategory);
            logSafetyEvent(messageText, detectedCategory, `Backend flagged: ${data.message_for_moderator}`);
            
            // Auto-hide warning after 5 seconds
            setTimeout(() => {
                hideInputWarning();
            }, 5000);
        } else {
            hideInputWarning();
            logSafetyEvent(messageText, null, 'No safety concerns detected by backend');
        }
        
        // Show PII warning if personal information was detected
        if (data.pii_warning) {
            showPIIWarning(data.pii_warning);
            logSafetyEvent(messageText, 'PII', 'Personal information detected and redacted');
            
            // Auto-hide PII warning after 7 seconds
            setTimeout(() => {
                hidePIIWarning();
            }, 7000);
        }
        
        // Guardrail explanation is displayed in UI if transparency is enabled
        
        // Add AI response with metadata and confidence
        // Ensure we use the actual backend confidence data
        const confidenceScore = data.confidence_score !== null && data.confidence_score !== undefined 
            ? parseFloat(data.confidence_score) 
            : null;
        const confidenceLevel = data.confidence_level || null;
        const confidenceReasons = data.confidence_reasons || [];
        
        // Confidence data extracted from response
        
        // Learning analysis data extracted from response
        addMessage(
            data.response, 
            'ai', 
            isRisky, 
            detectedCategory,
            confidenceScore,
            confidenceLevel,
            confidenceReasons,
            data.learning_analysis  // Pass learning analysis
        );
        
    } catch (error) {
        // Fallback to mock response if backend is unavailable
        console.error('Backend error, using fallback:', error);
        removeTypingIndicator();
        
        // Use frontend safety filter as fallback
        const detectedCategory = checkSafetyFilter(messageText);
        const isRisky = detectedCategory !== null;
        
        if (isRisky) {
            showInputWarning(detectedCategory);
            logSafetyEvent(messageText, detectedCategory, 'Warning displayed (fallback mode)');
            setTimeout(() => {
                hideInputWarning();
            }, 5000);
        }
        
        // Generate mock response (with calculated confidence for fallback mode)
        const aiResponse = generateAIResponse(messageText, isRisky, detectedCategory);
        
        // Calculate confidence based on query type (similar to backend logic)
        let defaultConfidence = 70.0;
        let defaultLevel = 'Medium';
        const lowerMessage = messageText.toLowerCase();
        
        // 100% confidence for certain facts
        if (lowerMessage.includes('2+2') || lowerMessage.includes('2 + 2') ||
            lowerMessage.includes('3*3') || lowerMessage.includes('3 * 3') || lowerMessage.includes('3 times 3') ||
            lowerMessage.includes('10-5') || lowerMessage.includes('10 - 5') ||
            (lowerMessage.includes('capital') && lowerMessage.includes('france')) ||
            (lowerMessage.includes('capital') && lowerMessage.includes('japan')) ||
            lowerMessage.includes('water boils') || lowerMessage.includes('earth orbits')) {
            defaultConfidence = 100.0;
            defaultLevel = 'High';
        }
        // High confidence for educational topics
        else if (lowerMessage.includes('explain') && (lowerMessage.includes('photosynthesis') || lowerMessage.includes('gravity'))) {
            defaultConfidence = 95.0;
            defaultLevel = 'High';
        }
        // Low confidence for advice/predictions
        else if (lowerMessage.includes('should i') || lowerMessage.includes('will') || 
                 lowerMessage.includes('invest') || lowerMessage.includes('predict')) {
            defaultConfidence = 35.0;
            defaultLevel = 'Low';
        }
        // Medium confidence for weather
        else if (lowerMessage.includes('weather')) {
            defaultConfidence = 65.0;
            defaultLevel = 'Medium';
        }
        // Default based on risk
        else {
            defaultConfidence = isRisky ? 50.0 : 75.0;
            defaultLevel = defaultConfidence >= 80 ? 'High' : defaultConfidence >= 50 ? 'Medium' : 'Low';
        }
        
        addMessage(aiResponse, 'ai', isRisky, detectedCategory, defaultConfidence, defaultLevel, [], null);
    }
}

// Add Message to Chat
function addMessage(text, sender, isRisky = false, detectedCategory = null, confidenceScore = null, confidenceLevel = null, confidenceReasons = [], learningAnalysis = null) {
    messageCount++;
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}-message`;
    
    const avatarIcon = sender === 'user' ? 'fa-user' : 'fa-robot';
    const senderName = sender === 'user' ? 'You' : 'AI Assistant';
    const currentTime = new Date().toLocaleTimeString('en-US', { 
        hour: '2-digit', 
        minute: '2-digit' 
    });
    
    // Add safety checked badge for AI messages in learning mode if risky
    let safetyBadge = '';
    if (sender === 'ai' && learningMode && isRisky) {
        safetyBadge = '<span class="safety-checked-badge">(Safety Checked)</span>';
    }
    
    // Add confidence badge for AI messages
    let confidenceBadge = '';
    if (sender === 'ai') {
        // Use actual backend confidence data - only fallback if truly missing
        if (confidenceScore !== null && confidenceScore !== undefined && confidenceLevel) {
            // Use real backend data
            const score = parseFloat(confidenceScore);
            const level = confidenceLevel; // Use the exact level from backend
            const confidenceEmoji = level === 'High' ? '🟢' : level === 'Medium' ? '🟡' : '🔴';
            confidenceBadge = `<span class="confidence-badge confidence-${level.toLowerCase()}">${confidenceEmoji} ${level} (${Math.round(score)}%)</span>`;
        } else {
            // Only use fallback if backend data is completely missing (for backward compatibility)
            console.warn('Missing confidence data, using fallback');
            const score = 75.0;
            const level = 'Medium';
            const confidenceEmoji = '🟡';
            confidenceBadge = `<span class="confidence-badge confidence-${level.toLowerCase()}">${confidenceEmoji} ${level} (${Math.round(score)}%)</span>`;
        }
    }
    
    // Add learning mode analysis for AI messages
    let learningModeNote = '';
    if (sender === 'ai' && learningMode && learningAnalysis) {
        learningModeNote = buildLearningAnalysisHTML(learningAnalysis);
    } else if (sender === 'ai' && learningMode && !learningAnalysis) {
        // Fallback for when backend doesn't return learning_analysis
        let noteContent = '🔍 Learning Mode: Analysis unavailable.';
        if (isRisky && detectedCategory) {
            const categoryNames = {
                medical: 'Medical',
                financial: 'Financial',
                legal: 'Legal',
                crisis: 'Crisis'
            };
            const categoryName = categoryNames[detectedCategory] || detectedCategory;
            noteContent = `🔍 Learning Mode: ${categoryName} keywords detected. This would be flagged for human review in production.`;
        }
        learningModeNote = `
            <div class="learning-mode-note">
                <i class="fas fa-search"></i>
                <span>${noteContent}</span>
            </div>
        `;
    }
    
    messageDiv.innerHTML = `
        <div class="message-avatar">
            <i class="fas ${avatarIcon}"></i>
        </div>
        <div class="message-content">
            <div class="message-header">
                <span class="message-sender">${senderName}${safetyBadge}${confidenceBadge}</span>
                <span class="message-time">${currentTime}</span>
            </div>
            <div class="message-text">${escapeHtml(text)}</div>
            ${learningModeNote}
        </div>
    `;
    
    chatMessages.appendChild(messageDiv);
    
    // Initialize collapsible sections for learning analysis
    if (learningModeNote && sender === 'ai') {
        initializeCollapsibleSections(messageDiv);
    }
    
    scrollToBottom();
}

// Show Typing Indicator
function showTypingIndicator() {
    const typingDiv = document.createElement('div');
    typingDiv.className = 'message ai-message typing-message';
    typingDiv.id = 'typingIndicator';
    typingDiv.innerHTML = `
        <div class="message-avatar">
            <i class="fas fa-robot"></i>
        </div>
        <div class="message-content">
            <div class="message-header">
                <span class="message-sender">AI Assistant</span>
            </div>
            <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;
    
    chatMessages.appendChild(typingDiv);
    scrollToBottom();
}

// Remove Typing Indicator
function removeTypingIndicator() {
    const typingIndicator = document.getElementById('typingIndicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
}

// Generate AI Response (Mock)
function generateAIResponse(userMessage, isRisky = false, detectedCategory = null) {
    const lowerMessage = userMessage.toLowerCase();
    
    // Different responses for risky vs safe content
    if (isRisky) {
        // Risky content responses - more cautious and educational
        const riskyResponses = {
            medical: `I understand you mentioned medical-related topics. In a production AI system, medical queries would typically be flagged for review to ensure accurate, safe information. This educational system demonstrates how such content is identified and would be handled with appropriate guardrails and potentially human medical professional oversight.`,
            financial: `I notice financial-related keywords in your message. Financial advice requires careful consideration and often regulatory compliance. In production systems, such queries would be flagged for review to ensure responsible handling. This demonstrates how AI safety systems identify and manage sensitive financial content.`,
            legal: `Your message contains legal-related terms. Legal matters often require professional expertise and careful handling. In a production AI system, legal queries would be flagged for review to ensure appropriate responses. This educational system shows how such content is identified for safety oversight.`,
            crisis: `I detect content that may relate to crisis situations. In production systems, crisis-related content is immediately flagged for human review and appropriate support resources. This educational demonstration shows how AI safety systems identify such critical content. If you're experiencing a crisis, please reach out to professional support services.`
        };
        
        if (detectedCategory && riskyResponses[detectedCategory]) {
            return riskyResponses[detectedCategory];
        }
        
        // Generic risky response
        return `I've detected content that may require special handling. In a production AI safety system, this type of query would be flagged for human review to ensure appropriate, responsible responses. This educational system demonstrates how guardrails identify and manage potentially sensitive content.`;
    }
    
    // Safe content responses - original logic
    if (lowerMessage.includes('safety') || lowerMessage.includes('guardrail')) {
        return `Great question! AI safety involves implementing guardrails to ensure AI systems behave responsibly. This includes content filtering, bias detection, and human oversight mechanisms. In this educational system, we're demonstrating how such guardrails can work in practice.`;
    }
    
    if (lowerMessage.includes('bias') || lowerMessage.includes('fair')) {
        return `Bias in AI is a critical safety concern. AI systems can perpetuate or amplify biases present in training data. Safety measures include diverse datasets, fairness audits, and continuous monitoring. This is why human-in-the-loop oversight is essential.`;
    }
    
    if (lowerMessage.includes('risk') || lowerMessage.includes('danger')) {
        return `AI risks can include misinformation, privacy violations, and unintended harmful outputs. Safety systems use multiple layers: input validation, output filtering, and human review processes. Education about these risks is the first step toward safer AI.`;
    }
    
    if (lowerMessage.includes('learn') || lowerMessage.includes('education')) {
        return `Learning about AI safety is crucial! Understanding how guardrails work, recognizing potential risks, and knowing when human oversight is needed are all part of responsible AI use. This educational system helps demonstrate these concepts.`;
    }
    
    if (lowerMessage.includes('hello') || lowerMessage.includes('hi') || lowerMessage.includes('hey')) {
        return `Hello! I'm here to help you learn about AI safety. Feel free to ask me about guardrails, bias, risks, or any other AI safety topics. Remember, this is an educational demonstration.`;
    }
    
    // Default safe response
    const safeResponses = [
        `That's an interesting point about "${userMessage}". From an AI safety perspective, it's important to consider how AI systems handle such queries responsibly. This educational system demonstrates guardrails that help ensure appropriate responses.`,
        `Regarding "${userMessage}" - AI safety involves carefully evaluating inputs and outputs. In a production system, this would involve multiple safety checks and potentially human review for sensitive topics.`,
        `Good question! When discussing "${userMessage}", we must consider AI safety principles: transparency, accountability, and appropriate guardrails. This educational chatbot demonstrates how such systems can be designed with safety in mind.`
    ];
    
    return safeResponses[Math.floor(Math.random() * safeResponses.length)];
}

// Toggle Learning Mode
learningModeBtn.addEventListener('click', () => {
    learningMode = !learningMode;
    userSettings.learning_mode = learningMode;
    saveSettings();
    
    // Sync with settings modal toggle
    const learningToggle = document.getElementById('learningModeToggle');
    if (learningToggle) {
        learningToggle.checked = learningMode;
    }
    
    const span = learningModeBtn.querySelector('span');
    if (learningMode) {
        learningModeBtn.classList.add('active');
        span.textContent = '🎓 Learning Mode: ON';
    } else {
        learningModeBtn.classList.remove('active');
        span.textContent = '🎓 Learning Mode: OFF';
    }
    // Learning mode toggled
});

// Clear Chat
clearChatBtn.addEventListener('click', () => {
    if (confirm('Are you sure you want to clear the chat?')) {
        // Keep only the initial welcome message
        const welcomeMessage = chatMessages.querySelector('.message.ai-message');
        chatMessages.innerHTML = '';
        if (welcomeMessage) {
            chatMessages.appendChild(welcomeMessage);
        }
        messageCount = 0;
        
        // Reset session_id to start a new conversation
        currentSessionId = null;
        localStorage.removeItem('aiSafetyChatSessionId');
        
        scrollToBottom();
    }
});

// Send Button Click
sendBtn.addEventListener('click', sendMessage);

// Enter Key Press
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// Scroll to Bottom
function scrollToBottom() {
    chatMessages.scrollTo({
        top: chatMessages.scrollHeight,
        behavior: 'smooth'
    });
}

// Build Learning Analysis HTML with collapsible sections
function buildLearningAnalysisHTML(analysis) {
    if (!analysis) return '';
    
    const riskIcon = analysis.risk_category !== 'Safe' ? '⚠️' : '✅';
    const guardrailsHTML = analysis.triggered_guardrails.length > 0
        ? analysis.triggered_guardrails.map(g => `<li>${g}</li>`).join('')
        : '<li>No guardrails triggered</li>';
    
    const confidenceHTML = analysis.confidence_breakdown.length > 0
        ? analysis.confidence_breakdown.map(item => 
            `<li><strong>${item.factor}:</strong> <span class="impact-${item.impact.startsWith('+') ? 'positive' : item.impact.startsWith('-') ? 'negative' : 'neutral'}">${item.impact}</span></li>`
          ).join('')
        : '<li>No specific factors identified</li>';
    
    const tipsHTML = analysis.safety_tips.map(tip => `<li>${tip}</li>`).join('');
    
    const humanReviewHTML = analysis.human_review_reason
        ? `<div class="learning-section">
            <button class="learning-toggle" onclick="toggleLearningSection(this)">
                <i class="fas fa-user-shield"></i> Human Review Reason
                <i class="fas fa-chevron-down"></i>
            </button>
            <div class="learning-content">
                <p>${escapeHtml(analysis.human_review_reason)}</p>
            </div>
        </div>`
        : '';
    
    // Context Analysis Section
    let contextHTML = '';
    if (analysis.context_analysis) {
        const ctx = analysis.context_analysis;
        const contextFlags = ctx.context_flags && ctx.context_flags.length > 0
            ? ctx.context_flags.map(flag => `<li>${escapeHtml(flag)}</li>`).join('')
            : '<li>No context flags detected</li>';
        
        const previousQueries = ctx.previous_queries && ctx.previous_queries.length > 0
            ? ctx.previous_queries.slice(-3).map((q, idx) => {
                const cat = q.category ? ` (${q.category})` : '';
                return `<li>${escapeHtml(q.content.substring(0, 60))}${cat ? cat : ''}...</li>`;
              }).join('')
            : '<li>No previous queries</li>';
        
        contextHTML = `
            <div class="learning-section">
                <button class="learning-toggle" onclick="toggleLearningSection(this)">
                    <i class="fas fa-history"></i> Conversation Context Analysis
                    <i class="fas fa-chevron-down"></i>
                </button>
                <div class="learning-content">
                    <div style="margin-bottom: 12px;">
                        <strong>Context Flags:</strong>
                        <ul>${contextFlags}</ul>
                    </div>
                    <div style="margin-bottom: 12px;">
                        <strong>Risk Indicators:</strong>
                        <ul>
                            <li>Risk Escalation: ${ctx.risk_escalation ? '⚠️ Yes' : '✅ No'}</li>
                            <li>Filter Bypass Attempt: ${ctx.filter_bypass_attempt ? '⚠️ Yes' : '✅ No'}</li>
                            <li>Persistent Sensitive Topic: ${ctx.persistent_sensitive_topic ? '⚠️ Yes' : '✅ No'}</li>
                            <li>Cumulative Risk Score: ${(ctx.cumulative_risk_score * 100).toFixed(0)}%</li>
                        </ul>
                    </div>
                    <div>
                        <strong>Recent Queries:</strong>
                        <ul>${previousQueries}</ul>
                    </div>
                </div>
            </div>
        `;
    }
    
    return `
        <div class="learning-mode-analysis">
            <div class="learning-header">
                <i class="fas fa-graduation-cap"></i>
                <strong>Learning Mode Analysis</strong>
            </div>
            
            <div class="learning-section">
                <button class="learning-toggle" onclick="toggleLearningSection(this)">
                    ${riskIcon} Risk Category: ${escapeHtml(analysis.risk_category)}
                    <i class="fas fa-chevron-down"></i>
                </button>
                <div class="learning-content">
                    <p>The query was categorized as <strong>${escapeHtml(analysis.risk_category)}</strong> based on content analysis.</p>
                </div>
            </div>
            
            <div class="learning-section">
                <button class="learning-toggle" onclick="toggleLearningSection(this)">
                    <i class="fas fa-shield-alt"></i> Triggered Guardrails
                    <i class="fas fa-chevron-down"></i>
                </button>
                <div class="learning-content">
                    <ul>${guardrailsHTML}</ul>
                </div>
            </div>
            
            <div class="learning-section">
                <button class="learning-toggle" onclick="toggleLearningSection(this)">
                    <i class="fas fa-chart-line"></i> Confidence Breakdown
                    <i class="fas fa-chevron-down"></i>
                </button>
                <div class="learning-content">
                    <ul>${confidenceHTML}</ul>
                </div>
            </div>
            
            <div class="learning-section">
                <button class="learning-toggle" onclick="toggleLearningSection(this)">
                    <i class="fas fa-lightbulb"></i> Safety Tips
                    <i class="fas fa-chevron-down"></i>
                </button>
                <div class="learning-content">
                    <ul>${tipsHTML}</ul>
                </div>
            </div>
            
            ${humanReviewHTML}
            ${contextHTML}
        </div>
    `;
}

// Toggle collapsible learning sections (global function for onclick handlers)
window.toggleLearningSection = function(button) {
    const content = button.nextElementSibling;
    const icon = button.querySelector('.fa-chevron-down, .fa-chevron-up');
    
    if (!icon) return;
    
    if (content.style.display === 'none' || !content.style.display) {
        content.style.display = 'block';
        if (icon.classList.contains('fa-chevron-down')) {
            icon.classList.remove('fa-chevron-down');
            icon.classList.add('fa-chevron-up');
        }
    } else {
        content.style.display = 'none';
        if (icon.classList.contains('fa-chevron-up')) {
            icon.classList.remove('fa-chevron-up');
            icon.classList.add('fa-chevron-down');
        }
    }
};

// Initialize collapsible sections (all collapsed by default)
function initializeCollapsibleSections(messageDiv) {
    const sections = messageDiv.querySelectorAll('.learning-content');
    sections.forEach(section => {
        section.style.display = 'none';
    });
}

// User Settings
let userSettings = {
    safety_level: 'moderate',
    transparency: true,
    learning_mode: false,
    data_logging: false,
    response_speed: 'balanced'
};

// Load settings from localStorage
function loadSettings() {
    const saved = localStorage.getItem('aiSafetyChatSettings');
    if (saved) {
        try {
            userSettings = { ...userSettings, ...JSON.parse(saved) };
            applySettingsToUI();
        } catch (e) {
            console.error('Error loading settings:', e);
        }
    }
}

// Save settings to localStorage
function saveSettings() {
    localStorage.setItem('aiSafetyChatSettings', JSON.stringify(userSettings));
    // Settings saved to localStorage
}

// Apply settings to UI
function applySettingsToUI() {
    document.getElementById('safetyLevel').value = userSettings.safety_level;
    document.getElementById('transparencyToggle').checked = userSettings.transparency;
    document.getElementById('learningModeToggle').checked = userSettings.learning_mode;
    document.getElementById('dataLoggingToggle').checked = userSettings.data_logging;
    
    // Set response speed dropdown
    document.getElementById('responseSpeed').value = userSettings.response_speed || 'balanced';
    
    // Sync learning mode button with settings
    learningMode = userSettings.learning_mode;
    const learningBtn = document.getElementById('learningModeBtn');
    const span = learningBtn.querySelector('span');
    if (learningMode) {
        learningBtn.classList.add('active');
        span.textContent = '🎓 Learning Mode: ON';
    } else {
        learningBtn.classList.remove('active');
        span.textContent = '🎓 Learning Mode: OFF';
    }
}

// Get settings from UI
function getSettingsFromUI() {
    return {
        safety_level: document.getElementById('safetyLevel').value,
        transparency: document.getElementById('transparencyToggle').checked,
        learning_mode: document.getElementById('learningModeToggle').checked,
        data_logging: document.getElementById('dataLoggingToggle').checked,
        response_speed: document.getElementById('responseSpeed').value || 'balanced'
    };
}

// Settings Modal Elements
const settingsBtn = document.getElementById('settingsBtn');
const settingsModal = document.getElementById('settingsModal');
const closeSettingsBtn = document.getElementById('closeSettingsBtn');
const saveSettingsBtn = document.getElementById('saveSettingsBtn');
const resetSettingsBtn = document.getElementById('resetSettingsBtn');

// Open Settings Modal
settingsBtn.addEventListener('click', () => {
    settingsModal.classList.remove('hidden');
    applySettingsToUI();
});

// Close Settings Modal
closeSettingsBtn.addEventListener('click', () => {
    settingsModal.classList.add('hidden');
});

// Close modal when clicking outside
settingsModal.addEventListener('click', (e) => {
    if (e.target === settingsModal) {
        settingsModal.classList.add('hidden');
    }
});

// Save Settings
saveSettingsBtn.addEventListener('click', () => {
    userSettings = getSettingsFromUI();
    saveSettings();
    
    // Sync learning mode
    learningMode = userSettings.learning_mode;
    const learningBtn = document.getElementById('learningModeBtn');
    const span = learningBtn.querySelector('span');
    if (learningMode) {
        learningBtn.classList.add('active');
        span.textContent = '🎓 Learning Mode: ON';
    } else {
        learningBtn.classList.remove('active');
        span.textContent = '🎓 Learning Mode: OFF';
    }
    
    // Show confirmation
    const originalText = saveSettingsBtn.innerHTML;
    saveSettingsBtn.innerHTML = '<i class="fas fa-check"></i> Saved!';
    saveSettingsBtn.style.background = 'rgba(16, 185, 129, 0.8)';
    
    setTimeout(() => {
        saveSettingsBtn.innerHTML = originalText;
        saveSettingsBtn.style.background = '';
    }, 2000);
    
    // Close modal after a brief delay
    setTimeout(() => {
        settingsModal.classList.add('hidden');
    }, 500);
});

// Reset Settings
resetSettingsBtn.addEventListener('click', () => {
    if (confirm('Reset all settings to defaults?')) {
        userSettings = {
            safety_level: 'moderate',
            transparency: true,
            learning_mode: false,
            data_logging: false,
            response_speed: 'balanced'
        };
        applySettingsToUI();
        saveSettings();
    }
});

// Sync learning mode toggle with settings
document.getElementById('learningModeToggle').addEventListener('change', (e) => {
    userSettings.learning_mode = e.target.checked;
});

// Load settings on page load
loadSettings();

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
