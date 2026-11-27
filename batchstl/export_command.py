"""'Batch STL Export' command and its dialog."""

import adsk.core
import adsk.fusion

from . import bodies, exporter, naming, settings as settings_mod, ui_util

CMD_ID = 'FusionBatchSTL_Export'

UNITS = [
    ('design', 'Design default'),
    ('mm', 'Millimeters'),
    ('cm', 'Centimeters'),
    ('m', 'Meters'),
    ('in', 'Inches'),
    ('ft', 'Feet'),
]
REFINEMENTS = [
    ('low', 'Low'),
    ('normal', 'Medium'),
    ('high', 'High'),
    ('veryhigh', 'Very high'),
    ('custom', 'Custom'),
]
FORMATS = [('binary', 'Binary'), ('ascii', 'ASCII')]
CUSTOM_IDS = ['surface_deviation', 'normal_deviation', 'max_edge_length', 'aspect_ratio']
DIALOG_WIDTH = 420
DIALOG_MIN_WIDTH = 380
TABLE_ID = 'body_table'
ROW_PREFIX = 'row_'


def register(ui):
    ui_util.add_command(
        ui, CMD_ID, 'Batch STL Export',
        'Export the ticked bodies in the design to STL files. Bundled bodies are merged into one STL per bundle.',
        'batch_export', _ExportCreated(), promoted=True)


class _DialogState(object):
    """Shared between the dialog's event handlers."""

    def __init__(self, base, excluded):
        self.base = base
        self.excluded = set(excluded)  # keys of unticked bodies (including ones currently filtered out)
        self.rows = {}  # checkbox input id -> body key
        self.bundle_inputs = {}  # bundle text input id -> bodies.native_key
        self.bundles = {}  # native_key -> bundle name typed in the dialog (saved on Export)
        self.natives = {}  # native_key -> a body to write the bundle attribute on
        self.generation = 0  # input ids must be unique even after rows are rebuilt


# ---------------------------------------------------------------- helpers

def _dropdown(parent, input_id, name, options, selected):
    dd = parent.addDropDownCommandInput(input_id, name, adsk.core.DropDownStyles.TextListDropDownStyle)
    for key, label in options:
        dd.listItems.add(label, key == selected, '')
    return dd


def _dropdown_key(dd, options):
    item = dd.selectedItem
    for key, label in options:
        if item and item.name == label:
            return key
    return options[0][0]


def _read_settings(inputs, base):
    s = dict(base)
    s['output_folder'] = inputs.itemById('folder').value.strip()
    s['body_template'] = inputs.itemById('body_template').value.strip() or settings_mod.DEFAULTS['body_template']
    s['bundle_template'] = inputs.itemById('bundle_template').value.strip() or settings_mod.DEFAULTS['bundle_template']
    s['overwrite'] = inputs.itemById('overwrite').value
    s['open_folder'] = inputs.itemById('open_folder').value
    s['units'] = _dropdown_key(inputs.itemById('units'), UNITS)
    s['binary'] = _dropdown_key(inputs.itemById('format'), FORMATS) == 'binary'
    s['refinement'] = _dropdown_key(inputs.itemById('refinement'), REFINEMENTS)
    s['surface_deviation'] = inputs.itemById('surface_deviation').value
    s['normal_deviation'] = inputs.itemById('normal_deviation').value
    s['max_edge_length'] = inputs.itemById('max_edge_length').value
    s['aspect_ratio'] = inputs.itemById('aspect_ratio').value
    s['include_hidden'] = inputs.itemById('include_hidden').value
    s['solid_only'] = inputs.itemById('solid_only').value
    s['also_individual'] = inputs.itemById('also_individual').value
    return s


def _update_summary(inputs, state):
    app = adsk.core.Application.get()
    box = inputs.itemById('summary')
    try:
        design = exporter.active_design(app)
        jobs = exporter.build_jobs(design, exporter.document_name(app), _read_settings(inputs, state.base),
                                   state.excluded, state.bundles)
        box.text = exporter.summarize(jobs)
    except Exception as e:
        box.text = str(e)


