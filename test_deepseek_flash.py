#!/usr/bin/env python3
# Test deepseek/deepseek-v4-flash via Nous Portal (correct token path)
import json, httpx
from pathlib import Path

auth_path = Path.home() / "AppData" / "Local" / "hermes" / "profiles" / "hermes-agent-os" / "auth.json"
data = json.loads(auth_path.read_text(encoding="utf-8"))
nous = (data.get("providers", {}) or {}).get("nous", {})
token = nous.get("agent_key") or nous.get("access_token") or ""
print(f"Token found: {len(token)} chars")

r = httpx.post(
    "https://inference-api.nousresearch.com/v1/chat/completions",
    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    json={"model": "deepseek/deepseek-v4-flash", "messages": [{"role": "user", "content": "Reply with exactly: FLASH_OK"}]},
    timeout=45
)
d = r.json()
print(f"HTTP {r.status_code} | model=deepseek/deepseek-v4-flash")
if r.status_code == 200:
    reply = d["choices"][0]["message"]["content"].strip()
    print(f"Reply: {reply}")
    print(f"Tokens: {d.get('usage', {}).get('total_tokens', '?')}")
    print("✅ deepseek/deepseek-v4-flash ACTIVE via Nous Portal")
else:
    print(f"❌ Error: {d.get('error', d)}")
