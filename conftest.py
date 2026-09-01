# Root-level pytest configuration for Project HELIX.
# test_fastpath.py is a Phase 3 script-style test (runs checks at import time
# and calls sys.exit). Exclude it from pytest collection so it doesn't crash
# the test runner. Run it directly: python tests/test_fastpath.py
collect_ignore = ["tests/test_fastpath.py"]