def _populate_table(inputs, state):
    """(Re)build one row per body that passes the hidden/surface filters."""
    table = adsk.core.TableCommandInput.cast(inputs.itemById(TABLE_ID))
    while table.rowCount > 0:
        table.deleteRow(0)
    state.rows = {}
    state.bundle_inputs = {}
    state.generation += 1

    design = adsk.fusion.Design.cast(adsk.core.Application.get().activeProduct)
    if not design:
        return
    include_hidden = inputs.itemById('include_hidden').value
    solid_only = inputs.itemById('solid_only').value
    refs = bodies.collect_bodies(design, include_hidden, solid_only)

    ci = table.commandInputs
    head = '{}h{}_'.format(ROW_PREFIX, state.generation)
    table.addCommandInput(ci.addTextBoxCommandInput(head + 'b', '', '<b>Body</b>', 1, True), 0, 1)
    bundle_head = ci.addTextBoxCommandInput(head + 'g', '', '<b>Bundle</b>', 1, True)
    bundle_head.tooltip = 'Type the same bundle name on several bodies to merge them into one STL file.'
    table.addCommandInput(bundle_head, 0, 2)

    for i, ref in enumerate(refs, start=1):
        rid = '{}{}_{}'.format(ROW_PREFIX, state.generation, i)
        label = ref.label
        notes = []
        if not ref.body.isVisible:
            notes.append('hidden')
        if not ref.body.isSolid:
            notes.append('surface')
        if notes:
            label += ' <i>({})</i>'.format(', '.join(notes))
        check = ci.addBoolValueInput(rid, '', True, '', ref.key not in state.excluded)
        check.tooltip = 'Export this body'
        table.addCommandInput(check, i, 0)
        table.addCommandInput(ci.addTextBoxCommandInput(rid + '_n', '', label, 1, True), i, 1)
        nkey = bodies.native_key(ref.body)
        state.natives.setdefault(nkey, ref.body)
        bundle = state.bundles.get(nkey, bodies.get_bundle(ref.body))
        bundle_input = ci.addStringValueInput(rid + '_b', '', bundle)
        bundle_input.tooltip = ('Bundle name. Bodies with the same name are merged into one STL file. '
                                'Leave empty to export the body on its own.')
        table.addCommandInput(bundle_input, i, 2)
        state.rows[rid] = ref.key
        state.bundle_inputs[rid + '_b'] = nkey


def _bundle_edited(inputs, state, changed):
    nkey = state.bundle_inputs[changed.id]
    name = changed.value.strip()
    state.bundles[nkey] = name
    # Every instance of a component shares one bundle: keep their rows in step.
    for input_id, other in state.bundle_inputs.items():
        if other == nkey and input_id != changed.id:
            other_input = inputs.itemById(input_id)
            if other_input.value.strip() != name:
                other_input.value = changed.value


def _save_bundles(state):
    """Write bundle names typed in the table to the design. Returns bodies that could not be tagged."""
    failed = []
    for nkey, name in state.bundles.items():
        body = state.natives.get(nkey)
        if body is None or bodies.get_bundle(body) == name:
            continue
        try:
            bodies.set_bundle(body, name)
        except Exception:
            failed.append(body.name)
    return failed


def _set_all(inputs, state, value):
    for rid, key in state.rows.items():
        inputs.itemById(rid).value = value
        if value:
            state.excluded.discard(key)
        else:
            state.excluded.add(key)


def _update_custom_visibility(inputs):
    custom = _dropdown_key(inputs.itemById('refinement'), REFINEMENTS) == 'custom'
    for input_id in CUSTOM_IDS:
        inputs.itemById(input_id).isVisible = custom


# ---------------------------------------------------------------- dialog command

