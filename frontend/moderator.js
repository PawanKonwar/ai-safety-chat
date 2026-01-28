// State
let flaggedMessages = [];
let reviewedMessages = [];
let currentEditId = null;
let reviewStartTimes = {};
const API_BASE_URL = 'http://localhost:8000';

// Sample flagged messages for fallback demonstration
const sampleMessages = [
    {
        id: "msg_1",
        timestamp: new Date(Date.now() - 15 * 60000).toISOString(), // 15 minutes ago
        user_message: "I have a terrible headache and feel sick. Should I take medicine?",
        category: "medical",
        ai_response: "I understand you mentioned medical-related topics. In a production AI system, medical queries would typically be flagged for review to ensure accurate, safe information. This educational system demonstrates how such content is identified and would be handled with appropriate guardrails and potentially human medical professional oversight.",
        confidence: 0.85
    },
    {
        id: "msg_2",
        timestamp: new Date(Date.now() - 45 * 60000).toISOString(), // 45 minutes ago
        user_message: "I want to invest in bitcoin and stocks. What should I do?",
        category: "financial",
        ai_response: "I notice financial-related keywords in your message. Financial advice requires careful consideration and often regulatory compliance. In production systems, such queries would be flagged for review to ensure responsible handling. This demonstrates how AI safety systems identify and manage sensitive financial content.",
        confidence: 0.80
    }
];

