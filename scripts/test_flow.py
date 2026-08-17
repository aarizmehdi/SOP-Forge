import urllib.request
import json

BASE_URL = "http://localhost:8000"

def post(path, data, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=json.dumps(data).encode(), headers=headers, method="POST")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

def get(path, token=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{BASE_URL}{path}", headers=headers, method="GET")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

print("1. Testing Health...")
health = get("/health")
print("Health:", health)

print("\n2. Logging in as Aisha Khan (Employee)...")
login_res = post("/api/auth/login", {"email": "aisha.khan@company.com", "password": "password123"})
token = login_res["access_token"]
print("Logged in! Token received. User:", login_res["name"], "| Role:", login_res["role"])

print("\n3. Submitting Leave Request (Annual Leave 3 days)...")
sub_res = post("/api/request/submit", {
    "request_type": "leave",
    "submitted_data": {
        "leave_type": "annual",
        "start_date": "2026-08-25",
        "end_date": "2026-08-27",
        "reason": "Family trip to northern areas for annual holiday",
        "half_day": False
    }
}, token=token)

req_id = sub_res["id"]
print("Submitted! Request ID:", req_id, "| Status:", sub_res["status"], "| Decision:", sub_res["decision"])

import time
print("Waiting for background AI workflow to complete...")
time.sleep(1.5)

print("\n4. Checking Request Status & AI Evaluation...")
req_detail = get(f"/api/request/{req_id}", token=token)
print("Decision:", req_detail["decision"])
print("Confidence:", req_detail["confidence"])
print("Status:", req_detail["status"])
print("Reasoning:", req_detail["evaluation_reasoning"])
print("Policy Refs:", req_detail["retrieved_policy_refs"])

print("\n5. Logging in as Bilal Hussain (Manager)...")
mgr_login = post("/api/auth/login", {"email": "bilal.hussain@company.com", "password": "password123"})
mgr_token = mgr_login["access_token"]

print("\n6. Checking Audit Logs as Manager...")
audit_logs = get("/api/audit/logs?limit=5", token=mgr_token)
print(f"Audit log entries count: {len(audit_logs)}")
for log in audit_logs:
    print(f"  - Event: {log['event_type']} | Decision: {log['decision']} | Actor: {log['actor_name'] or log['actor_role']}")

print("\n[SUCCESS] End-to-end verification completed clean!")
