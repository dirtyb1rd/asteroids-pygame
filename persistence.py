import json
import os

_DATA_DIR  = os.path.join(os.path.dirname(__file__), "data")
_SCORES_FILE = os.path.join(_DATA_DIR, "scores.json")

_DEFAULT_SCORES = {
    "asteroids": {"classic": 0, "survival": 0, "hardcore": 0},
    "snake":     {"classic": 0, "wrap": 0, "speedrun": 0},
    "tetris":    {"marathon": 0, "sprint": 0, "ultra": 0},
    "pong":      {"vs_cpu": 0},
    "breakout":  {"classic": 0, "endless": 0},
}

_DEFAULT_SETTINGS = {
    "crt_effects": True,
    "show_fps": False,
}

_scores: dict   = {}
_settings: dict = {}


def load() -> None:
    """Load scores and settings from disk. Creates defaults if missing."""
    global _scores, _settings
    os.makedirs(_DATA_DIR, exist_ok=True)
    if os.path.exists(_SCORES_FILE):
        try:
            with open(_SCORES_FILE) as f:
                data = json.load(f)
            _scores   = data.get("scores", {})
            _settings = data.get("settings", {})
        except (json.JSONDecodeError, OSError):
            _scores   = {}
            _settings = {}
    # Fill missing keys with defaults
    for game, modes in _DEFAULT_SCORES.items():
        _scores.setdefault(game, {})
        for mode, val in modes.items():
            _scores[game].setdefault(mode, val)
    for key, val in _DEFAULT_SETTINGS.items():
        _settings.setdefault(key, val)


def save() -> None:
    """Persist scores and settings to disk."""
    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(_SCORES_FILE, "w") as f:
        json.dump({"scores": _scores, "settings": _settings}, f, indent=2)


def get_score(game: str, mode: str) -> int | float:
    return _scores.get(game, {}).get(mode, 0)


def set_score(game: str, mode: str, value: int | float) -> bool:
    """Update high score if value beats current. Returns True if new record."""
    current = get_score(game, mode)
    if value > current:
        _scores.setdefault(game, {})[mode] = value
        save()
        return True
    return False


def get_setting(key: str):
    return _settings.get(key, _DEFAULT_SETTINGS.get(key))


def set_setting(key: str, value) -> None:
    _settings[key] = value
    save()
