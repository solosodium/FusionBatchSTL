"""Turns a design + settings into STL files."""

import os
import subprocess
import sys
from collections import OrderedDict

import adsk.core
import adsk.fusion

from . import bodies, naming, stl_writer

# Multiply Fusion internal units (cm) by this to get the target unit.
UNIT_SCALE = {
    'mm': 10.0,
    'cm': 1.0,
    'm': 0.01,
    'in': 1.0 / 2.54,
    'ft': 1.0 / 30.48,
}

_QUALITY = {
    'low': adsk.fusion.TriangleMeshQualityOptions.LowQualityTriangleMesh,
    'normal': adsk.fusion.TriangleMeshQualityOptions.NormalQualityTriangleMesh,
    'high': adsk.fusion.TriangleMeshQualityOptions.HighQualityTriangleMesh,
    'veryhigh': adsk.fusion.TriangleMeshQualityOptions.VeryHighQualityTriangleMesh,
}


class ExportError(Exception):
    pass


class Job(object):
    def __init__(self, stem, members, label, is_bundle):
        self.stem = stem
        self.members = members
        self.label = label
        self.is_bundle = is_bundle


class Result(object):
    def __init__(self, folder):
        self.folder = folder
        self.files = []
        self.warnings = []
        self.cancelled = False


def active_design(app):
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        raise ExportError('Open a design in the Design workspace first.')
    return design


def document_name(app):
    doc = app.activeDocument
    name = ''
    try:
        if doc.dataFile:
            name = doc.dataFile.name
    except Exception:
        pass
    return naming.strip_version(name or doc.name) or 'Untitled'


def effective_folder(design, settings):
    return bodies.get_design_folder(design) or settings['output_folder']


def resolve_units(design, key):
    if key == 'design':
        key = design.unitsManager.defaultLengthUnits
    return key if key in UNIT_SCALE else 'mm'


def build_jobs(design, doc_name, settings, excluded=None, bundle_overrides=None):
    """bundle_overrides: {bodies.native_key: name} for unsaved bundle edits ('' = no bundle)."""
    refs = bodies.collect_bodies(design, settings['include_hidden'], settings['solid_only'])
    if excluded:
        refs = [r for r in refs if r.key not in excluded]
    singles = []
    bundles = OrderedDict()
    for ref in refs:
        if bundle_overrides and bodies.native_key(ref.body) in bundle_overrides:
            bundle = bundle_overrides[bodies.native_key(ref.body)]
        else:
            bundle = bodies.get_bundle(ref.body)
        if bundle:
            bundles.setdefault(bundle, []).append(ref)
            if settings['also_individual']:
                singles.append(ref)
        else:
            singles.append(ref)

    jobs = []
    for ref in singles:
        stem = naming.render(
            settings['body_template'],
            document=doc_name,
            component=ref.component_name,
            occurrence=ref.occurrence_name,
            body=ref.name,
            bundle='',
        )
        jobs.append(Job(stem, [ref], ref.label, False))
    for name, members in bundles.items():
        stem = naming.render(
            settings['bundle_template'],
            document=doc_name,
            component='',
            occurrence='',
            body=name,
            bundle=name,
        )
        jobs.append(Job(stem, members, 'Bundle "{}"'.format(name), True))

    for job, stem in zip(jobs, naming.make_unique([j.stem for j in jobs])):
        job.stem = stem
    return jobs


def summarize(jobs):
    singles = sum(1 for j in jobs if not j.is_bundle)
    bundle_jobs = [j for j in jobs if j.is_bundle]
    text = '{} file(s): {} individual bod{}, {} bundle(s)'.format(
        len(jobs), singles, 'y' if singles == 1 else 'ies', len(bundle_jobs))
    for j in bundle_jobs:
        text += '\n  - {} ({} bodies)'.format(j.label, len(j.members))
    return text


def mesh_body(body, settings, scale):
    calc = body.meshManager.createMeshCalculator()
    refinement = settings['refinement']
    if refinement == 'custom':
        calc.setQuality(adsk.fusion.TriangleMeshQualityOptions.NormalQualityTriangleMesh)
        calc.surfaceTolerance = settings['surface_deviation']
        calc.maxNormalDeviation = settings['normal_deviation']
        if settings['max_edge_length'] > 0:
            calc.maxSideLength = settings['max_edge_length']
        if settings['aspect_ratio'] > 0:
            calc.maxAspectRatio = settings['aspect_ratio']
    else:
        calc.setQuality(_QUALITY.get(refinement, _QUALITY['high']))
    mesh = calc.calculate()
    coords = mesh.nodeCoordinatesAsDouble
    if scale != 1.0:
        coords = [c * scale for c in coords]
    return coords, list(mesh.nodeIndices)


def run_export(app, settings, folder, show_progress=True, excluded=None):
    design = active_design(app)
    folder = os.path.expanduser(folder.strip())
    if not folder:
        raise ExportError('No output folder set.')
    doc_name = document_name(app)
    if excluded is None:
        excluded = bodies.get_excluded(design)
    jobs = build_jobs(design, doc_name, settings, excluded)
    if not jobs:
        raise ExportError('No bodies to export. Tick at least one body, or check the hidden/surface filters.')

    scale = UNIT_SCALE[resolve_units(design, settings['units'])]
    result = Result(folder)
    total = sum(len(j.members) for j in jobs)

    progress = None
    if show_progress:
        progress = app.userInterface.createProgressDialog()
        progress.cancelButtonText = 'Cancel'
        progress.isBackgroundTranslucent = False
        progress.isCancelButtonShown = True
        progress.show('Batch STL Export', 'Starting...', 0, total, 0)

    done = 0
    try:
        for job in jobs:
            meshes = []
            for ref in job.members:
                if progress:
                    if progress.wasCancelled:
                        result.cancelled = True
                        return result
                    progress.message = 'Meshing {} ({} of {})'.format(ref.label, done + 1, total)
                    progress.progressValue = done
                    adsk.doEvents()
                try:
                    meshes.append(mesh_body(ref.body, settings, scale))
                except Exception as e:
                    result.warnings.append('{}: meshing failed ({})'.format(ref.label, e))
                done += 1

            if stl_writer.triangle_count(meshes) == 0:
                result.warnings.append('{}: nothing to write, skipped'.format(job.label))
                continue

            path = os.path.join(folder, job.stem + '.stl')
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                if not settings['overwrite']:
                    path = naming.avoid_existing(path)
                stl_writer.write_stl(path, meshes, settings['binary'], os.path.basename(job.stem))
                result.files.append(path)
            except OSError as e:
                result.warnings.append('{}: could not write file ({})'.format(job.label, e))
    finally:
        if progress:
            progress.hide()

    if settings['open_folder'] and result.files:
        open_folder(folder)
    return result


def open_folder(folder):
    try:
        if sys.platform == 'win32':
            os.startfile(folder)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', folder])
    except Exception:
        pass


def report(ui, result):
    if result.cancelled:
        msg = 'Export cancelled. {} file(s) were written to:\n{}'.format(len(result.files), result.folder)
    else:
        msg = 'Exported {} STL file(s) to:\n{}'.format(len(result.files), result.folder)
    if result.warnings:
        shown = result.warnings[:15]
        msg += '\n\nWarnings:\n' + '\n'.join(shown)
        if len(result.warnings) > len(shown):
            msg += '\n... and {} more'.format(len(result.warnings) - len(shown))
    ui.messageBox(msg, 'Batch STL Export')
