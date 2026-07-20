import os
import json


def get_prefs_path() -> str:
    app_data = os.getenv('APPDATA')
    if not app_data:
        app_data = os.path.expanduser('~')
    prefs_dir = os.path.join(app_data, 'PersonalFinanceETL')
    os.makedirs(prefs_dir, exist_ok=True)
    return os.path.join(prefs_dir, 'prefs.json')


def add_recent_config(filepath: str) -> None:
    """Adds a configuration path to the recent list in preferences."""
    prefs_path = get_prefs_path()
    recents = get_recent_configs()

    if filepath in recents:
        recents.remove(filepath)
    recents.insert(0, filepath)

    # Keep top 10
    recents = recents[:10]

    with open(prefs_path, 'w') as f:
        json.dump({"recent_configs": recents}, f)


def get_recent_configs() -> list[str]:
    """Returns a list of recent configuration file paths."""
    prefs_path = get_prefs_path()
    if os.path.exists(prefs_path):
        with open(prefs_path, 'r') as f:
            try:
                data = json.load(f)
                recents = data.get("recent_configs", [])
                if isinstance(recents, list):
                    return [r for r in recents if os.path.exists(r)]
            except:
                pass
    return []
