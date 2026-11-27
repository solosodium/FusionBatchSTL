"""FusionBatchSTL - batch export bodies to STL, with optional bundles.

Entry point loaded by Fusion. The actual work lives in the ``batchstl`` package.
"""

import traceback

import adsk.core

from .batchstl import export_command, ui_util


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        export_command.register(ui)
    except Exception:
        if ui:
            ui.messageBox('FusionBatchSTL failed to start:\n{}'.format(traceback.format_exc()))


def stop(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        ui_util.unregister_all(ui)
    except Exception:
        if ui:
            ui.messageBox('FusionBatchSTL failed to stop:\n{}'.format(traceback.format_exc()))
