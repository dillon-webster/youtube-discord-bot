import json
import os
import threading
from pathlib import Path

from flask import Flask, redirect, request, session
from google_auth_oauthlib.flow import Flow

from token_store import save_token

SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
SCRIPT_DIR = Path(__file__).parent

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-me-in-production")


def _redirect_uri() -> str:
    base = (
        os.environ.get("WEB_URL")
        or f"https://{os.environ.get('RAILWAY_PUBLIC_DOMAIN', 'localhost:8080')}"
    )
    return f"{base.rstrip('/')}/callback"


def _make_flow() -> Flow:
    secrets_env = os.environ.get("GOOGLE_CLIENT_SECRETS")
    if secrets_env:
        return Flow.from_client_config(
            json.loads(secrets_env), scopes=SCOPES, redirect_uri=_redirect_uri()
        )
    return Flow.from_client_secrets_file(
        str(SCRIPT_DIR / "client_secrets.json"),
        scopes=SCOPES,
        redirect_uri=_redirect_uri(),
    )


@app.route("/auth")
def auth():
    discord_id = request.args.get("discord_id", "")
    if not discord_id:
        return "Missing discord_id", 400
    flow = _make_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline", prompt="consent", state=discord_id
    )
    session["code_verifier"] = getattr(flow, "code_verifier", None)
    return redirect(auth_url)


@app.route("/callback")
def callback():
    discord_id = request.args.get("state", "")
    flow = _make_flow()
    auth_response = request.url.replace("http://", "https://", 1)
    code_verifier = session.pop("code_verifier", None)
    fetch_kwargs = {"authorization_response": auth_response}
    if code_verifier:
        fetch_kwargs["code_verifier"] = code_verifier
    flow.fetch_token(**fetch_kwargs)
    save_token(discord_id, json.loads(flow.credentials.to_json()))
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Doofenshmirtz Evil Inc.</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Special+Elite&family=Courier+Prime&display=swap');
    body {
      background-color: #1a1a2e;
      color: #e0e0e0;
      font-family: 'Courier Prime', monospace;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      margin: 0;
    }
    .letterhead {
      background-color: #16213e;
      border: 3px solid #9b30ff;
      border-radius: 8px;
      max-width: 600px;
      width: 90%;
      padding: 40px;
      box-shadow: 0 0 30px rgba(155, 48, 255, 0.4);
      text-align: center;
    }
    .company-name {
      font-family: 'Special Elite', cursive;
      font-size: 2rem;
      color: #9b30ff;
      letter-spacing: 2px;
      margin: 0;
    }
    .tagline {
      font-size: 0.85rem;
      color: #888;
      margin: 4px 0 20px;
      font-style: italic;
    }
    .divider { border: none; border-top: 2px solid #9b30ff; margin: 20px 0; }
    .doof-img { width: 180px; border-radius: 8px; margin: 16px 0; border: 2px solid #9b30ff; }
    .headline { font-family: 'Special Elite', cursive; font-size: 1.4rem; color: #c77dff; margin: 16px 0 8px; }
    .body-text { font-size: 1rem; color: #ccc; line-height: 1.6; }
    .inator { color: #9b30ff; font-weight: bold; }
  </style>
</head>
<body>
  <div class="letterhead">
    <p class="company-name">Doofenshmirtz Evil Inc.</p>
    <p class="tagline">Tri-State Area's #1 Evil Science Corporation</p>
    <hr class="divider">
    <img src="/static/doof.webp" alt="Dr. Doofenshmirtz" class="doof-img">
    <hr class="divider">
    <p class="headline">Access Granted!</p>
    <p class="body-text">
      Congratulations! You have been approved to use the
      <span class="inator">RandomVideo-inator™</span>.<br><br>
      Head back to Discord and try <span class="inator">!random</span>.
    </p>
  </div>
</body>
</html>"""


def run_in_background():
    port = int(os.environ.get("PORT", 8080))
    t = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=port, use_reloader=False),
        daemon=True,
    )
    t.start()
