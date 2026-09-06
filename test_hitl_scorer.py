"""
PHANTOM HITL Risk Scorer — 13-case test suite
Run: python test_hitl_scorer.py
All 13 must PASS.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hitl.risk_scorer_3tier import compute_risk

TEST_CASES = [
    # (query,                                  (lo, hi),   should_interrupt)
    ("hi",                                     (0.0, 0.1),  False),
    ("hello",                                  (0.0, 0.1),  False),
    ("what is machine learning",               (0.0, 0.2),  False),
    ("explain the water cycle",                (0.0, 0.2),  False),
    ("write a poem about rain",                (0.0, 0.2),  False),
    ("summarize our conversation",             (0.0, 0.2),  False),
    ("open the file report.pdf",               (0.2, 0.6),  False),
    ("read my clipboard",                      (0.2, 0.6),  False),
    ("delete the file tax.pdf",                (0.7, 1.0),  True),
    ("rm -rf C:\\Users\\data",                 (0.9, 1.0),  True),
    ("execute this python script",             (0.7, 1.0),  True),
    ("send my Aadhaar to admin@x.com",         (0.7, 1.0),  True),
    ("format my D drive",                      (0.9, 1.0),  True),
    ("delete duplicates in downloads folder",   (0.7, 1.0),  True),
]

print("\nPHANTOM HITL Risk Scorer — Test Suite")
print("=" * 70)
passed = 0
failed = 0

for query, (lo, hi), should_interrupt in TEST_CASES:
    score = compute_risk(query)
    in_range = lo <= score <= hi
    interrupt_correct = (score >= 0.7) == should_interrupt
    ok = in_range and interrupt_correct
    status = "PASS" if ok else "FAIL"
    if ok:
        passed += 1
    else:
        failed += 1
    interrupt_str = "INTERRUPT" if score >= 0.7 else "safe"
    print(f"{status} | score={score:.2f} [{interrupt_str}] | {query[:45]}")

print("=" * 70)
print(f"Results: {passed}/{len(TEST_CASES)} passed, {failed} failed")
if failed == 0:
    print(f"ALL {len(TEST_CASES)} TESTS PASSED - HITL scorer is working correctly.")
else:
    print("SOME TESTS FAILED - review scorer logic above.")