class _ExportCreated(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            app = adsk.core.Application.get()
            cmd = args.command
            cmd.okButtonText = 'Export'
            # Starting another command (any other tool) while this dialog is
            # open must cancel it, not run the export.
            cmd.isExecutedWhenPreEmpted = False
            cmd.setDialogMinimumSize(DIALOG_MIN_WIDTH, 300)
            cmd.setDialogInitialSize(DIALOG_WIDTH, 560)
            s = settings_mod.load()
            design = adsk.fusion.Design.cast(app.activeProduct)
            folder = exporter.effective_folder(design, s) if design else s['output_folder']
            remembered = bool(design and bodies.get_design_folder(design))
            state = _DialogState(s, bodies.get_excluded(design) if design else set())

            inputs = cmd.commandInputs

            sel = inputs.addTabCommandInput('tab_bodies', 'Bodies').children
            table = sel.addTableCommandInput(TABLE_ID, 'Bodies', 3, '1:7:4')
            table.minimumVisibleRows = 4
            table.maximumVisibleRows = 12
            table.tablePresentationStyle = adsk.core.TablePresentationStyles.itemBorderTablePresentationStyle
            table.addToolbarCommandInput(table.commandInputs.addBoolValueInput('select_all', 'All', False, '', False))
            table.addToolbarCommandInput(table.commandInputs.addBoolValueInput('select_none', 'None', False, '', False))
            sel.addTextBoxCommandInput(
                'bundle_help', '',
                'Type the same <b>Bundle</b> name on several bodies to merge them into one STL. '
                'Bundle changes are saved with the design when you export.', 2, True)
            sel.addBoolValueInput('include_hidden', 'Include hidden bodies', True, '', s['include_hidden'])
            sel.addBoolValueInput('solid_only', 'Skip surface bodies', True, '', s['solid_only'])
            sel.addBoolValueInput('also_individual', 'Bundled bodies also as own files', True, '',
                                  s['also_individual'])
            sel.addTextBoxCommandInput('summary', 'Will export', '', 4, True)

            out = inputs.addTabCommandInput('tab_output', 'Output').children
            out.addStringValueInput('folder', 'Folder', folder)
            out.addBoolValueInput('browse', 'Browse...', False, '', False)
            out.addBoolValueInput('remember', 'Remember folder for this design', True, '', remembered)
            out.addStringValueInput('body_template', 'Body file name', s['body_template'])
            out.addStringValueInput('bundle_template', 'Bundle file name', s['bundle_template'])
            out.addTextBoxCommandInput('tokens_help', '', naming.TOKENS_HELP, 2, True)
            out.addBoolValueInput('overwrite', 'Overwrite existing files', True, '', s['overwrite'])
            out.addBoolValueInput('open_folder', 'Open folder when done', True, '', s['open_folder'])
            out.addBoolValueInput('save_defaults', 'Save these settings as defaults', True, '', True)

            mesh = inputs.addTabCommandInput('tab_mesh', 'Mesh').children
            _dropdown(mesh, 'units', 'Units', UNITS, s['units'])
            _dropdown(mesh, 'format', 'Format', FORMATS, 'binary' if s['binary'] else 'ascii')
            _dropdown(mesh, 'refinement', 'Refinement', REFINEMENTS, s['refinement'])
            mesh.addValueInput('surface_deviation', 'Surface deviation', 'mm',
                               adsk.core.ValueInput.createByReal(s['surface_deviation']))
            mesh.addValueInput('normal_deviation', 'Normal deviation', 'deg',
                               adsk.core.ValueInput.createByReal(s['normal_deviation']))
            edge = mesh.addValueInput('max_edge_length', 'Max edge length', 'mm',
                                      adsk.core.ValueInput.createByReal(s['max_edge_length']))
            edge.tooltip = 'Longest allowed triangle edge. 0 = no limit.'
            aspect = mesh.addFloatSpinnerCommandInput('aspect_ratio', 'Max aspect ratio', '', 0, 1000, 0.5,
                                                      s['aspect_ratio'])
            aspect.tooltip = 'Longest-to-shortest edge ratio of a triangle. 0 = no limit.'

            # Everything exists now, so the table and summary can read the other inputs.
            _populate_table(inputs, state)
            _update_custom_visibility(inputs)
            _update_summary(inputs, state)

            for event, handler in (
                (cmd.inputChanged, _ExportInputChanged(state)),
                (cmd.validateInputs, _ExportValidate()),
                (cmd.execute, _ExportExecute(state)),
            ):
                event.add(handler)
                ui_util.handlers.append(handler)
        except Exception:
            ui_util.show_error('Batch STL Export')


class _ExportInputChanged(adsk.core.InputChangedEventHandler):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def notify(self, args):
        try:
            changed = args.input
            # args.inputs only holds the changed input's siblings (e.g. the table's
            # own inputs for a toolbar button); look everything up dialog-wide.
            inputs = args.firingEvent.sender.commandInputs
            state = self.state
            if changed.id in state.rows:
                key = state.rows[changed.id]
                if changed.value:
                    state.excluded.discard(key)
                else:
                    state.excluded.add(key)
                _update_summary(inputs, state)
            elif changed.id in state.bundle_inputs:
                _bundle_edited(inputs, state, changed)
                _update_summary(inputs, state)
            elif changed.id in ('select_all', 'select_none'):
                changed.value = False
                _set_all(inputs, state, changed.id == 'select_all')
                _update_summary(inputs, state)
            elif changed.id == 'browse':
                changed.value = False
                ui = adsk.core.Application.get().userInterface
                dialog = ui.createFolderDialog()
                dialog.title = 'STL output folder'
                folder_input = inputs.itemById('folder')
                if folder_input.value:
                    dialog.initialDirectory = folder_input.value
                if dialog.showDialog() == adsk.core.DialogResults.DialogOK:
                    folder_input.value = dialog.folder
            elif changed.id == 'refinement':
                _update_custom_visibility(inputs)
            elif changed.id in ('include_hidden', 'solid_only'):
                _populate_table(inputs, state)
                _update_summary(inputs, state)
            elif changed.id == 'also_individual':
                _update_summary(inputs, state)
        except Exception:
            ui_util.show_error('Batch STL Export')


class _ExportValidate(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        inputs = args.firingEvent.sender.commandInputs
        ok = bool(inputs.itemById('folder').value.strip())
        for input_id in ('surface_deviation', 'normal_deviation', 'max_edge_length'):
            if not inputs.itemById(input_id).isValidExpression:
                ok = False
        args.areInputsValid = ok


class _ExportExecute(adsk.core.CommandEventHandler):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def notify(self, args):
        app = adsk.core.Application.get()
        ui = app.userInterface
        try:
            inputs = args.command.commandInputs
            base = self.state.base
            s = _read_settings(inputs, base)
            design = exporter.active_design(app)
            folder = s['output_folder']
            remember = inputs.itemById('remember').value
            bodies.set_design_folder(design, folder if remember else '')
            bodies.set_excluded(design, self.state.excluded)
            failed = _save_bundles(self.state)
            if failed:
                ui.messageBox('Could not set the bundle on these bodies (they may be in a linked component):\n'
                              + '\n'.join(failed), 'Batch STL Export')

            if inputs.itemById('save_defaults').value:
                to_save = dict(s)
                if remember:
                    # A per-design folder should not replace the global default folder.
                    to_save['output_folder'] = base['output_folder']
                settings_mod.save(to_save)

            result = exporter.run_export(app, s, folder, excluded=self.state.excluded)
            exporter.report(ui, result)
        except exporter.ExportError as e:
            ui.messageBox(str(e), 'Batch STL Export')
        except Exception:
            ui_util.show_error('Batch STL Export')

