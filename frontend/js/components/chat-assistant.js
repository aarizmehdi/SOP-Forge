/**
 * SOP Forge conversational UI. Server UI state and allowed actions are authoritative.
 */
const ChatAssistant = (() => {
    const STATES = Object.freeze({
        DOMAIN_SELECTION: 'DOMAIN_SELECTION',
        LANGUAGE_SELECTION: 'LANGUAGE_SELECTION',
        ACTIVE_CHAT: 'ACTIVE_CHAT',
        EVIDENCE_GATE: 'EVIDENCE_GATE',
        TERMINAL: 'TERMINAL',
    });
    const DOMAINS = [
        ['leave_hr', 'Leave & HR', 'Leave requests, balances, and HR guidance'],
        ['expenses_finance', 'Expenses & Finance', 'Reimbursements and expense guidance'],
        ['it_system_access', 'IT & System Access', 'System permissions and access requests'],
        ['policies_general', 'Policies & General', 'Company policy and organizational questions'],
    ];

    let uiState = STATES.DOMAIN_SELECTION;
    let allowedActions = [];
    let conversationId = null;
    let selectedDomain = null;
    let selectedLanguage = null;
    let isProcessing = false;
    let recognition = null;
    let isRecording = false;
    let currentTextBase = '';

    async function render(container) {
        conversationId = null;
        selectedDomain = null;
        selectedLanguage = null;
        isProcessing = false;
        allowedActions = [];
        uiState = STATES.DOMAIN_SELECTION;
        const user = Auth.getUser();
        const firstName = user.name.split(' ')[0];
        container.innerHTML = `
            <div class="ca-layout">
                <div id="ca-welcome" class="ca-welcome">
                    <div class="ca-welcome-inner">
                        <div class="ca-hero-icon" aria-hidden="true">✦</div>
                        <div class="ca-step-label">Step 1 of 2</div>
                        <h1 class="ca-hero-title">Good ${getGreeting()}, ${escapeHtml(firstName)}</h1>
                        <p class="ca-hero-subtitle">Choose an area so Forge AI can help in the right professional context.</p>
                        <div class="ca-quick-actions" id="ca-domain-choices">
                            ${DOMAINS.map(([value, title, description]) => `
                                <button class="ca-action-card" data-domain-choice="${value}" onclick="ChatAssistant.selectDomain('${value}')">
                                    <span class="ca-action-text"><span class="ca-action-title">${title}</span>
                                    <span class="ca-action-desc">${description}</span></span>
                                    <span class="ca-action-arrow" aria-hidden="true">→</span>
                                </button>`).join('')}
                        </div>
                    </div>
                </div>
                <div id="ca-messages" class="ca-messages" style="display:none"></div>
                <div id="ca-controls"></div>
            </div>`;
        renderControls();
    }

    function getGreeting() {
        const h = new Date().getHours();
        return h < 12 ? 'morning' : h < 17 ? 'afternoon' : 'evening';
    }

    function setState(state, actions = [], terminal = null) {
        if (!Object.values(STATES).includes(state)) throw new Error('Unknown conversation UI state');
        uiState = state;
        allowedActions = actions;
        const welcome = document.getElementById('ca-welcome');
        const messages = document.getElementById('ca-messages');
        const selecting = state === STATES.DOMAIN_SELECTION || state === STATES.LANGUAGE_SELECTION;
        if (welcome) welcome.style.display = selecting ? 'flex' : 'none';
        if (messages) messages.style.display = selecting ? 'none' : 'flex';
        renderControls(terminal);
    }

    function renderControls(terminal = null) {
        const host = document.getElementById('ca-controls');
        if (!host) return;
        if (uiState === STATES.DOMAIN_SELECTION || uiState === STATES.LANGUAGE_SELECTION) {
            host.innerHTML = '';
            return;
        }
        if (uiState === STATES.ACTIVE_CHAT) {
            host.innerHTML = `
                <div class="ca-input-bar" data-ui-state="ACTIVE_CHAT">
                    <div class="ca-input-wrap">
                        <input type="text" id="chat-input" placeholder="Type your request or message..." autocomplete="off"
                            onkeydown="if(event.key==='Enter' && !event.shiftKey){event.preventDefault();ChatAssistant.sendUserMessage();}">
                        <button id="chat-mic-btn" class="ca-send-btn" onclick="ChatAssistant.toggleRecording()" title="Speak" aria-label="Speak">◉</button>
                        <button id="chat-send-btn" class="ca-send-btn" onclick="ChatAssistant.sendUserMessage()" title="Send" aria-label="Send">➤</button>
                    </div>
                </div>`;
            return;
        }
        if (uiState === STATES.EVIDENCE_GATE) {
            host.innerHTML = `
                <div class="ca-transaction-bar" data-ui-state="EVIDENCE_GATE">
                    <button class="btn btn-primary" data-primary-action="upload_evidence" onclick="ChatAssistant.chooseEvidenceFile()">Upload Evidence</button>
                    <button class="btn btn-secondary" data-primary-action="skip_evidence" onclick="ChatAssistant.skipEvidence()">Skip Evidence</button>
                    <input id="chat-evidence-file" type="file" accept=".pdf,.jpeg,.jpg,.png" hidden
                        onchange="ChatAssistant.uploadEvidenceFromChat(this)">
                    <div id="chat-evidence-status" class="ca-action-status" aria-live="polite"></div>
                </div>`;
            return;
        }
        const title = terminalTitle(terminal);
        const viewAction = terminal?.outcome === 'incomplete_conversation'
            ? '' : '<a class="btn btn-primary" href="#/requests">View Request</a>';
        host.innerHTML = `
            <div class="ca-terminal-bar" data-ui-state="TERMINAL">
                <strong class="ca-terminal-title">${escapeHtml(title)}</strong>
                <div class="ca-terminal-actions">
                    ${viewAction}
                    <button class="btn btn-secondary" onclick="ChatAssistant.startNewConversation()">Start New Conversation</button>
                </div>
            </div>`;
    }

    function terminalTitle(terminal) {
        if (!terminal) return 'Request Complete';
        if (terminal.outcome === 'incomplete_conversation') return 'Conversation Closed';
        if (terminal.status === 'escalated' || terminal.decision === 'routed') return 'Sent for Manager Review';
        if (terminal.decision === 'approved') return 'Approved';
        if (terminal.decision === 'rejected') return 'Declined';
        return 'Request Submitted';
    }

    async function selectDomain(domain) {
        if (isProcessing || uiState !== STATES.DOMAIN_SELECTION) return;
        if (!DOMAINS.some(([value]) => value === domain)) return;
        selectedDomain = domain;
        const selected = DOMAINS.find(([value]) => value === domain);
        const inner = document.querySelector('.ca-welcome-inner');
        if (!inner) return;
        inner.innerHTML = `
            <div class="ca-hero-icon" aria-hidden="true">✦</div>
            <div class="ca-step-label">Step 2 of 2</div>
            <h1 class="ca-hero-title">Choose conversation language</h1>
            <p class="ca-hero-subtitle">Forge AI will use this language for every reply in ${escapeHtml(selected[1])}.</p>
            <div class="ca-quick-actions" id="ca-language-choices">
                <button class="ca-action-card" data-language-choice="en" onclick="ChatAssistant.selectLanguage('en')">
                    <span class="ca-action-text"><span class="ca-action-title">English</span>
                    <span class="ca-action-desc">All Forge AI replies will be in English</span></span>
                    <span class="ca-action-arrow" aria-hidden="true">→</span>
                </button>
                <button class="ca-action-card" data-language-choice="roman_urdu" onclick="ChatAssistant.selectLanguage('roman_urdu')">
                    <span class="ca-action-text"><span class="ca-action-title">Roman Urdu</span>
                    <span class="ca-action-desc">Tamam replies Roman Urdu mein hongay</span></span>
                    <span class="ca-action-arrow" aria-hidden="true">→</span>
                </button>
            </div>
            <button class="btn btn-ghost" onclick="ChatAssistant.backToDepartments()">Back to departments</button>`;
        setState(STATES.LANGUAGE_SELECTION, []);
    }

    async function selectLanguage(language) {
        if (isProcessing || uiState !== STATES.LANGUAGE_SELECTION || !selectedDomain) return;
        if (!['en', 'roman_urdu'].includes(language)) return;
        selectedLanguage = language;
        isProcessing = true;
        document.querySelectorAll('[data-language-choice]').forEach(button => { button.disabled = true; });
        try {
            const result = await API.startChatConversation(selectedDomain, selectedLanguage);
            conversationId = result.conversation_id;
            appendAssistant(result.message);
            applyServerResult(result);
        } catch (error) {
            App.toast(error.message || 'Could not start the conversation.', 'error');
            document.querySelectorAll('[data-language-choice]').forEach(button => { button.disabled = false; });
        } finally {
            isProcessing = false;
        }
    }

    function backToDepartments() {
        if (isProcessing || uiState !== STATES.LANGUAGE_SELECTION) return;
        const container = document.querySelector('.ca-layout')?.parentElement;
        if (container) render(container);
    }

    function appendUser(text) {
        const user = Auth.getUser();
        appendRow('user', Auth.getInitials(user.name), user.name, escapeHtml(text));
    }

    function appendAssistant(message) {
        appendRow('ai', '✦', 'Forge AI', formatMarkdown(message));
    }

    function appendRow(kind, avatar, name, html) {
        const messages = document.getElementById('ca-messages');
        const row = document.createElement('div');
        row.className = `ca-msg ca-msg-${kind}`;
        row.innerHTML = `<div class="ca-msg-avatar ca-avatar-${kind}">${escapeHtml(avatar)}</div>
            <div class="ca-msg-body"><div class="ca-msg-name">${escapeHtml(name)}</div>
            <div class="ca-msg-content ca-content-${kind}">${html}</div></div>`;
        messages.appendChild(row);
        messages.scrollTop = messages.scrollHeight;
    }

    function showTyping() {
        const messages = document.getElementById('ca-messages');
        const row = document.createElement('div');
        row.id = 'ca-typing';
        row.className = 'ca-msg ca-msg-ai';
        row.innerHTML = '<div class="ca-msg-avatar ca-avatar-ai">✦</div><div class="ca-msg-body"><div class="ca-msg-name">Forge AI</div><div class="ca-msg-content ca-content-ai"><div class="ca-typing-dots"><span></span><span></span><span></span></div></div></div>';
        messages.appendChild(row);
    }

    function applyServerResult(result) {
        const nextState = result.ui_state;
        const actions = Array.isArray(result.allowed_actions) ? result.allowed_actions : [];
        if (nextState === STATES.ACTIVE_CHAT && (!actions.includes('send_message') || !actions.includes('use_microphone'))) {
            throw new Error('Invalid active-chat action contract');
        }
        if (nextState === STATES.EVIDENCE_GATE && (actions.length !== 2 || !actions.includes('upload_evidence') || !actions.includes('skip_evidence'))) {
            throw new Error('Invalid evidence action contract');
        }
        setState(nextState, actions, result.terminal);
    }

    async function sendUserMessage() {
        if (isProcessing || uiState !== STATES.ACTIVE_CHAT || !allowedActions.includes('send_message')) return;
        const input = document.getElementById('chat-input');
        const text = input?.value.trim();
        if (!text || !conversationId) return;
        input.value = '';
        isProcessing = true;
        input.disabled = true;
        document.getElementById('chat-send-btn').disabled = true;
        document.getElementById('chat-mic-btn').disabled = true;
        appendUser(text);
        showTyping();
        try {
            const result = await API.sendChatAssistant(text, conversationId);
            document.getElementById('ca-typing')?.remove();
            appendAssistant(result.message);
            applyServerResult(result);
        } catch (error) {
            document.getElementById('ca-typing')?.remove();
            appendAssistant(error.message || 'Something went wrong. Please try again.');
        } finally {
            isProcessing = false;
            if (uiState === STATES.ACTIVE_CHAT) {
                const activeInput = document.getElementById('chat-input');
                if (activeInput) activeInput.disabled = false;
                const send = document.getElementById('chat-send-btn');
                const mic = document.getElementById('chat-mic-btn');
                if (send) send.disabled = false;
                if (mic) mic.disabled = false;
                activeInput?.focus();
            }
        }
    }

    function chooseEvidenceFile() {
        if (uiState !== STATES.EVIDENCE_GATE || !allowedActions.includes('upload_evidence')) return;
        document.getElementById('chat-evidence-file')?.click();
    }

    async function uploadEvidenceFromChat(fileInput) {
        if (isProcessing || uiState !== STATES.EVIDENCE_GATE || !fileInput.files?.[0]) return;
        const file = fileInput.files[0];
        const status = document.getElementById('chat-evidence-status');
        if (file.size > 5 * 1024 * 1024) {
            status.textContent = 'The file must be no larger than 5MB.';
            return;
        }
        isProcessing = true;
        status.textContent = 'Uploading evidence…';
        document.querySelectorAll('[data-primary-action]').forEach(button => { button.disabled = true; });
        try {
            const result = await API.uploadChatEvidence(conversationId, file);
            appendAssistant(result.message);
            applyServerResult(result);
        } catch (error) {
            status.textContent = `Upload failed: ${error.message}`;
            fileInput.value = '';
            document.querySelectorAll('[data-primary-action]').forEach(button => { button.disabled = false; });
        } finally {
            isProcessing = false;
        }
    }

    async function skipEvidence() {
        if (isProcessing || uiState !== STATES.EVIDENCE_GATE || !allowedActions.includes('skip_evidence')) return;
        isProcessing = true;
        document.querySelectorAll('[data-primary-action]').forEach(button => { button.disabled = true; });
        try {
            const result = await API.skipChatEvidence(conversationId);
            appendAssistant(result.message);
            applyServerResult(result);
        } catch (error) {
            const status = document.getElementById('chat-evidence-status');
            if (status) status.textContent = error.message || 'Could not skip evidence.';
            document.querySelectorAll('[data-primary-action]').forEach(button => { button.disabled = false; });
        } finally {
            isProcessing = false;
        }
    }

    function startNewConversation() {
        if (uiState !== STATES.TERMINAL) return;
        const container = document.querySelector('.ca-layout')?.parentElement;
        if (container) render(container);
    }

    async function toggleRecording() {
        if (uiState !== STATES.ACTIVE_CHAT || !allowedActions.includes('use_microphone')) return;
        if (isRecording) return stopRecording();
        if (!('webkitSpeechRecognition' in window)) {
            alert('Speech input is available in Chrome or Edge.');
            return;
        }
        const input = document.getElementById('chat-input');
        const mic = document.getElementById('chat-mic-btn');
        isRecording = true;
        currentTextBase = input.value;
        input.disabled = true;
        mic.classList.add('is-recording');
        recognition = new webkitSpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = selectedLanguage === 'roman_urdu' ? 'ur-PK' : 'en-US';
        recognition.onresult = event => {
            let finalText = '', interim = '';
            for (let i = event.resultIndex; i < event.results.length; i += 1) {
                if (event.results[i].isFinal) finalText += event.results[i][0].transcript;
                else interim += event.results[i][0].transcript;
            }
            if (finalText) currentTextBase = `${currentTextBase} ${finalText}`.trim();
            input.value = `${currentTextBase} ${interim}`.trim();
        };
        recognition.onerror = stopRecording;
        recognition.onend = stopRecording;
        recognition.start();
    }

    function stopRecording() {
        if (!isRecording) return;
        isRecording = false;
        recognition?.stop();
        recognition = null;
        const input = document.getElementById('chat-input');
        document.getElementById('chat-mic-btn')?.classList.remove('is-recording');
        if (uiState === STATES.ACTIVE_CHAT && input) {
            input.disabled = false;
            if (input.value.trim()) sendUserMessage();
        }
    }

    function escapeHtml(value) {
        return String(value ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }
    function formatMarkdown(text) {
        return escapeHtml(text).replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>').replace(/\n/g, '<br>');
    }

    return {
        STATES, render, setState, selectDomain, selectLanguage, backToDepartments,
        sendUserMessage, chooseEvidenceFile,
        uploadEvidenceFromChat, skipEvidence, startNewConversation, toggleRecording,
        terminalTitle, getState: () => ({
            uiState, allowedActions: [...allowedActions], conversationId,
            selectedDomain, selectedLanguage,
        }),
    };
})();
