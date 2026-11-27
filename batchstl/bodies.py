"""Collecting bodies from a design and storing bundle membership.

Bundle membership is stored as an attribute on each (native) BRepBody, so it
is saved with the design file. Because it lives on the native body, every
instance of a component shares the same bundle assignment.
"""

import json

import adsk.core
import adsk.fusion

ATTR_GROUP = 'FusionBatchSTL'
ATTR_BUNDLE = 'bundle'
ATTR_FOLDER = 'output_folder'
ATTR_EXCLUDED = 'excluded'


class BodyRef(object):
    """A body in the context of the root component (may be a proxy)."""

    def __init__(self, body, occurrence):
        self.body = body
        self.occurrence = occurrence

    @property
    def native(self):
        return native_body(self.body)

    @property
    def name(self):
        return self.body.name

    @property
    def component_name(self):
        # Root-level bodies: the root component is named after the document,
        # which {document} already covers.
        if not self.occurrence:
            return ''
        return self.body.parentComponent.name

    @property
    def occurrence_name(self):
        return self.occurrence.name if self.occurrence else ''

    @property
    def key(self):
        """Stable per-instance identifier used to remember export selection."""
        path = self.occurrence.fullPathName if self.occurrence else ''
        return '{}|{}'.format(path, self.body.name)

    @property
    def label(self):
        if self.occurrence:
            return '{} / {}'.format(self.occurrence.name, self.body.name)
        return self.body.name


def native_body(body):
    if body.assemblyContext:
        return body.nativeObject
    return body


def native_key(body):
    """Identifies the component's body that all its instances share (where bundles are stored)."""
    native = native_body(body)
    return '{}|{}'.format(native.parentComponent.id, native.name)


def collect_bodies(design, include_hidden=False, solid_only=True):
    """All BRep bodies in the design, as root-context references."""
    result = []

    def consider(body, occurrence):
        if not include_hidden and not body.isVisible:
            return
        if solid_only and not body.isSolid:
            return
        result.append(BodyRef(body, occurrence))

    root = design.rootComponent
    for body in root.bRepBodies:
        consider(body, None)
    for occ in root.allOccurrences:
        if not include_hidden and not occ.isVisible:
            continue
        for body in occ.bRepBodies:
            consider(body, occ)
    return result


def get_bundle(body):
    attr = native_body(body).attributes.itemByName(ATTR_GROUP, ATTR_BUNDLE)
    return attr.value if attr else ''


def set_bundle(body, name):
    attrs = native_body(body).attributes
    existing = attrs.itemByName(ATTR_GROUP, ATTR_BUNDLE)
    if existing:
        existing.deleteMe()
    if name:
        attrs.add(ATTR_GROUP, ATTR_BUNDLE, name)


def get_excluded(design):
    """Keys of bodies the user unticked for export in this design."""
    attr = design.attributes.itemByName(ATTR_GROUP, ATTR_EXCLUDED)
    if not attr:
        return set()
    try:
        return set(json.loads(attr.value))
    except ValueError:
        return set()


def set_excluded(design, keys):
    """Store the unticked bodies, dropping keys of bodies that no longer exist."""
    existing = {r.key for r in collect_bodies(design, include_hidden=True, solid_only=False)}
    keys = sorted(set(keys) & existing)
    if set(keys) == get_excluded(design):
        return  # unchanged: don't touch the document
    attr = design.attributes.itemByName(ATTR_GROUP, ATTR_EXCLUDED)
    if attr:
        attr.deleteMe()
    if keys:
        design.attributes.add(ATTR_GROUP, ATTR_EXCLUDED, json.dumps(keys))


def get_design_folder(design):
    attr = design.attributes.itemByName(ATTR_GROUP, ATTR_FOLDER)
    return attr.value if attr else ''


def set_design_folder(design, folder):
    existing = design.attributes.itemByName(ATTR_GROUP, ATTR_FOLDER)
    if folder:
        if existing and existing.value == folder:
            return
        if existing:
            existing.deleteMe()
        design.attributes.add(ATTR_GROUP, ATTR_FOLDER, folder)
    elif existing:
        existing.deleteMe()
