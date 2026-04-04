// State
let flaggedMessages = [];
let reviewedMessages = [];
let currentEditId = null;
let reviewStartTimes = {};
const API_BASE_URL = 'http://localhost:8000';

/** Align queue IDs: data-id / API may be string "42" while msg.id is number 42 */
function normalizeQueueId(id) {
    if (id == null || id === '') return null;
    const n = Number(id);
    if (!Number.isNaN(n) && String(n) === String(id).trim()) return n;
    return id;
}

// Sample flagged messages for fallback demonstration
const sampleMessages = [
    {
        id: "msg_1",
        timestamp: new Date(Date.now() - 15 * 60000).toISOString(),
        user_message: "I have a terrible headache and feel sick. Should I take medicine?",
        category: "medical",
        ai_response: "I understand you mentioned medical-related topics...",
        confidence: 0.85
    }
];

// Fetch flagged messages from backend
async function fetchFlaggedMessages() {
    try {
        // Pointing to the correct /moderator/flags endpoint
        const response = await fetch(`${API_BASE_URL}/moderator/flags`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        
        // Transform backend format to frontend format
        // Transform backend format to frontend format
        flaggedMessages = data.map(msg => ({
            id: msg.id, 
            timestamp: msg.timestamp,
            userMessage: msg.user_message,
            category: msg.category,
            aiResponse: msg.ai_response,
            confidence: msg.confidence,
            // UPDATED THESE TWO LINES BELOW:
            confidence_score: msg.confidence_score > 0 ? msg.confidence_score : (msg.confidence * 100),
            confidence_level: msg.confidence_level !== "Unknown" ? msg.confidence_level : (msg.confidence >= 0.8 ? 'High' : 'Medium'),
            priority_level: msg.priority_level || 'low',
            escalation_reason: msg.escalation_reason || 'Safety Trigger',
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
        
        renderPendingTable();
        updateStats();
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    fetchFlaggedMessages();
    
    // Auto-refresh every 5 seconds to catch new flags
    setInterval(fetchFlaggedMessages, 5000);
    
    renderReviewedTable();
    updateStats();
    
    // Event listeners
    document.getElementById('simulateFlagBtn').addEventListener('click', simulateNewFlag);

    // Delegated clicks for row actions (avoids broken inline handlers for string/non-numeric IDs)
    const pendingBody = document.getElementById('pendingTableBody');
    if (pendingBody) {
        pendingBody.addEventListener('click', (e) => {
            const btn = e.target.closest('button[data-action][data-id]');
            if (!btn) return;
            e.preventDefault();
            const action = btn.getAttribute('data-action');
            const idRaw = btn.getAttribute('data-id');
            if (idRaw == null || idRaw === '') return;
            handleAction(idRaw, action);
        });
    }

    // Modals setup
    setupModals();
});

function setupModals() {
    // Edit modal
    document.getElementById('closeEditModalBtn').addEventListener('click', closeEditModal);
    document.getElementById('cancelEditBtn').addEventListener('click', closeEditModal);
    document.getElementById('saveEditBtn').addEventListener('click', (e) => {
        e.preventDefault();
        saveEdit();
    });
    document.getElementById('editTextarea').addEventListener('input', () => updateCharCount('editTextarea', 'editCharCount'));

    // Reject modal — must match moderator.html <button id="saveRejectBtn" ...>
    const saveRejectBtn = document.getElementById('saveRejectBtn');
    if (!saveRejectBtn) {
        console.error('moderator.js: missing #saveRejectBtn — Reject & Send Alternative will not work');
    } else {
        saveRejectBtn.addEventListener('click', function onSaveRejectClick(e) {
            e.preventDefault();
            e.stopPropagation();
            saveReject();
        });
    }
    document.getElementById('closeRejectModalBtn').addEventListener('click', closeRejectModal);
    document.getElementById('cancelRejectBtn').addEventListener('click', closeRejectModal);
    document.getElementById('rejectTextarea').addEventListener('input', () => updateCharCount('rejectTextarea', 'rejectCharCount'));
}

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
        
        const confidenceEmoji = msg.confidence_level === 'High' ? '🟢' : msg.confidence_level === 'Medium' ? '🟡' : '🔴';
        const confidenceClass = `confidence-${(msg.confidence_level || 'medium').toLowerCase()}`;
        const confidenceBadge = `<span class="confidence-badge ${confidenceClass}" title="Confidence: ${Math.round(msg.confidence_score)}%">${confidenceEmoji} ${Math.round(msg.confidence_score)}%</span>`;
        
        const priority = msg.priority_level || 'low';
        const priorityConfig = {
            'critical': { emoji: '🔴', label: 'Critical', class: 'priority-critical' },
            'high': { emoji: '🟠', label: 'High', class: 'priority-high' },
            'medium': { emoji: '🟡', label: 'Medium', class: 'priority-medium' },
            'low': { emoji: '🟢', label: 'Low', class: 'priority-low' }
        };
        const pInfo = priorityConfig[priority] || priorityConfig['low'];
        const priorityBadge = `<span class="priority-badge ${pInfo.class}">${pInfo.emoji} ${pInfo.label}</span>`;
        
        return `
            <tr data-id="${msg.id}" class="priority-row priority-${priority}">
                <td>${timeStr}</td>
                <td><div class="message-preview" title="${escapeHtml(msg.userMessage)}">${escapeHtml(msg.userMessage)}</div></td>
                <td>
                    ${priorityBadge}
                    <span class="category-badge ${categoryClass}">${msg.category}</span>
                    ${confidenceBadge}
                </td>
                <td><div class="response-preview" title="${escapeHtml(msg.aiResponse)}">${escapeHtml(msg.aiResponse)}</div></td>
                <td>
                    <div class="action-buttons">
                        <button type="button" class="btn-action btn-approve" data-action="approve" data-id="${String(msg.id)}"><i class="fas fa-check"></i> Approve</button>
                        <button type="button" class="btn-action btn-edit" data-action="edit" data-id="${String(msg.id)}"><i class="fas fa-edit"></i> Edit</button>
                        <button type="button" class="btn-action btn-reject" data-action="reject" data-id="${String(msg.id)}"><i class="fas fa-times"></i> Reject</button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

// Handle Action (id may be string from data-id or number from tests)
async function handleAction(id, action) {
    const message = flaggedMessages.find(msg => msg.id == id);
    if (!message) return;
    
    const reviewTimeSeconds = Math.round((Date.now() - (reviewStartTimes[id] || Date.now())) / 1000);
    
    if (action === 'edit') {
        openEditModal(message);
    } else if (action === 'reject') {
        openRejectModal(message);
    } else {
        await submitModeratorAction(id, action, null, null, null, null, reviewTimeSeconds, message);
    }
}

async function submitModeratorAction(messageId, action, editedResponse, altResponse, reason, notes, reviewTime, message) {
    try {
        const response = await fetch(`${API_BASE_URL}/moderator/queue/${messageId}/action`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                action,
                edited_response: editedResponse,
                alternative_response: altResponse,
                rejection_reason: reason,
                notes: notes,
                review_time_seconds: reviewTime
            })
        });
        
        if (!response.ok) throw new Error('Action submission failed');
        
        // Success: Move to reviewed list
        const reviewedMessage = {
            ...message,
            decision: action,
            finalResponse: editedResponse || altResponse || message.aiResponse,
            timestamp: new Date(),
            reviewTime: reviewTime * 1000
        };
        
        reviewedMessages.unshift(reviewedMessage);
        flaggedMessages = flaggedMessages.filter(msg => msg.id != messageId);
        renderPendingTable();
        renderReviewedTable();
        updateStats();
        showNotification(`Action "${action}" completed`, 'success');
        
    } catch (error) {
        console.error('Error submitting action:', error);
        showNotification(error.message, 'error');
    }
}

// Modal Logic
function openEditModal(msg) {
    currentEditId = normalizeQueueId(msg.id);
    document.getElementById('editTextarea').value = msg.aiResponse;
    document.getElementById('originalResponsePreview').textContent = msg.aiResponse;
    document.getElementById('editModal').classList.remove('hidden');
}

function closeEditModal() {
    document.getElementById('editModal').classList.add('hidden');
    currentEditId = null;
}

async function saveEdit() {
    const editedResponse = document.getElementById('editTextarea').value.trim();
    const msg = flaggedMessages.find(m => m.id == currentEditId);
    if (!msg) {
        showNotification('Could not find this message. Close the modal and try again.', 'error');
        return;
    }
    if (!editedResponse) {
        showNotification('Enter a modified response before saving.', 'error');
        return;
    }
    const reviewTime = Math.round((Date.now() - reviewStartTimes[msg.id]) / 1000);
    await submitModeratorAction(currentEditId, 'edit', editedResponse, null, null, 'Human edited', reviewTime, msg);
    closeEditModal();
}

function openRejectModal(msg) {
    currentEditId = normalizeQueueId(msg.id);
    document.getElementById('rejectOriginalPreview').textContent = msg.aiResponse;
    document.getElementById('rejectTextarea').value = '';
    document.getElementById('rejectionReason').value = '';
    const rc = document.getElementById('rejectCharCount');
    if (rc) rc.textContent = '0';
    document.getElementById('rejectModal').classList.remove('hidden');
    console.log('[openRejectModal] currentEditId =', currentEditId, 'msg.id was', msg.id);
}

function closeRejectModal() {
    document.getElementById('rejectModal').classList.add('hidden');
    currentEditId = null;
}

async function saveReject() {
    console.log('Reject button clicked');

    const altResponse = document.getElementById('rejectTextarea').value.trim();
    const reasonEl = document.getElementById('rejectionReason');
    const reason = reasonEl ? reasonEl.value.trim() : '';
    // Loose equality: data-id / DOM is string, backend JSON often uses number
    const msg = flaggedMessages.find(m => m.id == currentEditId);

    if (currentEditId == null) {
        alert('Cannot submit: no message is selected (currentEditId is null). Close the modal and click Reject on a row again.');
        showNotification('currentEditId is null — reopen Reject from the queue.', 'error');
        return;
    }
    if (!msg) {
        alert('Could not find this message in the pending queue. The list may have refreshed — close and try again.');
        showNotification('Could not find this message. Close the modal and try again.', 'error');
        return;
    }
    if (!reason) {
        alert('Please select a rejection reason from the dropdown.');
        showNotification('Select a rejection reason.', 'error');
        return;
    }
    if (!altResponse) {
        alert('Please enter an alternative response in the text area.');
        showNotification('Enter an alternative response.', 'error');
        return;
    }

    const reviewTime = Math.round((Date.now() - (reviewStartTimes[msg.id] || Date.now())) / 1000);
    const idForApi = normalizeQueueId(currentEditId) ?? currentEditId;
    await submitModeratorAction(idForApi, 'reject', null, altResponse, reason, 'Rejected', reviewTime, msg);
    closeRejectModal();
}

// Helpers
function updateStats() {
    document.getElementById('totalFlagged').textContent = flaggedMessages.length + reviewedMessages.length;
    document.getElementById('pendingReviews').textContent = flaggedMessages.length;
}

function formatTime(timestamp) {
    const date = new Date(timestamp);
    const now = new Date();
    
    // Calculate difference in seconds for better accuracy
    const diffInSeconds = Math.floor((now - date) / 1000);
    
    if (diffInSeconds < 60) return 'Just now';
    
    const minutes = Math.floor(diffInSeconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    
    const days = Math.floor(hours / 24);
    if (days < 7) return `${days}d ago`;
    
    return date.toLocaleDateString('en-US', { 
        month: 'short', 
        day: 'numeric', 
        hour: '2-digit', 
        minute: '2-digit' 
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || "";
    return div.innerHTML;
}

function updateCharCount(tid, cid) {
    document.getElementById(cid).textContent = document.getElementById(tid).value.length;
}

function showNotification(m, type) {
    console.log(`[${type}] ${m}`);
}

function renderReviewedTable() {
    const tbody = document.getElementById('reviewedTableBody');
    const noReviewed = document.getElementById('noReviewed');
    if (reviewedMessages.length === 0) {
        noReviewed.classList.remove('hidden');
        return;
    }
    noReviewed.classList.add('hidden');
    tbody.innerHTML = reviewedMessages.map(msg => `
        <tr>
            <td>${formatTime(msg.timestamp)}</td>
            <td><div class="message-preview">${escapeHtml(msg.userMessage)}</div></td>
            <td><span class="category-badge category-${msg.category}">${msg.category}</span></td>
            <td><div class="response-preview">${escapeHtml(msg.finalResponse)}</div></td>
            <td><span class="decision-badge decision-${msg.decision}">${msg.decision}</span></td>
        </tr>
    `).join('');
}

async function simulateNewFlag() {
    await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: "I am having a medical crisis, help!", learning_mode: false })
    });
    fetchFlaggedMessages();
}

// Global exposure (inline handlers removed; keep for debugging)
window.handleAction = handleAction;
window.fetchFlaggedMessages = fetchFlaggedMessages;
window.saveReject = saveReject;