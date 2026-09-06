// Run with node --test backend/tests/frontend_contract.test.js from repository root.
const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const vm = require('node:vm');

function loadEscapeHtml() {
    const source = fs.readFileSync('frontend/js/app.js', 'utf8');
    const start = source.indexOf('    function escapeHtml(');
    const end = source.indexOf('\n\n    return', start);
    const sandbox = {};
    vm.createContext(sandbox);
    vm.runInContext(source.slice(start, end) + '\nglobalThis.escapeHtml = escapeHtml;', sandbox);
    return sandbox.escapeHtml;
}

test('chat sends only message and owned conversation identifier', async () => {
    let sent;
    const sandbox = { window: {location: {origin: 'http://test'}}, localStorage: {getItem: () => 'test-token'},
        fetch: async (url, opts) => {sent = {url, opts}; return {ok: true, status: 200, json: async () => ({})};} };
    vm.createContext(sandbox);
    vm.runInContext(fs.readFileSync('frontend/js/api.js', 'utf8') + '\nglobalThis.api = API;', sandbox);
    await sandbox.api.sendChatAssistant('four days', 'draft-id');
    assert.deepEqual(JSON.parse(sent.opts.body), {message: 'four days', conversation_id: 'draft-id'});
    assert.equal(sent.opts.headers.Authorization, 'Bearer test-token');
});

test('manager evidence viewing includes authentication and uses backend response bytes', async () => {
    let sent;
    const viewer = {location: {}, close() {}};
    const sandbox = { window: {open: () => viewer}, Auth: {getToken: () => 'test-token'},
        fetch: async (url, opts) => {sent = {url, opts}; return {ok: true, blob: async () => 'file-bytes'};},
        URL: {createObjectURL: blob => {assert.equal(blob, 'file-bytes'); return 'blob:test';}, revokeObjectURL() {}},
        setTimeout() {}, App: {toast() {throw new Error('unexpected toast');}} };
    vm.createContext(sandbox);
    vm.runInContext(fs.readFileSync('frontend/js/components/review-panel.js', 'utf8') + '\nglobalThis.panel = ReviewPanel;', sandbox);
    await sandbox.panel.openEvidence('evidence-id');
    assert.equal(sent.opts.headers.Authorization, 'Bearer test-token');
    assert.equal(viewer.location.href, 'blob:test');
    assert.equal(viewer.opener, null);
});

test('employee evidence viewing includes authentication and uses size_bytes contract', async () => {
    let sent;
    const viewer = {location: {}, close() {}};
    const sandbox = { window: {open: () => viewer}, Auth: {getToken: () => 'employee-token'},
        fetch: async (url, opts) => {sent = {url, opts}; return {ok: true, blob: async () => 'employee-file'};},
        URL: {createObjectURL: blob => {assert.equal(blob, 'employee-file'); return 'blob:employee';}, revokeObjectURL() {}},
        setTimeout() {}, document: {createElement: () => ({click() {}})}, App: {toast() {throw new Error('unexpected toast');}} };
    vm.createContext(sandbox);
    vm.runInContext(fs.readFileSync('frontend/js/components/my-requests.js', 'utf8') + '\nglobalThis.requests = MyRequests;', sandbox);
    await sandbox.requests.openEvidence('evidence-id');
    assert.equal(sent.url, '/api/evidence/file/evidence-id');
    assert.equal(sent.opts.headers.Authorization, 'Bearer employee-token');
    assert.equal(viewer.location.href, 'blob:employee');
    assert.equal(viewer.opener, null);
    assert.match(fs.readFileSync('frontend/js/components/my-requests.js', 'utf8'), /ev\.size_bytes/);
});

test('manager review rendering escapes employee-controlled fields', async () => {
    const escapeHtml = loadEscapeHtml();
    const list = {innerHTML: ''};
    const malicious = '<img src=x onerror=globalThis.pwned=true>';
    const sandbox = {
        Auth: {getUser: () => ({role: 'manager'}), hasMinRole: () => false},
        API: {getPendingReviews: async () => [{
            id: '00000000-0000-0000-0000-000000000001', employee_name: malicious,
            employee_id_code: malicious, department: malicious, request_type: 'leave', status: 'escalated',
            ai_decision: 'routed', created_at: '2026-09-06T00:00:00Z', sla_remaining_minutes: 30,
            submitted_data: {leave_type: 'annual', start_date: '2026-09-07', end_date: '2026-09-07', reason: malicious},
            evaluation_reasoning: malicious, policy_refs: [malicious], has_evidence: false,
            override_log: [{by_name: malicious, justification: malicious}]
        }]},
        App: {escapeHtml},
        document: {getElementById: id => id === 'review-list' ? list : null, querySelectorAll: () => []},
        setTimeout() {}
    };
    vm.createContext(sandbox);
    vm.runInContext(fs.readFileSync('frontend/js/components/review-panel.js', 'utf8') + '\nglobalThis.panel = ReviewPanel;', sandbox);
    await sandbox.panel.render({innerHTML: ''});
    await new Promise(resolve => setImmediate(resolve));
    assert.doesNotMatch(list.innerHTML, /<img/i);
    assert.match(list.innerHTML, /&lt;img/);
});

