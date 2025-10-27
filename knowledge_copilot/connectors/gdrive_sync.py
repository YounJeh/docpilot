from __future__ import annotations
import os, io, json, hashlib, math, datetime as dt
from typing import List, Dict, Optional
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from pypdf import PdfReader  # pip install pypdf
from dotenv import load_dotenv

# Charger .env
print(f"Loading .env file for GitHub sync... : {Path(__file__).resolve().parents[2] / '.env'}")
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

# --------- Config ----------
GDRIVE_FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID", "")
MAX_FILE_MB = float(os.getenv("MAX_FILE_MB", "10"))  # limite taille downloads
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
INCLUDE_SUBFOLDERS = True # parcourir récursivement les sous-dossiers


IGNORE_MIME_PREFIXES = {
    "image/", "video/", "audio/"
}
TEXTUAL_DOWNLOADABLE = {
    "text/plain", "text/markdown"
}

# --------- Utils ----------
def load_drive_client() -> any:
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    assert cred_path and Path(cred_path).exists(), "GOOGLE_APPLICATION_CREDENTIALS introuvable"
    creds = Credentials.from_service_account_file(cred_path, scopes=SCOPES)
    return build("drive", "v3", credentials=creds, cache_discovery=False)

def sha256_text(text: str) -> str:
    h = hashlib.sha256()
    h.update(text.encode("utf-8", errors="ignore"))
    return h.hexdigest()

def approx_token_count(text: str) -> int:
    return max(1, math.ceil(len(text) / 4))

def chunk_text(text: str, max_tokens: int = 1000, overlap_tokens: int = 100) -> List[Dict]:
    if not text:
        return []
    max_chars = max_tokens * 4
    overlap_chars = overlap_tokens * 4
    n, start, out = len(text), 0, []
    while start < n:
        end = min(n, start + max_chars)
        chunk = text[start:end]
        out.append({"text": chunk, "approx_tokens": approx_token_count(chunk)})
        if end == n: break
        start = max(0, end - overlap_chars)
    return out

# --------- Extraction contenu ----------
def export_google_doc(drive, file_id: str, mime: str) -> str:
    # Docs -> text/plain ; Slides -> application/pdf (puis parse)
    if mime == "application/vnd.google-apps.document":
        request = drive.files().export(fileId=file_id, mimeType="text/plain")
        buf = io.BytesIO(request.execute())
        return buf.getvalue().decode("utf-8", errors="ignore")

    if mime == "application/vnd.google-apps.presentation":
        request = drive.files().export(fileId=file_id, mimeType="application/pdf")
        pdf_bytes = request.execute()
        return parse_pdf_bytes(pdf_bytes)

    # D'autres types Google (Sheets, Drawings) -> ignorer ou gérer plus tard
    return ""

def download_file_content(drive, file_id: str, size_limit_mb: float) -> bytes:
    request = drive.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
        # contrôle de taille
        if buf.tell() > size_limit_mb * 1024 * 1024:
            raise RuntimeError("Fichier trop volumineux")
    return buf.getvalue()

def parse_pdf_bytes(b: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(b))
        parts = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        return "\n".join(parts).strip()
    except Exception:
        return ""

def decode_text_bytes(b: bytes) -> str:
    return b.decode("utf-8", errors="ignore")

def should_skip_mime(mime: str) -> bool:
    if not mime: return True
    return any(mime.startswith(pref) for pref in IGNORE_MIME_PREFIXES)

# --------- Listing fichiers d'un dossier ----------
def list_folder_files(drive, folder_id: str) -> List[Dict]:
    q = f"'{folder_id}' in parents and trashed=false"
    fields = "nextPageToken, files(id,name,mimeType,modifiedTime,webViewLink,size)"
    items, page_token = [], None
    while True:
        resp = drive.files().list(q=q, spaces="drive", fields=fields, pageToken=page_token).execute()
        items.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return items

def list_children(drive, folder_id: str) -> List[Dict]:
    """Liste les ENFANTS directs d'un dossier (fichiers + sous-dossiers + shortcuts)."""
    q = f"'{folder_id}' in parents and trashed=false"
    # on demande les champs utiles + shortcutDetails
    fields = ("nextPageToken, files("
              "id,name,mimeType,modifiedTime,webViewLink,size,"
              "shortcutDetails/targetId,shortcutDetails/targetMimeType)")
    items, page_token = [], None
    while True:
        resp = drive.files().list(
            q=q, spaces="drive", fields=fields,
            pageToken=page_token,
            supportsAllDrives=True, includeItemsFromAllDrives=True,
            pageSize=1000
        ).execute()
        items.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return items

