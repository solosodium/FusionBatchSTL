"""Shared toolbar/command registration helpers."""

import os
import traceback

import adsk.core

WORKSPACE_ID = 'FusionSolidEnvironment'
# Preferred panel first (Utilities > Make), falling back to Utilities > Add-Ins.
PANEL_IDS = ['MakePanel', 'SolidScriptsAddinsPanel']

RESOURCES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'resources')

# Event handlers must be kept alive for as long as the add-in runs.
handlers = []
_registered = []  # (command id, panel id)


def resource(name):
    path = os.path.join(RESOURCES, name)
    return path if os.path.isdir(path) else ''


def show_error(context):
    ui = adsk.core.Application.get().userInterface
    ui.messageBox('{} failed:\n{}'.format(context, traceback.format_exc()), 'FusionBatchSTL')


def _find_panel(ui):
    ws = ui.workspaces.itemById(WORKSPACE_ID)
    if not ws:
        return None
    for panel_id in PANEL_IDS:
        panel = ws.toolbarPanels.itemById(panel_id)
        if panel:
            return panel
    return None


def add_command(ui, cmd_id, name, tooltip, icon, created_handler, promoted=False):
    existing = ui.commandDefinitions.itemById(cmd_id)
    if existing:
        existing.deleteMe()
    cmd_def = ui.commandDefinitions.addButtonDefinition(cmd_id, name, tooltip, resource(icon))
    cmd_def.commandCreated.add(created_handler)
    handlers.append(created_handler)

    panel = _find_panel(ui)
    if panel:
        old = panel.controls.itemById(cmd_id)
        if old:
            old.deleteMe()
        control = panel.controls.addCommand(cmd_def)
        control.isPromoted = promoted
        _registered.append((cmd_id, panel.id))
    else:
        _registered.append((cmd_id, None))
    return cmd_def


def unregister_all(ui):
    ws = ui.workspaces.itemById(WORKSPACE_ID)
    for cmd_id, panel_id in _registered:
        if ws and panel_id:
            panel = ws.toolbarPanels.itemById(panel_id)
            if panel:
                control = panel.controls.itemById(cmd_id)
                if control:
                    control.deleteMe()
        cmd_def = ui.commandDefinitions.itemById(cmd_id)
        if cmd_def:
            cmd_def.deleteMe()
    del _registered[:]
    del handlers[:]
