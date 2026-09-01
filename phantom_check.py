"""
PHANTOM Diagnostic Script — checks all 10 dependencies.
Run: python phantom_check.py
"""

import sys
import traceback

results = {}  # component -> (status, note)


def check(name, fn):
    try:
        note = fn()
        results[name] = ("PASS", note or "")
        print(f"\n[PASS] {name}")
        if note:
            print(f"       {note}")
    except Exception as e:
        results[name] = ("FAIL", str(e))
        print(f"\n[FAIL] {name}")
        print(f"       Error: {e}")


# ── CHECK 1: Ollama running ───────────────────────────────────────────────────
def check_ollama():
    import requests
    r = requests.get("http://localhost:11434", timeout=5)
    body = r.text
    assert r.status_code == 200 or "Ollama" in body or "ollama" in body.lower(), \
        f"Unexpected response: {r.status_code} — {body[:100]}"
    return f"HTTP {r.status_code}"

check("Ollama running", check_ollama)


# ── CHECK 2: Model available ──────────────────────────────────────────────────
def check_model():
    import requests
    r = requests.get("http://localhost:11434/api/tags", timeout=5)
    data = r.json()
    models = [m["name"] for m in data.get("models", [])]
    print(f"       Models found: {models}")
    targets = ["llama3", "qwen", "mistral", "llama", "gemma", "phi"]
    matched = [m for m in models if any(t in m.lower() for t in targets)]
    assert matched, f"No expected model found. Installed: {models}"
    return f"Found: {matched}"

check("Model available", check_model)


# ── CHECK 3: Presidio ────────────────────────────────────────────────────────
def check_presidio():
    from presidio_analyzer import AnalyzerEngine
    analyzer = AnalyzerEngine()
    results_pii = analyzer.analyze(
        text="My name is Tanmay and my email is test@test.com",
        language="en"
    )
    entities = [(r.entity_type, round(r.score, 2)) for r in results_pii]
    print(f"       Entities: {entities}")
    types = [r.entity_type for r in results_pii]
    assert "PERSON" in types or "EMAIL_ADDRESS" in types, \
        f"Expected PERSON or EMAIL_ADDRESS, got: {types}"
    return f"Detected: {types}"

check("Presidio", check_presidio)


# ── CHECK 4: spaCy ───────────────────────────────────────────────────────────
def check_spacy():
    import spacy
    nlp = spacy.load("en_core_web_sm")
    doc = nlp("Rahul lives in Bengaluru.")
    ents = [(ent.text, ent.label_) for ent in doc.ents]
    print(f"       Entities: {ents}")
    labels = [e[1] for e in ents]
    assert "PERSON" in labels or "GPE" in labels, \
        f"Expected PERSON or GPE, got: {labels}"
    return f"Found: {ents}"

check("spaCy en_core_web_sm", check_spacy)


# ── CHECK 5: ChromaDB ────────────────────────────────────────────────────────
def check_chromadb():
    import chromadb
    client = chromadb.Client()
    col = client.create_collection("test_check")
    col.add(documents=["hello world"], ids=["1"])
    res = col.query(query_texts=["hello"], n_results=1)
    docs = res["documents"][0]
    print(f"       Query result: {docs}")
    client.delete_collection("test_check")
    assert "hello world" in docs, f"Expected 'hello world', got: {docs}"
    return f"Returned: {docs}"

check("ChromaDB", check_chromadb)


# ── CHECK 6: sentence-transformers ───────────────────────────────────────────
def check_sentence_transformers():
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")
    emb = model.encode("test sentence")
    print(f"       Embedding shape: {emb.shape}")
    assert emb.shape == (384,), f"Expected shape (384,), got {emb.shape}"
    return f"Shape: {emb.shape}"

check("sentence-transformers", check_sentence_transformers)


# ── CHECK 7: LangGraph ───────────────────────────────────────────────────────
def check_langgraph():
    from langgraph.graph import StateGraph, END
    from langgraph.checkpoint.memory import MemorySaver
    from typing import TypedDict

    class S(TypedDict):
        val: str

    g = StateGraph(S)
    g.add_node("n", lambda s: {"val": "ok"})
    g.set_entry_point("n")
    g.add_edge("n", END)
    app = g.compile(checkpointer=MemorySaver())
    out = app.invoke(
        {"val": ""},
        config={"configurable": {"thread_id": "t1"}}
    )
    print(f"       Output: {out}")
    assert out.get("val") == "ok", f"Expected val='ok', got: {out}"
    return f"Output: {out}"

check("LangGraph", check_langgraph)


# ── CHECK 8: langchain-ollama ─────────────────────────────────────────────────
def check_langchain_ollama():
    from langchain_ollama import ChatOllama
    import requests

    # Find the best available model first
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        models = [m["name"] for m in r.json().get("models", [])]
    except Exception:
        models = []

    targets = ["llama3", "qwen", "mistral", "gemma", "phi", "llama"]
    model_name = next(
        (m for m in models if any(t in m.lower() for t in targets)),
        "llama3"  # fallback
    )
    print(f"       Using model: {model_name}")

    llm = ChatOllama(model=model_name, temperature=0)
    response = llm.invoke("Reply with the single word PASS only. No punctuation.")
    content = response.content if hasattr(response, "content") else str(response)
    print(f"       Response: {content!r}")
    assert content.strip(), "Empty response from LLM"
    return f"Response: {content.strip()[:50]}"

check("langchain-ollama", check_langchain_ollama)


# ── CHECK 9: PyQt6 ───────────────────────────────────────────────────────────
def check_pyqt6():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    assert app is not None, "QApplication could not be created"
    return "QApplication created"

check("PyQt6", check_pyqt6)


# ── CHECK 10: pyperclip ──────────────────────────────────────────────────────
def check_pyperclip():
    import pyperclip
    pyperclip.copy("phantom_test")
    val = pyperclip.paste()
    print(f"       Clipboard value: {val!r}")
    assert val == "phantom_test", f"Expected 'phantom_test', got: {val!r}"
    return f"Clipboard: {val!r}"

check("pyperclip", check_pyperclip)


# ── SUMMARY TABLE ─────────────────────────────────────────────────────────────
FIX_CMDS = {
    "Ollama running":        "Download from https://ollama.com and run: ollama serve",
    "Model available":       "ollama pull llama3.2:3b  (or: ollama pull qwen3:4b)",
    "Presidio":              "pip install presidio-analyzer presidio-anonymizer",
    "spaCy en_core_web_sm":  "pip install spacy && python -m spacy download en_core_web_sm",
    "ChromaDB":              "pip install chromadb",
    "sentence-transformers": "pip install sentence-transformers",
    "LangGraph":             "pip install langgraph",
    "langchain-ollama":      "pip install langchain-ollama",
    "PyQt6":                 "pip install PyQt6",
    "pyperclip":             "pip install pyperclip",
}

print("\n")
print("=" * 75)
print("  PHANTOM — Dependency Check Summary")
print("=" * 75)
header = f"{'Component':<28}| {'Status':<7}| Fix if FAIL"
print(header)
print("-" * 75)

all_pass = True
for component, fix in FIX_CMDS.items():
    status, note = results.get(component, ("NOT RUN", ""))
    if status != "PASS":
        all_pass = False
    fix_str = "" if status == "PASS" else fix
    print(f"{component:<28}| {status:<7}| {fix_str}")

print("=" * 75)
if all_pass:
    print("  ALL CHECKS PASSED — PHANTOM is ready to run.")
else:
    print("  SOME CHECKS FAILED — fix the above before running PHANTOM.")
print("=" * 75)
