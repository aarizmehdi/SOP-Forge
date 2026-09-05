/**
 * SOP Forge — HR Assistant Chat Interface
 * Premium full-screen chat experience inspired by ChatGPT/Claude.
 * Welcome state is vertically centered. Conversation flows naturally.
 */

const ChatAssistant = (() => {
    let chatHistory = [];
    let isProcessing = false;
    let hasStartedConversation = false;
    
    let isRecording = false;
    let currentTextBase = '';

    async function render(container) {
        chatHistory = [];
        isProcessing = false;
        hasStartedConversation = false;

        const user = Auth.getUser();
        const firstName = user.name.split(' ')[0];

        container.innerHTML = `
            <div class="ca-layout">
                <!-- Welcome Hero (vertically centered, shown before first message) -->
                <div id="ca-welcome" class="ca-welcome">
                    <div class="ca-welcome-inner">
                        <div class="ca-hero-icon">
                            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                            </svg>
                        </div>
                        <h1 class="ca-hero-title">Good ${getGreeting()}, ${firstName}</h1>
                        <p class="ca-hero-subtitle">How can I help you today?</p>

                        <div class="ca-quick-actions">
                            <button class="ca-action-card" onclick="ChatAssistant.selectDepartment('I need help with leave or attendance')">
                                <span class="ca-action-emoji">📅</span>
                                <div class="ca-action-text">
                                    <span class="ca-action-title">Leave & Attendance</span>
                                    <span class="ca-action-desc">Annual, sick, casual leave & attendance</span>
                                </div>
                                <svg class="ca-action-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                            </button>
                            <button class="ca-action-card" onclick="ChatAssistant.selectDepartment('I need help with expense reimbursement')">
                                <span class="ca-action-emoji">💰</span>
                                <div class="ca-action-text">
                                    <span class="ca-action-title">Finance & Expenses</span>
                                    <span class="ca-action-desc">Travel, medical, or equipment claims</span>
                                </div>
                                <svg class="ca-action-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                            </button>
                            <button class="ca-action-card" onclick="ChatAssistant.selectDepartment('I need help with IT system access')">
                                <span class="ca-action-emoji">🔑</span>
                                <div class="ca-action-text">
                                    <span class="ca-action-title">IT & Systems</span>
                                    <span class="ca-action-desc">System access, VPN, or credentials</span>
                                </div>
                                <svg class="ca-action-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                            </button>
                            <button class="ca-action-card" onclick="ChatAssistant.selectDepartment('I want to ask about company policies')">
                                <span class="ca-action-emoji">📋</span>
                                <div class="ca-action-text">
                                    <span class="ca-action-title">Company Policies</span>
                                    <span class="ca-action-desc">Rules, guidelines, and benefits</span>
                                </div>
                                <svg class="ca-action-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Messages (hidden until first message, then replaces welcome) -->
                <div id="ca-messages" class="ca-messages" style="display:none"></div>

                <!-- Input bar — always visible at bottom -->
                <div class="ca-input-bar">
                    <div class="ca-input-wrap">
                        <input type="text" id="chat-input"
                            placeholder="Type your request or message..."
                            autocomplete="off"
                            onkeydown="if(event.key==='Enter' && !event.shiftKey) { event.preventDefault(); ChatAssistant.sendUserMessage(); }">
                        <button id="chat-mic-btn" class="ca-send-btn" style="margin-right: 4px;" onclick="ChatAssistant.toggleRecording()" title="Speak">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="22"/><line x1="8" y1="22" x2="16" y2="22"/></svg>
                        </button>
                        <button id="chat-send-btn" class="ca-send-btn" onclick="ChatAssistant.sendUserMessage()" title="Send">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M22 2L11 13"/><path d="M22 2L15 22L11 13L2 9L22 2Z"/></svg>
                        </button>
                    </div>
                </div>
            </div>
        `;
    }

    function getGreeting() {
        const h = new Date().getHours();
        if (h < 12) return 'morning';
        if (h < 17) return 'afternoon';
        return 'evening';
    }

    function switchToConversation() {
        if (hasStartedConversation) return;
        hasStartedConversation = true;
        const welcome = document.getElementById('ca-welcome');
        const messages = document.getElementById('ca-messages');
        if (welcome) welcome.style.display = 'none';
        if (messages) messages.style.display = 'flex';
    }

    function selectDepartment(promptText) {
        if (isProcessing) return;
        document.getElementById('chat-input').value = promptText;
        sendUserMessage();
    }

    async function sendUserMessage() {
        if (isProcessing) return;
        const input = document.getElementById('chat-input');
        const text = input.value.trim();
        if (!text) return;

        input.value = '';
        isProcessing = true;

        const sendBtn = document.getElementById('chat-send-btn');
        input.disabled = true;
        input.placeholder = 'Processing your request...';
        sendBtn.disabled = true;

        switchToConversation();

        const messagesContainer = document.getElementById('ca-messages');
        const user = Auth.getUser();

        // User message
        const userRow = document.createElement('div');
        userRow.className = 'ca-msg ca-msg-user';
        userRow.innerHTML = `
            <div class="ca-msg-avatar ca-avatar-user">${Auth.getInitials(user.name)}</div>
            <div class="ca-msg-body">
                <div class="ca-msg-name">${user.name}</div>
                <div class="ca-msg-content ca-content-user">${escapeHtml(text)}</div>
            </div>
        `;
        messagesContainer.appendChild(userRow);

        // Typing indicator
        const typingRow = document.createElement('div');
        typingRow.className = 'ca-msg ca-msg-ai';
        typingRow.id = 'ca-typing';
        typingRow.innerHTML = `
            <div class="ca-msg-avatar ca-avatar-ai">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
            </div>
            <div class="ca-msg-body">
                <div class="ca-msg-name">Forge AI Copilot</div>
                <div class="ca-msg-content ca-content-ai">
                    <div class="ca-typing-dots">
                        <span></span><span></span><span></span>
                    </div>
                </div>
            </div>
        `;
        messagesContainer.appendChild(typingRow);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        chatHistory.push({ role: 'user', content: text });

        try {
            const result = await API.sendChatAssistant(text, chatHistory);
            document.getElementById('ca-typing')?.remove();
            chatHistory.push({ role: 'assistant', content: result.message });

            let contentHtml = `<p>${formatMarkdown(result.message)}</p>`;

            if (result.request_details) {
                const req = result.request_details;
                const isAwaitingEvidence = req.status === 'awaiting_evidence' || req.decision === 'awaiting_evidence';

                if (isAwaitingEvidence) {
                    contentHtml += `
                        <div id="chat-evidence-card-${req.id}" style="margin-top: 14px; background: rgba(59, 130, 246, 0.08); border: 1.5px dashed rgba(59, 130, 246, 0.35); border-radius: 12px; padding: 16px; text-align: center;">
                            <div style="font-size: 13px; font-weight: 600; color: var(--primary-400); margin-bottom: 4px; display: flex; align-items: center; justify-content: center; gap: 6px;">
                                📎 Upload Required Medical Certificate / Evidence
                            </div>
                            <div style="font-size: 11px; color: var(--text-tertiary); margin-bottom: 12px;">
                                Allowed Formats: <strong>PDF, JPEG, PNG</strong> (Max file size: <strong>5MB</strong>)
                            </div>
                            <input type="file" id="chat-file-input-${req.id}" style="display:none" accept=".pdf,.jpeg,.jpg,.png" onchange="ChatAssistant.uploadEvidenceFromChat('${req.id}', this)">
                            <button class="btn btn-primary btn-sm" style="font-size: 12px; padding: 8px 18px; border-radius: 8px; display: inline-flex; align-items: center; gap: 6px;" onclick="document.getElementById('chat-file-input-${req.id}').click()">
                                📁 Select File & Attach Evidence
                            </button>
                            <div id="chat-upload-status-${req.id}" style="font-size: 11px; margin-top: 8px; font-weight: 500;"></div>
                        </div>
                    `;
                } else {
                    contentHtml += `
                        <div style="margin-top: 12px;">
                            <a href="#/requests" class="btn btn-secondary btn-sm" style="background:var(--bg-tertiary);border-color:var(--border-subtle);color:var(--text-primary);font-size:12px;padding:6px 12px">View in My Requests</a>
                        </div>
                    `;
                }
            }

            const aiRow = document.createElement('div');
            aiRow.className = 'ca-msg ca-msg-ai';
            aiRow.innerHTML = `
                <div class="ca-msg-avatar ca-avatar-ai">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                </div>
                <div class="ca-msg-body">
                    <div class="ca-msg-name">Forge AI Copilot</div>
                    <div class="ca-msg-content ca-content-ai">${contentHtml}</div>
                </div>
            `;
            messagesContainer.appendChild(aiRow);

        } catch (err) {
            document.getElementById('ca-typing')?.remove();
            const errRow = document.createElement('div');
            errRow.className = 'ca-msg ca-msg-ai';
            errRow.innerHTML = `
                <div class="ca-msg-avatar ca-avatar-ai" style="border-color:#ef4444">!</div>
                <div class="ca-msg-body">
                    <div class="ca-msg-name">Forge AI Copilot</div>
                    <div class="ca-msg-content ca-content-ai" style="border-color:rgba(239,68,68,0.3)">
                        <p style="color:#ef4444">Something went wrong. Please try again.</p>
                    </div>
                </div>
            `;
            messagesContainer.appendChild(errRow);
        }

        isProcessing = false;
        input.disabled = false;
        input.placeholder = 'Type your request or message...';
        sendBtn.disabled = false;
        input.focus();
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    function escapeHtml(s) { return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
    function formatMarkdown(t) { return t.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\*(.*?)\*/g, '<em>$1</em>').replace(/\n/g, '<br>'); }

    let recognition = null;

    async function toggleRecording() {
        if (isRecording) {
            stopRecording();
        } else {
            await startRecording();
        }
    }

    async function startRecording() {
        if (!('webkitSpeechRecognition' in window)) {
            alert("Your browser does not support the Web Speech API. Please use Chrome or Edge.");
            return;
        }

        const micBtn = document.getElementById('chat-mic-btn');
        const input = document.getElementById('chat-input');
        const sendBtn = document.getElementById('chat-send-btn');
        
        if (micBtn) micBtn.classList.add('is-recording');
        if (input) {
            input.disabled = true;
            input.placeholder = "Listening... Speak now";
        }
        if (sendBtn) sendBtn.disabled = true;
        isRecording = true;

        currentTextBase = input.value;

        recognition = new webkitSpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = 'en-US';

        recognition.onresult = (event) => {
            let interimTranscript = '';
            let finalTranscript = '';

            for (let i = event.resultIndex; i < event.results.length; ++i) {
                if (event.results[i].isFinal) {
                    finalTranscript += event.results[i][0].transcript;
                } else {
                    interimTranscript += event.results[i][0].transcript;
                }
            }

            if (finalTranscript) {
                currentTextBase = (currentTextBase ? currentTextBase + ' ' : '') + finalTranscript;
                input.value = currentTextBase;
            } else if (interimTranscript) {
                input.value = (currentTextBase ? currentTextBase + ' ' : '') + interimTranscript;
            }
        };

        recognition.onerror = (event) => {
            console.error("Speech recognition error:", event.error);
            stopRecording();
            if (event.error === 'not-allowed') {
                alert("Microphone access denied. Please allow microphone access in your browser settings.");
            } else {
                alert("Speech recognition error: " + event.error);
            }
        };

        recognition.onend = () => {
            stopRecording();
        };

        try {
            recognition.start();
        } catch (error) {
            console.error("Error starting recognition:", error);
            stopRecording();
        }
    }

    function stopRecording() {
        if (!isRecording) return;
        isRecording = false;
        
        const micBtn = document.getElementById('chat-mic-btn');
        const input = document.getElementById('chat-input');
        const sendBtn = document.getElementById('chat-send-btn');
        
        if (micBtn) micBtn.classList.remove('is-recording');
        if (input) {
            input.disabled = false;
            input.placeholder = "Type your request or message...";
        }
        if (sendBtn) sendBtn.disabled = false;
        
        if (recognition) {
            recognition.stop();
            recognition = null;
        }
        
        // Auto-send if there's text after recording stops
        if (input && input.value.trim().length > 0) {
            sendUserMessage();
        }
    }

    async function uploadEvidenceFromChat(requestId, fileInput) {
        if (!fileInput.files || !fileInput.files[0]) return;
        const file = fileInput.files[0];
        const statusEl = document.getElementById(`chat-upload-status-${requestId}`);
        const cardEl = document.getElementById(`chat-evidence-card-${requestId}`);

        // Front-end File Size Validation (5 MB Max)
        if (file.size > 5 * 1024 * 1024) {
            App.toast('File size exceeds 5MB limit. Please upload a file smaller than 5MB.', 'error');
            if (statusEl) statusEl.innerHTML = '<span style="color:#ef4444">❌ File exceeds 5MB limit.</span>';
            return;
        }

        // Extension validation
        const ext = file.name.split('.').pop().toLowerCase();
        if (!['pdf', 'jpg', 'jpeg', 'png'].includes(ext)) {
            App.toast('Invalid file format. Only PDF, JPEG, and PNG files are allowed.', 'error');
            if (statusEl) statusEl.innerHTML = '<span style="color:#ef4444">❌ Invalid file type. PDF, JPEG, PNG only.</span>';
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        try {
            if (statusEl) statusEl.innerHTML = '<span style="color:var(--primary-400)">⏳ Uploading and evaluating evidence...</span>';
            const token = Auth.getToken();
            const res = await fetch(`/api/evidence/upload/${requestId}`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`
                },
                body: formData
            });

            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.detail || 'Failed to upload evidence');
            }

            App.toast('Medical certificate attached successfully!', 'success');
            
            if (cardEl) {
                cardEl.style.borderStyle = 'solid';
                cardEl.style.borderColor = 'rgba(16, 185, 129, 0.4)';
                cardEl.style.background = 'rgba(16, 185, 129, 0.08)';
                cardEl.innerHTML = `
                    <div style="font-size: 13px; font-weight: 600; color: var(--success); display: flex; align-items: center; justify-content: center; gap: 6px;">
                        ✅ Medical Certificate Attached (${file.name})
                    </div>
                    <div style="font-size: 11px; color: var(--text-tertiary); margin-top: 4px;">
                        Status: <strong>${(data.new_request_status || 'ESCALATED').toUpperCase()}</strong> — Sent to Manager for Review
                    </div>
                `;
            }

            // Append assistant confirmation message
            const messagesContainer = document.getElementById('ca-messages');
            const aiRow = document.createElement('div');
            aiRow.className = 'ca-msg ca-msg-ai';
            aiRow.innerHTML = `
                <div class="ca-msg-avatar ca-avatar-ai">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                </div>
                <div class="ca-msg-body">
                    <div class="ca-msg-name">Forge AI Copilot</div>
                    <div class="ca-msg-content ca-content-ai">
                        <p><strong>⏳ Request Sent for Manager Review.</strong></p>
                        <p>Thank you! Your medical certificate (<strong>${file.name}</strong>) has been uploaded and attached to your leave request. Your request is now routed to your manager with your supporting evidence.</p>
                        <div style="margin-top: 10px;">
                            <a href="#/requests" class="btn btn-secondary btn-sm" style="background:var(--bg-tertiary);border-color:var(--border-subtle);color:var(--text-primary);font-size:12px;padding:6px 12px">View in My Requests</a>
                        </div>
                    </div>
                </div>
            `;
            messagesContainer.appendChild(aiRow);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;

        } catch (err) {
            App.toast(`Upload failed: ${err.message}`, 'error');
            if (statusEl) statusEl.innerHTML = `<span style="color:#ef4444">❌ Upload failed: ${err.message}</span>`;
        }
    }

    return { render, selectDepartment, sendUserMessage, toggleRecording, uploadEvidenceFromChat };
})();
