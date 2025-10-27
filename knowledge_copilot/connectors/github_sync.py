from __future__ import annotations
import os
import re
import json
import shutil
import hashlib
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple
import nbformat
from dotenv import load_dotenv

# Charger .env
print(f"Loading .env file for GitHub sync... : {Path(__file__).resolve().parents[2] / '.env'}")
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

# ---------- Config lecture ----------
GH_PAT = os.getenv("GH_PAT", "")
GH_REPOS = [r.strip() for r in os.getenv("GH_REPOS", "").split(",") if r.strip()]
GH_DEFAULT_BRANCH = os.getenv("GH_DEFAULT_BRANCH", "main")
MAX_FILE_MB = float(os.getenv("MAX_FILE_MB", "2"))  # coupe > 2 Mo par défaut

# Dossiers / patterns ignorés
IGNORE_DIRS = {".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__"}
# Extensions "binaires" à ignorer (ajuste au besoin)
BINARY_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp",
    ".pdf", ".zip", ".tar", ".gz", ".rar", ".7z",
    ".so", ".dylib", ".dll", ".exe", ".bin"
}

# ---------- Utils ----------
def sha256_text(text: str) -> str:
    h = hashlib.sha256()
    h.update(text.encode("utf-8", errors="ignore"))
    return h.hexdigest()

def is_binary_path(p: Path) -> bool:
    return p.suffix.lower() in BINARY_EXT

def safe_read_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

def extract_from_py(source: str) -> str:
    """
    Extrait docstrings + commentaires depuis un .py
    - Docstrings via AST (triple quotes)
    - Commentaires lignes commençant par #
    """
    import ast
    out_parts: List[str] = []
    try:
        tree = ast.parse(source)
        module_doc = ast.get_docstring(tree) or ""
        if module_doc:
            out_parts.append(module_doc)

        class FuncVisitor(ast.NodeVisitor):
            def visit_FunctionDef(self, node):
                doc = ast.get_docstring(node)
                if doc:
                    out_parts.append(doc)
                self.generic_visit(node)
            def visit_AsyncFunctionDef(self, node):
                doc = ast.get_docstring(node)
                if doc:
                    out_parts.append(doc)
                self.generic_visit(node)
            def visit_ClassDef(self, node):
                doc = ast.get_docstring(node)
                if doc:
                    out_parts.append(doc)
                self.generic_visit(node)

        FuncVisitor().visit(tree)
    except Exception:
        # en fallback on ne casse pas
        pass

    # commentaires "# ..."
    comments = []
    for line in source.splitlines():
        s = line.strip()
        if s.startswith("#"):
            # ignore shebang/env lines
            if s.startswith("#!") or s.startswith("# -*-"):
                continue
            comments.append(s.lstrip("# ").rstrip())

    if comments:
        out_parts.append("\n".join(comments))

    return "\n\n".join([p for p in out_parts if p.strip()])

def extract_from_ipynb(nb_path: Path) -> str:
    """
    Extrait Markdown + commentaires (# ...) des cellules code.
    """
    try:
        nb = nbformat.read(nb_path, as_version=4)
    except Exception:
        return ""
    parts: List[str] = []
    for cell in nb.cells:
        if cell.cell_type == "markdown":
            parts.append(cell.source or "")
        elif cell.cell_type == "code":
            comments = []
            for line in (cell.source or "").splitlines():
                s = line.strip()
                if s.startswith("#") and not s.startswith("#!"):
                    comments.append(s.lstrip("# ").rstrip())
            if comments:
                parts.append("\n".join(comments))
    return "\n\n".join([p for p in parts if p.strip()])

def should_keep_file(path: Path) -> bool:
    if any(part in IGNORE_DIRS for part in path.parts):
        return False
    if is_binary_path(path):
        return False
    if path.suffix.lower() not in {".md", ".py", ".ipynb"}:
        return False
    # taille max
    try:
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > MAX_FILE_MB:
            return False
    except Exception:
        pass
    return True

# ---------- Clonage shallow ----------
def shallow_clone(repo: str, branch: str, workdir: Path) -> Path:
    """
    Clone shallow une seule branche dans un dossier temporaire.
    repo: "org/name"
    """
    target = workdir / repo.replace("/", "_")
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
    target.parent.mkdir(parents=True, exist_ok=True)

    # URL https avec token pour lecture
    url = f"https://{GH_PAT}:x-oauth-basic@github.com/{repo}.git" if GH_PAT else f"https://github.com/{repo}.git"
    subprocess.check_call([
        "git", "clone", "--depth", "1", "--branch", branch, url, str(target)
    ])
    # enlever .git pour éviter scans inutiles
    shutil.rmtree(target / ".git", ignore_errors=True)
    return target