def list_tree_files(drive, root_folder_id: str) -> List[Dict]:
    """Parcourt récursivement tous les sous-dossiers et retourne tous les FICHIERS (pas les dossiers)."""
    queue = [root_folder_id]
    results = []
    seen_folders = set()
    while queue:
        fid = queue.pop(0)
        if fid in seen_folders:
            continue
        seen_folders.add(fid)
        children = list_children(drive, fid)
        for f in children:
            mime = f.get("mimeType", "")
            if mime == "application/vnd.google-apps.folder":
                if INCLUDE_SUBFOLDERS:
                    queue.append(f["id"])
                continue
            if mime == "application/vnd.google-apps.shortcut":
                # on remplace par la cible du raccourci
                target_id = f.get("shortcutDetails", {}).get("targetId")
                target_mime = f.get("shortcutDetails", {}).get("targetMimeType")
                if target_id and target_mime:
                    f = {
                        **f,
                        "id": target_id,
                        "mimeType": target_mime,
                        # garde le nom/links du raccourci si besoin
                    }
                else:
                    continue
            results.append(f)
    return results

# --------- Sync principale ----------
def sync_drive(folder_id: Optional[str] = None, max_tokens=1000, overlap=100) -> Dict:
    folder_id = folder_id or GDRIVE_FOLDER_ID
    assert folder_id, "GDRIVE_FOLDER_ID manquant"

    drive = load_drive_client()
    files = list_tree_files(drive, folder_id)

    documents, chunks = [], []
    now_iso = dt.datetime.utcnow().isoformat() + "Z"

    for f in files:
        fid, name, mime = f["id"], f.get("name",""), f.get("mimeType","")
        if should_skip_mime(mime):
            continue

        text = ""
        try:
            if mime.startswith("application/vnd.google-apps."):
                text = export_google_doc(drive, fid, mime)
            else:
                # Fichiers non-Google (pdf, md, txt, etc.)
                raw = download_file_content(drive, fid, MAX_FILE_MB)
                if mime == "application/pdf":
                    text = parse_pdf_bytes(raw)
                elif mime in TEXTUAL_DOWNLOADABLE or name.lower().endswith((".md",".txt",".py",".csv",".ipynb")):
                    text = decode_text_bytes(raw)
                else:
                    # on ignore les binaires/format non gérés
                    text = ""
        except Exception:
            continue

        text = (text or "").strip()
        if not text:
            continue

        content_hash = sha256_text(text)
        doc = {
            "source": "gdrive",
            "uri": f"gdrive://{fid}",
            "title": name,
            "mime": mime,
            "content_hash": content_hash,
            "raw_text": text,
            "metadata": {
                "drive_file_id": fid,
                "name": name,
                "mimeType": mime,
                "modifiedTime": f.get("modifiedTime"),
                "webViewLink": f.get("webViewLink"),
                "ingested_at": now_iso,
            }
        }
        documents.append(doc)

        # chunking
        for i, ch in enumerate(chunk_text(text, max_tokens=max_tokens, overlap_tokens=overlap)):
            chunks.append({
                "doc_content_hash": content_hash,
                "chunk_index": i,
                "text": ch["text"],
                "approx_tokens": ch["approx_tokens"],
                "metadata": {
                    **doc["metadata"],
                    "title": name,
                    "uri": f"gdrive://{fid}"
                }
            })

    # dédup par hash
    seen, dedup_docs = set(), []
    for d in documents:
        if d["content_hash"] in seen: continue
        seen.add(d["content_hash"]); dedup_docs.append(d)

    return {
        "folder_id": folder_id,
        "documents_count": len(dedup_docs),
        "chunks_count": len(chunks),
        "documents": dedup_docs,
        "chunks": chunks[:50],  # aperçu
    }

if __name__ == "__main__":
    import typer, json
    app = typer.Typer(help="Sync Google Drive folder -> documents/chunks")

    @app.command()
    def run(folder_id: str = "", dump_json: str = ""):
        res = sync_drive(folder_id or None)
        if dump_json:
            Path(dump_json).write_text(json.dumps(res, ensure_ascii=False, indent=2))
            print(f"Wrote: {dump_json}")
        print(f"Docs: {res['documents_count']} | Chunks: {res['chunks_count']}")

    app()
