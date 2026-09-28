#!/usr/bin/env python3
"""Test pipeline LLM : matching + CV + LM ATS (Nous Portal cloud)"""
import sys, os, time
ONESHOT = "C:/Users/pixel/AppData/Local/Temp/Oneshot-tmp"
sys.path.insert(0, ONESHOT)
os.environ["PYTHONPATH"] = ONESHOT
os.chdir(ONESHOT)

from config.settings import settings
from core.llm.llm_client import llm_client
from core.llm.job_evaluator import job_evaluator
from core.documents.cv_builder import prioritize_skills, build_tailored_summary
from core.documents.cover_letter_builder import build_cover_letter_text, build_cover_letter_pdf

profile = settings.load_profile()
criteria = settings.load_search_criteria()
desc = "Developpeur Python Django, 3 ans d experience, PostgreSQL, Docker, API REST, salaire 40k-50k Paris"

print(f"LLM: available={llm_client.available} provider={llm_client.provider} model={llm_client.model_name}")
print(f"Profile: {profile.first_name} {profile.last_name} email={profile.email}")
print(f"Skills: {profile.skills[:6]}")

# 1. ATS keywords (deterministic)
t0 = time.time()
skills = prioritize_skills(profile, "Développeur Python", desc)
print(f"1. ATS skills ({time.time()-t0:.1f}s): {skills[:8]}")

# 2. Tailored summary
summary = build_tailored_summary(profile, "Développeur Python", desc)
print(f"2. Summary: {summary[:120]}")

# 3. Job evaluation (LLM Nous Portal) — use evaluate_job (correct wrapper)
t0 = time.time()
result = job_evaluator.evaluate_job("Développeur Python", "TechCorp", desc, profile, criteria)
print(f"3. Job eval ({time.time()-t0:.1f}s): score={result.score} match={result.is_match}")
print(f"   rationale: {result.rationale[:100]}")

# 4. Cover letter text (LLM)
t0 = time.time()
cl = build_cover_letter_text(profile, "Développeur Python", "TechCorp", desc, "Paris")
print(f"4. Cover letter ({time.time()-t0:.1f}s): {len(cl)} chars")
print(f"   preview: {cl[:120].replace(chr(10),' ')}")

# 5. Cover letter PDF
t0 = time.time()
pdf = build_cover_letter_pdf(profile, "Développeur Python", "TechCorp", desc, "Paris")
print(f"5. PDF: {pdf} ({time.time()-t0:.1f}s)")
print("=== PIPELINE OK ===")
