import json
from pathlib import Path

_TOKEN_FILE = Path(__file__).parent / "tokens.json"


def get_token(discord_id: str) -> dict | None:
    if not _TOKEN_FILE.exists():
        return None
    return json.loads(_TOKEN_FILE.read_text()).get(str(discord_id))


def save_token(discord_id: str, token_data: dict):
    tokens = {}
    if _TOKEN_FILE.exists():
        tokens = json.loads(_TOKEN_FILE.read_text())
    tokens[str(discord_id)] = token_data
    _TOKEN_FILE.write_text(json.dumps(tokens, indent=2))