# ---------- Parcours & extraction ----------
def scan_repo_folder(root: Path, repo_full: str, branch: str) -> List[Dict]:
    docs: List[Dict] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if not should_keep_file(p):
            continue

        text = ""
        if p.suffix.lower() == ".md":
            text = safe_read_text(p)
        elif p.suffix.lower() == ".py":
            text = extract_from_py(safe_read_text(p))
        elif p.suffix.lower() == ".ipynb":
            text = extract_from_ipynb(p)
        if not text.strip():
            continue

        uri = f"github://{repo_full}@{branch}/{p.relative_to(root).as_posix()}"
        title = p.name
        mime = {
            ".md": "text/markdown",
            ".py": "text/x-python-comments",
            ".ipynb": "application/x-ipynb+comments"
        }.get(p.suffix.lower(), "text/plain")

        content_hash = sha256_text(text)

        docs.append({
            "source": "github",
            "uri": uri,
            "title": title,
            "mime": mime,
            "content_hash": content_hash,
            "raw_text": text,
            "metadata": {
                "repo": repo_full,
                "branch": branch,
                "path": p.relative_to(root).as_posix()
            }
        })
    return docs

# ---------- Chunking ----------
from ..utils.chunking import chunk_text

def to_chunks(doc: Dict, max_tokens=1000, overlap=100) -> List[Dict]:
    chunks = chunk_text(doc["raw_text"], max_tokens, overlap)
    out = []
    for i, ch in enumerate(chunks):
        # Calculer approx_tokens si pas présent
        approx_tokens = ch.get("approx_tokens", max(1, len(ch["text"]) // 4))
        
        out.append({
            "doc_content_hash": doc["content_hash"],
            "chunk_index": i,
            "text": ch["text"],
            "approx_tokens": approx_tokens,
            "metadata": {
                **doc["metadata"],
                "title": doc["title"],
                "mime": doc["mime"],
                "uri": doc["uri"]
            }
        })
    return out

# ---------- Entrée principale ----------
def sync_github(repos: List[str] | None = None, branch: str | None = None) -> Dict:
    repos = repos or GH_REPOS
    branch = branch or GH_DEFAULT_BRANCH
    assert repos, "Aucun repo GitHub fourni. Renseigne GH_REPOS ou passe une liste."

    workdir = Path(".cache/github")
    workdir.mkdir(parents=True, exist_ok=True)

    all_docs: List[Dict] = []
    for repo in repos:
        local = shallow_clone(repo, branch, workdir)
        docs = scan_repo_folder(local, repo, branch)
        all_docs.extend(docs)

    # dédoublonner par content_hash (si plusieurs repos contiennent la même doc)
    seen = set()
    dedup_docs = []
    for d in all_docs:
        if d["content_hash"] in seen:
            continue
        seen.add(d["content_hash"])
        dedup_docs.append(d)

    # transformer en chunks
    all_chunks: List[Dict] = []
    for d in dedup_docs:
        all_chunks.extend(to_chunks(d))

    return {
        "repos": repos,
        "branch": branch,
        "documents_count": len(dedup_docs),
        "chunks_count": len(all_chunks),
        "documents": dedup_docs,
        "chunks": all_chunks[:50],  # on renvoie un aperçu ; en pratique tu insères en DB
    }

# ---------- CLI ----------
if __name__ == "__main__":
    import typer
    app = typer.Typer(help="Sync GitHub repos -> documents/chunks")

    @app.command()
    def run(
        repos: str = typer.Option(None, help="Liste 'org/repo,org2/repo2' sinon GH_REPOS"),
        branch: str = typer.Option(None, help="Branche, sinon GH_DEFAULT_BRANCH"),
        dump_json: str = typer.Option(None, help="Chemin JSON pour sauvegarder l'aperçu"),
    ):
        repo_list = [r.strip() for r in repos.split(",")] if repos else None
        print(f"Sync GitHub repos: {repo_list or GH_REPOS} @ branch: {branch or GH_DEFAULT_BRANCH}")
        result = sync_github(repo_list, branch)
        if dump_json:
            Path(dump_json).write_text(json.dumps(result, ensure_ascii=False, indent=2))
            print(f"Wrote: {dump_json}")
        print(f"Docs: {result['documents_count']} | Chunks: {result['chunks_count']}")

    app()