test('employee request detail escapes content and renders authenticated evidence action', async () => {
    const escapeHtml = loadEscapeHtml();
    const malicious = '</textarea><script>globalThis.pwned=true</script>';
    let overlay;
    const sandbox = {
        API: {getRequest: async () => ({
            id: '00000000-0000-0000-0000-000000000001', request_type: 'leave', status: 'escalated', decision: 'routed',
            created_at: '2026-09-06T00:00:00Z', submitted_data: {leave_type: 'annual', reason: malicious},
            has_evidence: true, evidence_list: [{id: '00000000-0000-0000-0000-000000000002', original_filename: malicious, size_bytes: 2048}]
        })},
        App: {escapeHtml, toast() {}}, Auth: {getToken: () => 'token'}, window: {open: () => null},
        document: {createElement: () => ({innerHTML: '', className: '', addEventListener() {}}), body: {appendChild: value => {overlay = value;}}, querySelectorAll: () => []},
        setTimeout() {}, URL: {createObjectURL: () => 'blob:test', revokeObjectURL() {}}
    };
    vm.createContext(sandbox);
    vm.runInContext(fs.readFileSync('frontend/js/components/my-requests.js', 'utf8') + '\nglobalThis.requests = MyRequests;', sandbox);
    await sandbox.requests.viewDetail('00000000-0000-0000-0000-000000000001');
    assert.doesNotMatch(overlay.innerHTML, /<script/i);
    assert.match(overlay.innerHTML, /&lt;script/);
    assert.match(overlay.innerHTML, /MyRequests\.openEvidence/);
    assert.match(overlay.innerHTML, /\(2 KB\)/);
});

test('overridden decisions retain truthful employee status', () => {
    const source = fs.readFileSync('frontend/js/components/my-requests.js', 'utf8');
    const start = source.indexOf('    function getStatusInfo(');
    const end = source.indexOf('    function getTypeLabel(', start);
    const sandbox = {};
    vm.createContext(sandbox);
    vm.runInContext(source.slice(start, end) + '\nglobalThis.statusInfo = getStatusInfo;', sandbox);
    assert.equal(sandbox.statusInfo('overridden', 'approved').label, 'Approved');
    assert.equal(sandbox.statusInfo('overridden', 'rejected').label, 'Declined');
    assert.equal(sandbox.statusInfo('escalated', 'routed').label, 'Under Review');
});

function loadChatAssistant() {
    const controls = {innerHTML: ''};
    const sandbox = {
        Auth: {getUser: () => ({name: 'Test Employee'}), getInitials: () => 'TE'},
        API: {}, App: {toast() {}}, alert() {}, FormData: class {},
        document: {
            getElementById: id => id === 'ca-controls' ? controls : null,
            querySelectorAll: () => [],
            querySelector: () => null,
            createElement: () => ({innerHTML: '', className: ''}),
        },
        window: {},
    };
    vm.createContext(sandbox);
    vm.runInContext(fs.readFileSync('frontend/js/components/chat-assistant.js', 'utf8') + '\nglobalThis.chat = ChatAssistant;', sandbox);
    return {chat: sandbox.chat, controls, sandbox};
}

test('domain selection renders four choices without a composer', async () => {
    const {chat} = loadChatAssistant();
    const container = {innerHTML: ''};
    await chat.render(container);
    assert.equal((container.innerHTML.match(/data-domain-choice=/g) || []).length, 4);
    assert.doesNotMatch(container.innerHTML, /id="chat-input"/);
    assert.equal(chat.getState().uiState, 'DOMAIN_SELECTION');
});

test('evidence gate renders exactly upload and skip primary actions', () => {
    const {chat, controls} = loadChatAssistant();
    chat.setState('EVIDENCE_GATE', ['upload_evidence', 'skip_evidence']);
    assert.equal((controls.innerHTML.match(/data-primary-action=/g) || []).length, 2);
    assert.match(controls.innerHTML, />Upload Evidence</);
    assert.match(controls.innerHTML, />Skip Evidence</);
    assert.doesNotMatch(controls.innerHTML, /id="chat-input"|chat-mic-btn|chat-send-btn/);
});

test('terminal controls omit composer and title comes from authoritative result', () => {
    const {chat, controls} = loadChatAssistant();
    chat.setState('TERMINAL', ['view_request', 'start_new_conversation']);
    assert.doesNotMatch(controls.innerHTML, /id="chat-input"|chat-mic-btn|chat-send-btn/);
    assert.equal(chat.terminalTitle({status: 'escalated', decision: 'routed'}), 'Sent for Manager Review');
    assert.equal(chat.terminalTitle({status: 'resolved', decision: 'approved'}), 'Approved');
});

test('API starts domains and skips evidence through explicit transactions', async () => {
    const calls = [];
    const sandbox = {
        window: {location: {origin: 'http://test'}},
        localStorage: {getItem: () => 'test-token'},
        fetch: async (url, opts) => {
            calls.push({url, body: opts.body ? JSON.parse(opts.body) : null});
            return {ok: true, status: 200, json: async () => ({})};
        },
    };
    vm.createContext(sandbox);
    vm.runInContext(fs.readFileSync('frontend/js/api.js', 'utf8') + '\nglobalThis.api = API;', sandbox);
    await sandbox.api.startChatConversation('leave_hr');
    await sandbox.api.skipChatEvidence('conversation-id');
    assert.deepEqual(calls[0].body, {domain: 'leave_hr'});
    assert.equal(calls[1].url, 'http://test/api/evidence/draft/conversation-id/skip');
    assert.equal(calls[1].body, null);
});
