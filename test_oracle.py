"""
HELIX -- Oracle Integration Test
Tests each configured provider with a real query.
"""
import sys, time
sys.path.insert(0, r"C:\HELIX")

from core.oracle.cloud import CloudOracle, _openai_compat_query
from config.settings import GROQ_API_KEY, DEEPSEEK_API_KEY, OPENROUTER_API_KEY, GEMINI_API_KEY

TEST_PROMPT = "In one sentence, what is artificial intelligence?"

SEP = "-" * 55

def test_provider(name, fn):
    print(f"\n[TEST] {name}")
    print(SEP)
    try:
        t0 = time.time()
        result = fn()
        elapsed = time.time() - t0
        snippet = result[:200].replace("\n", " ")
        print(f"  [OK]  ({elapsed:.2f}s)")
        print(f"  ->  {snippet}")
    except Exception as e:
        print(f"  [FAIL]  FAILED: {str(e)[:120]}")

print(SEP)
print("  HELIX Cloud Oracle -- Provider Test")
print(SEP)

# ── Individual provider tests ──────────────────────────────
test_provider("Groq (llama-3.3-70b-versatile)", lambda: _openai_compat_query(
    "https://api.groq.com/openai/v1", GROQ_API_KEY,
    "llama-3.3-70b-versatile", TEST_PROMPT
))

test_provider("DeepSeek (deepseek-chat)", lambda: _openai_compat_query(
    "https://api.deepseek.com", DEEPSEEK_API_KEY,
    "deepseek-chat", TEST_PROMPT
))

test_provider("OpenRouter (gemma-4-31b-it:free)", lambda: _openai_compat_query(
    "https://openrouter.ai/api/v1", OPENROUTER_API_KEY,
    "google/gemma-4-31b-it:free", TEST_PROMPT
))

# ── Full fallback chain test ───────────────────────────────
print(f"\n[TEST] Full Fallback Chain (auto-selects best provider)")
print(SEP)
oracle = CloudOracle()
print(f"  Configured: {oracle.status()}")
t0 = time.time()
result = oracle.query(TEST_PROMPT)
elapsed = time.time() - t0
snippet = result[:200].replace("\n", " ")
print(f"  [OK]  Active provider: {oracle.active_provider}  ({elapsed:.2f}s)")
print(f"  ->  {snippet}")

print(f"\n{SEP}")
print("  Test complete.")
print(SEP)