// Fetch flagged messages from backend
async function fetchFlaggedMessages() {
    try {
        const response = await fetch(`${API_BASE_URL}/moderator/queue`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        
        // Transform backend format to frontend format
        flaggedMessages = data.map(msg => ({
            id: msg.id,
            timestamp: msg.timestamp,
            userMessage: msg.user_message,
            category: msg.category,
            aiResponse: msg.ai_response,
            confidence: msg.confidence,
            confidence_score: msg.confidence_score !== null && msg.confidence_score !== undefined ? msg.confidence_score : 75.0, // Default for backward compatibility
            confidence_level: msg.confidence_level || (msg.confidence_score !== null && msg.confidence_score !== undefined 
                ? (msg.confidence_score >= 80 ? 'High' : msg.confidence_score >= 50 ? 'Medium' : 'Low')
                : 'Medium'),
            priority_level: msg.priority_level || 'low',
            escalation_reason: msg.escalation_reason || null,
            target_response_time: msg.target_response_time || 60
        }));
        
        // Initialize review start times for new messages
        flaggedMessages.forEach(msg => {
            if (!reviewStartTimes[msg.id]) {
                reviewStartTimes[msg.id] = Date.now();
            }
        });
        
        renderPendingTable();
        updateStats();
    } catch (error) {
        console.error('Error fetching flagged messages, using fallback:', error);
        // Fallback to sample messages if backend is unavailable
        flaggedMessages = sampleMessages.map(msg => ({
            id: msg.id,
            timestamp: new Date(msg.timestamp),
            userMessage: msg.user_message,
            category: msg.category,
            aiResponse: msg.ai_response,
            confidence: msg.confidence
        }));
        
        flaggedMessages.forEach(msg => {
            if (!reviewStartTimes[msg.id]) {
                reviewStartTimes[msg.id] = Date.now();
            }
        });
        
        renderPendingTable();
        updateStats();
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Fetch flagged messages from backend
    fetchFlaggedMessages();
    
    // Set up auto-refresh every 5 seconds
    setInterval(fetchFlaggedMessages, 5000);
    
    renderReviewedTable();
    updateStats();
    
    // Event listeners
    document.getElementById('simulateFlagBtn').addEventListener('click', simulateNewFlag);
    
    // Edit modal
    document.getElementById('closeEditModalBtn').addEventListener('click', closeEditModal);
    document.getElementById('cancelEditBtn').addEventListener('click', closeEditModal);
    document.getElementById('saveEditBtn').addEventListener('click', saveEdit);
    document.getElementById('editTextarea').addEventListener('input', () => updateCharCount('editTextarea', 'editCharCount'));
    document.getElementById('editModal').addEventListener('click', (e) => {
        if (e.target.id === 'editModal') {
            closeEditModal();
        }
    });
    
    // Reject modal
    document.getElementById('closeRejectModalBtn').addEventListener('click', closeRejectModal);
    document.getElementById('cancelRejectBtn').addEventListener('click', closeRejectModal);
    document.getElementById('saveRejectBtn').addEventListener('click', saveReject);
    document.getElementById('rejectTextarea').addEventListener('input', () => updateCharCount('rejectTextarea', 'rejectCharCount'));
    document.getElementById('rejectModal').addEventListener('click', (e) => {
        if (e.target.id === 'rejectModal') {
            closeRejectModal();
        }
    });
});

// Render Pending Table
function renderPendingTable() {
    const tbody = document.getElementById('pendingTableBody');
    const noPending = document.getElementById('noPending');
    
    if (flaggedMessages.length === 0) {
        tbody.innerHTML = '';
        noPending.classList.remove('hidden');
        return;
    }
    
    noPending.classList.add('hidden');
    tbody.innerHTML = flaggedMessages.map(msg => {
        const timeStr = formatTime(new Date(msg.timestamp));
        const categoryClass = `category-${msg.category}`;
        
        // Add confidence badge
        let confidenceBadge = '';
        if (msg.confidence_score !== null && msg.confidence_score !== undefined) {
            const confidenceEmoji = msg.confidence_level === 'High' ? '🟢' : msg.confidence_level === 'Medium' ? '🟡' : '🔴';
            const confidenceClass = `confidence-${(msg.confidence_level || 'medium').toLowerCase()}`;
            confidenceBadge = `<span class="confidence-badge ${confidenceClass}" title="Confidence: ${Math.round(msg.confidence_score)}%">${confidenceEmoji} ${Math.round(msg.confidence_score)}%</span>`;
        }
        
        // Add priority badge
        const priority = msg.priority_level || 'low';
        const priorityConfig = {
            'critical': { emoji: '🔴', label: 'Critical', class: 'priority-critical', time: 'Immediate' },
            'high': { emoji: '🟠', label: 'High', class: 'priority-high', time: `< ${msg.target_response_time || 5} min` },
            'medium': { emoji: '🟡', label: 'Medium', class: 'priority-medium', time: `< ${msg.target_response_time || 15} min` },
            'low': { emoji: '🟢', label: 'Low', class: 'priority-low', time: `< ${msg.target_response_time || 60} min` }
        };
        const priorityInfo = priorityConfig[priority] || priorityConfig['low'];
        const priorityBadge = `<span class="priority-badge ${priorityInfo.class}" title="${msg.escalation_reason || priorityInfo.label} - Target: ${priorityInfo.time}">
            ${priorityInfo.emoji} ${priorityInfo.label}
        </span>`;
        
        return `
            <tr data-id="${msg.id}" class="priority-row priority-${priority}">
                <td>${timeStr}</td>
                <td>
                    <div class="message-preview" title="${escapeHtml(msg.userMessage)}">
                        ${escapeHtml(msg.userMessage)}
                    </div>
                </td>
                <td>
                    ${priorityBadge}
                    <span class="category-badge ${categoryClass}">${msg.category}</span>
                    ${confidenceBadge}
                </td>
                <td>
                    <div class="response-preview" title="${escapeHtml(msg.aiResponse)}">
                        ${escapeHtml(msg.aiResponse)}
                    </div>
                </td>
                <td>
                    <div class="action-buttons">
                        <button class="btn-action btn-approve" onclick="handleAction(${msg.id}, 'approve')" title="Approve as-is">
                            <i class="fas fa-check"></i> Approve
                        </button>
                        <button class="btn-action btn-edit" onclick="handleAction(${msg.id}, 'edit')" title="Edit and approve">
                            <i class="fas fa-edit"></i> Edit
                        </button>
                        <button class="btn-action btn-reject" onclick="handleAction(${msg.id}, 'reject')" title="Reject and provide alternative">
                            <i class="fas fa-times"></i> Reject
                        </button>
                        <button class="btn-action btn-clarify" onclick="handleAction(${msg.id}, 'clarify')" title="Request clarification from user">
                            <i class="fas fa-question-circle"></i> Clarify
                        </button>
                        <button class="btn-action btn-escalate" onclick="handleAction(${msg.id}, 'escalate')" title="Escalate to admin">
                            <i class="fas fa-arrow-up"></i> Escalate
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

// Render Reviewed Table
function renderReviewedTable() {
    const tbody = document.getElementById('reviewedTableBody');
    const noReviewed = document.getElementById('noReviewed');
    
    if (reviewedMessages.length === 0) {
        tbody.innerHTML = '';
        noReviewed.classList.remove('hidden');
        return;
    }
    
    noReviewed.classList.add('hidden');
    tbody.innerHTML = reviewedMessages.map(msg => {
        const timeStr = formatTime(msg.timestamp);
        const categoryClass = `category-${msg.category}`;
        const decisionClass = `decision-${msg.decision}`;
        
        return `
            <tr>
                <td>${timeStr}</td>
                <td>
                    <div class="message-preview" title="${escapeHtml(msg.userMessage)}">
                        ${escapeHtml(msg.userMessage)}
                    </div>
                </td>
                <td>
                    <span class="category-badge ${categoryClass}">${msg.category}</span>
                </td>
                <td>
                    <div class="response-preview" title="${escapeHtml(msg.finalResponse)}">
                        ${escapeHtml(msg.finalResponse)}
                    </div>
                </td>
                <td>
                    <span class="decision-badge ${decisionClass}">${msg.decision}</span>
                </td>
            </tr>
        `;
    }).join('');
}

// Handle Action
async function handleAction(id, action) {
    const message = flaggedMessages.find(msg => msg.id === id);
    if (!message) return;
    
    const reviewTime = reviewStartTimes[id] ? Date.now() - reviewStartTimes[id] : 0;
    const reviewTimeSeconds = Math.round(reviewTime / 1000);
    
    // Handle actions that require modals
    if (action === 'edit') {
        openEditModal(message);
        return;
    }
    
    if (action === 'reject') {
        openRejectModal(message);
        return;
    }
    
    // Handle direct actions (approve, clarify, escalate)
    await submitModeratorAction(id, action, null, null, null, null, reviewTimeSeconds, message);
}

// Open Edit Modal
function openEditModal(message) {
    currentEditId = message.id;
    const textarea = document.getElementById('editTextarea');
    const originalPreview = document.getElementById('originalResponsePreview');
    
    textarea.value = message.aiResponse;
    originalPreview.textContent = message.aiResponse;
    updateCharCount('editTextarea', 'editCharCount');
    
    document.getElementById('editModal').classList.remove('hidden');
    textarea.focus();
}

// Close Edit Modal
function closeEditModal() {
    document.getElementById('editModal').classList.add('hidden');
    currentEditId = null;
    document.getElementById('editTextarea').value = '';
    document.getElementById('editNotes').value = '';
    document.getElementById('editCharCount').textContent = '0';
}

// Open Reject Modal
function openRejectModal(message) {
    currentEditId = message.id;
    const textarea = document.getElementById('rejectTextarea');
    const originalPreview = document.getElementById('rejectOriginalPreview');
    
    textarea.value = '';
    originalPreview.textContent = message.aiResponse;
    document.getElementById('rejectionReason').value = '';
    document.getElementById('rejectNotes').value = '';
    updateCharCount('rejectTextarea', 'rejectCharCount');
    
    document.getElementById('rejectModal').classList.remove('hidden');
    textarea.focus();
}

// Close Reject Modal
function closeRejectModal() {
    document.getElementById('rejectModal').classList.add('hidden');
    currentEditId = null;
    document.getElementById('rejectTextarea').value = '';
    document.getElementById('rejectionReason').value = '';
    document.getElementById('rejectNotes').value = '';
    document.getElementById('rejectCharCount').textContent = '0';
}

// Update character counter
function updateCharCount(textareaId, counterId) {
    const textarea = document.getElementById(textareaId);
    const counter = document.getElementById(counterId);
    if (textarea && counter) {
        counter.textContent = textarea.value.length;
    }
}

// Save Edit
async function saveEdit() {
    if (!currentEditId) return;
    
    const message = flaggedMessages.find(msg => msg.id === currentEditId);
    if (!message) return;
    
    const editedResponse = document.getElementById('editTextarea').value.trim();
    if (!editedResponse) {
        alert('Please enter a modified response.');
        return;
    }
    
    const notes = document.getElementById('editNotes').value.trim();
    const reviewTime = reviewStartTimes[currentEditId] ? Date.now() - reviewStartTimes[currentEditId] : 0;
    const reviewTimeSeconds = Math.round(reviewTime / 1000);
    
    await submitModeratorAction(
        currentEditId,
        'edit',
        editedResponse,
        null,
        null,
        notes,
        reviewTimeSeconds,
        message
    );
    
    closeEditModal();
}

// Save Reject
async function saveReject() {
    if (!currentEditId) return;
    
    const message = flaggedMessages.find(msg => msg.id === currentEditId);
    if (!message) return;
    
    const alternativeResponse = document.getElementById('rejectTextarea').value.trim();
    if (!alternativeResponse) {
        alert('Please enter an alternative response.');
        return;
    }
    
    const rejectionReason = document.getElementById('rejectionReason').value;
    if (!rejectionReason) {
        alert('Please select a rejection reason.');
        return;
    }
    
    const notes = document.getElementById('rejectNotes').value.trim();
    const reviewTime = reviewStartTimes[currentEditId] ? Date.now() - reviewStartTimes[currentEditId] : 0;
    const reviewTimeSeconds = Math.round(reviewTime / 1000);
    
    await submitModeratorAction(
        currentEditId,
        'reject',
        null,
        alternativeResponse,
        rejectionReason,
        notes,
        reviewTimeSeconds,
        message
    );
    
    closeRejectModal();
}

// Submit Moderator Action (shared function)
async function submitModeratorAction(
    messageId,
    action,
    editedResponse,
    alternativeResponse,
    rejectionReason,
    notes,
    reviewTimeSeconds,
    message
) {
    try {
        const requestBody = {
            action: action,
            edited_response: editedResponse || null,
            alternative_response: alternativeResponse || null,
            rejection_reason: rejectionReason || null,
            notes: notes || null,
            review_time_seconds: reviewTimeSeconds
        };
        
        // Submit moderator action to backend
        
        const response = await fetch(`${API_BASE_URL}/moderator/queue/${messageId}/action`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
            // Moderator action recorded successfully
        
        // Determine final response for display
        let finalResponse = message.aiResponse;
        if (action === 'edit' && editedResponse) {
            finalResponse = editedResponse + ' (Human-Edited)';
        } else if (action === 'reject' && alternativeResponse) {
            finalResponse = alternativeResponse + ' (Rejected & Replaced)';
        } else if (action === 'clarify') {
            finalResponse = 'Can you provide more details about your situation? This will help me give you a more accurate response.';
        } else if (action === 'escalate') {
            finalResponse = message.aiResponse + ' (Escalated to Admin)';
        } else if (action === 'approve') {
            finalResponse = message.aiResponse + ' (Approved)';
        }
        
        // Move to reviewed
        const reviewedMessage = {
            ...message,
            decision: action,
            finalResponse: finalResponse,
            reviewedAt: new Date(),
            reviewTime: reviewTimeSeconds * 1000
        };
        
        reviewedMessages.unshift(reviewedMessage);
        flaggedMessages = flaggedMessages.filter(msg => msg.id !== messageId);
        delete reviewStartTimes[messageId];
        
        renderPendingTable();
        renderReviewedTable();
        updateStats();
        
        // Show success message
        showNotification(`Action "${action}" completed successfully`, 'success');
        
    } catch (error) {
        console.error('Error submitting moderator action:', error);
        showNotification(`Error: ${error.message}`, 'error');
    }
}

// Show notification
function showNotification(message, type = 'info') {
    // Simple alert for now, could be enhanced with toast notifications
    if (type === 'error') {
        alert('❌ ' + message);
    } else {
        console.log('✅ ' + message);
    }
}

// Simulate New Flag
async function simulateNewFlag() {
    const categories = ['medical', 'financial', 'legal', 'crisis'];
    const category = categories[Math.floor(Math.random() * categories.length)];
    
    const sampleUserMessages = {
        medical: [
            "I have a fever and my head hurts. What medicine should I take?",
            "I've been feeling sick for days. Should I see a doctor?",
            "My pain is getting worse. Can you help?"
        ],
        financial: [
            "I want to invest my money in cryptocurrency. Is it safe?",
            "Should I take out a loan to buy stocks?",
            "I need advice on managing my credit card debt."
        ],
        legal: [
            "I need to sue my landlord. Can you help me with legal advice?",
            "Is it illegal to do this? I need legal guidance.",
            "I want to break my contract. What are my legal options?"
        ],
        crisis: [
            "I feel so hopeless and depressed. I don't know what to do.",
            "I've been thinking about ending my life.",
            "Everything feels meaningless and I'm in crisis."
        ]
    };
    
    const userMessages = sampleUserMessages[category];
    const userMessage = userMessages[Math.floor(Math.random() * userMessages.length)];
    
    // Send to backend to get flagged
    try {
        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: userMessage,
                learning_mode: false
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            // Refresh the queue to show the new flagged message
            await fetchFlaggedMessages();
            // New flag simulated via backend
                category: category,
                userMessage: userMessage,
                flagged: data.flagged
            });
        } else {
            throw new Error('Backend request failed');
        }
    } catch (error) {
        console.error('Error simulating flag via backend, using local:', error);
        // Fallback: add locally
        const sampleAIResponses = {
            medical: "I understand you mentioned medical-related topics. In a production AI system, medical queries would typically be flagged for review to ensure accurate, safe information. This educational system demonstrates how such content is identified and would be handled with appropriate guardrails and potentially human medical professional oversight.",
            financial: "I notice financial-related keywords in your message. Financial advice requires careful consideration and often regulatory compliance. In production systems, such queries would be flagged for review to ensure responsible handling. This demonstrates how AI safety systems identify and manage sensitive financial content.",
            legal: "Your message contains legal-related terms. Legal matters often require professional expertise and careful handling. In a production AI system, legal queries would be flagged for review to ensure appropriate responses. This educational system shows how such content is identified for safety oversight.",
            crisis: "I detect content that may relate to crisis situations. In production systems, crisis-related content is immediately flagged for human review and appropriate support resources. This educational demonstration shows how AI safety systems identify such critical content. If you're experiencing a crisis, please reach out to professional support services."
        };
        
        const newMessage = {
            id: `msg_${Date.now()}`,
            timestamp: new Date(),
            userMessage: userMessage,
            category: category,
            aiResponse: sampleAIResponses[category],
            confidence: 0.85
        };
        
        flaggedMessages.unshift(newMessage);
        reviewStartTimes[newMessage.id] = Date.now();
        
        renderPendingTable();
        updateStats();
        
        // New flag simulated locally
            id: newMessage.id,
            category: category,
            userMessage: userMessage
        });
    }
}

// Update Stats
function updateStats() {
    const totalFlagged = flaggedMessages.length + reviewedMessages.length;
    const pendingReviews = flaggedMessages.length;
    
    // Calculate average review time
    let totalReviewTime = 0;
    let reviewCount = 0;
    reviewedMessages.forEach(msg => {
        if (msg.reviewTime) {
            totalReviewTime += msg.reviewTime;
            reviewCount++;
        }
    });
    
    const avgReviewTime = reviewCount > 0 
        ? Math.round(totalReviewTime / reviewCount / 1000 / 60) // minutes
        : 0;
    
    document.getElementById('totalFlagged').textContent = totalFlagged;
    document.getElementById('pendingReviews').textContent = pendingReviews;
    document.getElementById('avgReviewTime').textContent = avgReviewTime > 0 ? `${avgReviewTime}m` : '0m';
}

// Make fetchFlaggedMessages available globally for refresh
window.fetchFlaggedMessages = fetchFlaggedMessages;

// Format Time
function formatTime(date) {
    const now = new Date();
    const diff = now - date;
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);
    
    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;
    
    return date.toLocaleDateString('en-US', { 
        month: 'short', 
        day: 'numeric', 
        hour: '2-digit', 
        minute: '2-digit' 
    });
}

// Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Make handleAction available globally
window.handleAction = handleAction;
