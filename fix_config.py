import os

def fix_config():
    with open("utils/config.py", "r", encoding="utf-8") as f:
        content = f.read()
        
    old_chroma = 'CHROMA_PERSIST_DIR: str = _get("CHROMA_DB_PATH", _get("CHROMA_PERSIST_DIR", "./data/chromadb"))'
    
    new_chroma = '''PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _make_absolute(path: str) -> str:
    if path.startswith("./"):
        return os.path.join(PROJECT_ROOT, path[2:])
    if not os.path.isabs(path):
        return os.path.join(PROJECT_ROOT, path)
    return path

CHROMA_PERSIST_DIR: str = _make_absolute(_get("CHROMA_DB_PATH", _get("CHROMA_PERSIST_DIR", "./data/chromadb")))'''
    
    content = content.replace(old_chroma, new_chroma)
    
    # Also fix AUDIT_LOG_PATH
    old_audit = 'AUDIT_LOG_PATH: str = _get("AUDIT_LOG_PATH", "./data/phantom_audit.jsonl")'
    new_audit = 'AUDIT_LOG_PATH: str = _make_absolute(_get("AUDIT_LOG_PATH", "./data/phantom_audit.jsonl"))'
    content = content.replace(old_audit, new_audit)
    
    with open("utils/config.py", "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    fix_config()
    print("Done")
