"""Global default settings, persisted as JSON in the user's app-data folder."""

import json
import math
import os
import sys

DEFAULTS = {
    'output_folder': os.path.join(os.path.expanduser('~'), 'Documents', 'Fusion STL Exports'),
    'body_template': '{body}',
    'bundle_template': '{bundle}',
    'units': 'mm',              # design | mm | cm | m | in | ft
    'refinement': 'high',       # low | normal | high | veryhigh | custom
    'surface_deviation': 0.001,  # cm (Fusion internal units)
    'normal_deviation': math.radians(10.0),  # radians
    'max_edge_length': 0.0,     # cm, 0 = no limit
    'aspect_ratio': 21.5,
    'binary': True,
    'include_hidden': False,
    'solid_only': True,
    'also_individual': False,   # also export bundled bodies as their own files
    'overwrite': True,
    'open_folder': True,
}


def _settings_path():
    if sys.platform == 'win32':
        base = os.environ.get('APPDATA') or os.path.expanduser('~')
    elif sys.platform == 'darwin':
        base = os.path.expanduser('~/Library/Application Support')
    else:
        base = os.path.expanduser('~/.config')
    return os.path.join(base, 'FusionBatchSTL', 'settings.json')


def load():
    settings = dict(DEFAULTS)
    try:
        with open(_settings_path(), 'r', encoding='utf-8') as f:
            stored = json.load(f)
        for key, value in stored.items():
            if key in DEFAULTS and isinstance(value, type(DEFAULTS[key])):
                settings[key] = value
            elif key in DEFAULTS and isinstance(DEFAULTS[key], float) and isinstance(value, int):
                settings[key] = float(value)
    except (OSError, ValueError):
        pass
    return settings


def save(settings):
    path = _settings_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = {k: settings[k] for k in DEFAULTS if k in settings}
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
