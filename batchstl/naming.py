"""File-name templating helpers. Pure Python, no Fusion dependency."""

import datetime
import os
import re

TOKENS_HELP = (
    'Tokens: {document} {component} {occurrence} {body} {bundle} {date} {time}. '
    'Use / to create subfolders.'
)

_INVALID = re.compile(r'[<>:"|?*\x00-\x1f]')
_RESERVED = {'CON', 'PRN', 'AUX', 'NUL'} | {'COM%d' % i for i in range(1, 10)} | {'LPT%d' % i for i in range(1, 10)}
_VERSION_SUFFIX = re.compile(r'\s+v\d+$')


class _Tokens(dict):
    def __missing__(self, key):
        # Leave unknown tokens as literal text instead of failing.
        return '{' + key + '}'


def strip_version(name):
    """'Bracket v12' -> 'Bracket'."""
    return _VERSION_SUFFIX.sub('', name or '').strip()


def sanitize_part(part):
    part = _INVALID.sub('_', part)
    part = re.sub(r'_{2,}', '_', part)
    part = part.strip(' _-').rstrip('.')
    if not part:
        part = '_'
    if part.split('.')[0].upper() in _RESERVED:
        part = '_' + part
    return part


def render(template, **values):
    """Render ``template`` into a relative path (no extension), using os.sep."""
    now = datetime.datetime.now()
    values.setdefault('date', now.strftime('%Y-%m-%d'))
    values.setdefault('time', now.strftime('%H%M%S'))
    # Token values must never introduce folders on their own.
    safe = _Tokens({k: str(v).replace('/', '_').replace('\\', '_') for k, v in values.items()})
    try:
        text = template.format_map(safe)
    except (ValueError, IndexError):
        text = template
    parts = [p for p in re.split(r'[\\/]+', text) if p.strip() and p.strip() not in ('.', '..')]
    parts = [sanitize_part(p) for p in parts]
    return os.path.join(*parts) if parts else 'export'


def make_unique(stems):
    """Append _2, _3 ... to stems that collide (case-insensitively)."""
    seen = {}
    result = []
    for stem in stems:
        key = stem.lower()
        if key not in seen:
            seen[key] = 1
            result.append(stem)
            continue
        n = seen[key]
        while True:
            n += 1
            candidate = '{}_{}'.format(stem, n)
            if candidate.lower() not in seen:
                break
        seen[key] = n
        seen[candidate.lower()] = 1
        result.append(candidate)
    return result


def avoid_existing(path):
    """Return ``path`` or 'name (1).stl', 'name (2).stl' ... if it already exists."""
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    i = 1
    while os.path.exists('{} ({}){}'.format(base, i, ext)):
        i += 1
    return '{} ({}){}'.format(base, i, ext)
