// Run with node --test backend/tests/frontend_contract.test.js from repository root.
const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const vm = require('node:vm');

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
