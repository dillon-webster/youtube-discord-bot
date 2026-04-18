import json
import os
import threading
from pathlib import Path

from flask import Flask, redirect, request
from google_auth_oauthlib.flow import Flow

from token_store import save_token

SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
SCRIPT_DIR = Path(__file__).parent

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-me-in-production")


def _redirect_uri() -> str:
    base = os.environ.get("WEB_URL") or f"https://{os.environ.get('RAILWAY_PUBLIC_DOMAIN', 'localhost:8080')}"
    return f"{base.rstrip('/')}/callback"


def _make_flow() -> Flow:
    secrets_env = os.environ.get("GOOGLE_CLIENT_SECRETS")
    if secrets_env:
        return Flow.from_client_config(json.loads(secrets_env), scopes=SCOPES, redirect_uri=_redirect_uri())
    return Flow.from_client_secrets_file(
        str(SCRIPT_DIR / "client_secrets.json"), scopes=SCOPES, redirect_uri=_redirect_uri()
    )


@app.route("/auth")
def auth():
    discord_id = request.args.get("discord_id", "")
    if not discord_id:
        return "Missing discord_id", 400
    flow = _make_flow()
    auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent", state=discord_id)
    return redirect(auth_url)


@app.route("/callback")
def callback():
    discord_id = request.args.get("state", "")
    flow = _make_flow()
    # Fix scheme when running behind Railway's HTTPS proxy
    auth_response = request.url.replace("http://", "https://", 1)
    flow.fetch_token(authorization_response=auth_response)
    save_token(discord_id, json.loads(flow.credentials.to_json()))
    return "<h2>All set! Head back to Discord and try !random</h2>"


def run_in_background():
    port = int(os.environ.get("PORT", 8080))
    t = threading.Thread(target=lambda: app.run(host="0.0.0.0", port=port, use_reloader=False), daemon=True)
    t.start()
