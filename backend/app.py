"""
Activity Tracker – Backend
Hanterar registrering, feedback och OTA-uppdateringar.
Deploy: Railway.app
"""

import os
import sqlite3
import uuid
import json
import smtplib
import urllib.request
import logging
from datetime import datetime
from email.mime.text import MIMEText
from flask import Flask, request, jsonify, Response

# ── Ladda .env lokalt (Railway sätter dessa som env-vars) ─────────
if os.path.exists(".env"):
    for line in open(".env"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)

GMAIL_USER    = os.environ["GMAIL_USER"]
GMAIL_PASS    = os.environ["GMAIL_APP_PASSWORD"]
ADMIN_EMAIL   = os.environ["ADMIN_EMAIL"]
GITHUB_TOKEN  = os.environ["GITHUB_TOKEN"]
GITHUB_REPO   = os.environ["GITHUB_REPO"]   # "MarcusNygren514/activity-tracker"

DB_PATH = os.environ.get("DB_PATH", "users.db")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)


# ── Databas ───────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        id         TEXT PRIMARY KEY,
        name       TEXT NOT NULL,
        email      TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS feedback (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    TEXT NOT NULL,
        category   TEXT NOT NULL,
        message    TEXT NOT NULL,
        app_version TEXT,
        created_at TEXT NOT NULL
    )""")
    conn.commit()
    return conn


# ── E-post ────────────────────────────────────────────────────────

def send_email(to, subject, body):
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = to
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as smtp:
            smtp.login(GMAIL_USER, GMAIL_PASS)
            smtp.send_message(msg)
    except Exception as e:
        logging.error(f"E-post misslyckades: {e}")


# ── GitHub-hjälp ─────────────────────────────────────────────────

def github_get(path):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{GITHUB_REPO}{path}",
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept":        "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


# ── Routes ────────────────────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify({"ok": True})


@app.route("/register", methods=["POST"])
def register():
    data  = request.get_json(silent=True) or {}
    name  = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()

    if not name or not email or "@" not in email:
        return jsonify({"ok": False, "error": "Namn och giltig e-post krävs"}), 400

    db = get_db()

    # Befintlig användare → returnera deras token
    existing = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if existing:
        return jsonify({"ok": True, "token": existing["id"], "existing": True})

    token = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users (id, name, email, created_at) VALUES (?,?,?,?)",
        (token, name, email, datetime.now().isoformat()),
    )
    db.commit()

    send_email(
        email,
        "Välkommen till Activity Tracker",
        f"Hej {name}!\n\nDu är nu registrerad i Activity Tracker.\n"
        f"Din enhet är kopplad och redo att använda.\n\n"
        f"Mvh / Activity Tracker",
    )
    send_email(
        ADMIN_EMAIL,
        f"[AT] Ny användare: {name}",
        f"Namn:  {name}\nEmail: {email}\nTid:   {datetime.now().isoformat()}",
    )

    logging.info(f"Ny användare registrerad: {email}")
    return jsonify({"ok": True, "token": token, "existing": False})


@app.route("/feedback", methods=["POST"])
def feedback():
    data        = request.get_json(silent=True) or {}
    token       = data.get("token", "").strip()
    category    = data.get("category", "övrigt").strip()
    message     = data.get("message", "").strip()
    version     = data.get("version", "okänd")
    diagnostics = data.get("diagnostics", {})

    if not message:
        return jsonify({"ok": False, "error": "Meddelande krävs"}), 400

    db   = get_db()
    user = db.execute("SELECT * FROM users WHERE id=?", (token,)).fetchone() if token else None

    sender_name  = user["name"]  if user else data.get("name", "Okänd användare").strip() or "Okänd användare"
    sender_email = user["email"] if user else data.get("email", "").strip()
    user_id      = token if user else "anon"

    db.execute(
        "INSERT INTO feedback (user_id, category, message, app_version, created_at) VALUES (?,?,?,?,?)",
        (user_id, category, message, version, datetime.now().isoformat()),
    )
    db.commit()

    diag_lines = ""
    if diagnostics:
        diag_lines = (
            "\n── Diagnostik ───────────────────────\n"
            f"OS:             {diagnostics.get('os_version', '?')}\n"
            f"Python:         {diagnostics.get('python_version', '?')}\n"
            f"RAM totalt:     {diagnostics.get('ram_total_gb', '?')} GB\n"
            f"RAM ledigt:     {diagnostics.get('ram_free_gb', '?')} GB\n"
            f"Ollama:         {'Igång' if diagnostics.get('ollama_running') else 'Ej igång'}\n"
            f"Tracker:        {'Aktiv' if diagnostics.get('tracker_running') else 'Ej aktiv'}\n"
            f"Senaste fel:    {diagnostics.get('last_error') or 'inga'}\n"
        )

    send_email(
        ADMIN_EMAIL,
        f"[AT Feedback] {category} – {sender_name}",
        f"Från:    {sender_name}{(' (' + sender_email + ')') if sender_email else ''}\n"
        f"Version: {version}\n"
        f"Kategori:{category}\n\n"
        f"{message}"
        f"{diag_lines}",
    )

    return jsonify({"ok": True})


@app.route("/version")
def version():
    try:
        release = github_get("/releases/latest")
        tag     = release["tag_name"]           # t.ex. "v1.2.0"
        notes   = release.get("body", "")
        asset   = next(
            (a for a in release.get("assets", []) if a["name"].endswith(".exe")),
            None,
        )
        return jsonify({
            "ok":           True,
            "version":      tag,
            "notes":        notes,
            "download_url": f"/download/{tag}" if asset else None,
            "asset_name":   asset["name"] if asset else None,
            "size":         asset["size"] if asset else 0,
        })
    except Exception as e:
        logging.error(f"/version fel: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/download/<tag>")
def download(tag):
    try:
        release = github_get(f"/releases/tags/{tag}")
        asset   = next(
            (a for a in release.get("assets", []) if a["name"].endswith(".exe")),
            None,
        )
        if not asset:
            return "Ingen installer hittades", 404

        # Hämta den faktiska nedladdningslänken (omdirigering krävs)
        req = urllib.request.Request(
            asset["url"],
            headers={
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Accept":        "application/octet-stream",
            },
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()

        return Response(
            data,
            mimetype="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{asset["name"]}"'},
        )
    except Exception as e:
        logging.error(f"/download fel: {e}")
        return str(e), 500


if __name__ == "__main__":
    get_db()  # initiera tabeller
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
