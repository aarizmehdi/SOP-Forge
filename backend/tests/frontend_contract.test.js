// Source-level production frontend contracts. Run from the repository root.
const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const repositoryRoot = path.resolve(__dirname, '..', '..');
const sourcePath = value => path.join(repositoryRoot, value);
const read = value => fs.readFileSync(sourcePath(value), 'utf8');

test('frontend has one React/Vite entrypoint with strict TypeScript', () => {
  assert.match(read('frontend/index.html'), /src="\/src\/main\.tsx"/);
  assert.match(read('frontend/tsconfig.json'), /"strict": true/);
  assert.equal(fs.existsSync(sourcePath('frontend/js')), false);
  assert.equal(fs.existsSync(sourcePath('frontend/index.css')), false);
});
test('central client attaches bearer auth to JSON and multipart requests', () => {
  const source = read('frontend/src/lib/api.ts');
  assert.match(source, /headers\.set\(["']Authorization["'], `Bearer \$\{token\}`\)/);
  assert.match(source, /init\.body instanceof FormData/);
  assert.match(source, /form\.append\(["']file["'], file\)/);
  assert.match(source, /response\.status === 401/);
  assert.match(source, /openEvidence/);
});
test('chat follows the authoritative five-state contract', () => {
  const source = read('frontend/src/pages/ChatPage.tsx');
  for (const state of ['DOMAIN_SELECTION','LANGUAGE_SELECTION','ACTIVE_CHAT','EVIDENCE_GATE','TERMINAL']) assert.match(source, new RegExp(state));
  assert.match(source, /result\.ui_state/); assert.match(source, /result\.allowed_actions/);
  assert.match(source, /upload_evidence/); assert.match(source, /skip_evidence/);
  for (const domain of ['leave_hr','expenses_finance','it_system_access','policies_general']) assert.ok(source.includes(domain), `missing ${domain}`);
});
test('all preserved backend workflows are represented in the typed client', () => {
  const source = read('frontend/src/lib/api.ts');
  for (const path of ['/api/auth/login','/api/request/submit','/api/request/assistant/start','/api/review/pending','/api/audit/logs','/api/incidents','/api/admin/sop','/api/evidence/file','/api/speech/token']) assert.ok(source.includes(path), `missing ${path}`);
});
test('production targets preserve Vercel API proxy and FastAPI dist serving', () => {
  const vercel = read('frontend/vercel.json'); const backend = read('backend/app/main.py');
  assert.match(vercel, /sop-forge-production\.up\.railway\.app\/api/);
  assert.match(vercel, /"outputDirectory": "dist"/); assert.match(backend, /"frontend", "dist"/);
});
test('transaction cleanup is dry-run by default and preserves policy data', () => {
  const source = read('scripts/maintenance/clear_test_transactional_data.py');
  assert.match(source, /CLEAR-TEST-TRANSACTIONAL-DATA/); assert.match(source, /if args\.confirm != CONFIRMATION/);
  assert.doesNotMatch(source, /database\.(users|departments|sop_documents|sop_chunks)\.delete/);
});
