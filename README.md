# FusionBatchSTL

A Fusion add-in that exports every body in a design to STL in one go, using
settings you save once. You can also group bodies into **bundles**: each bundle
exports as a single merged STL file.

## Install

1. Clone or copy this folder somewhere permanent. The folder must be named `FusionBatchSTL`.
2. In Fusion, open **Utilities > Add-Ins > Scripts and Add-Ins** (Shift+S).
3. On the **Add-Ins** tab, click the **+** next to "My Add-Ins" and select this folder.
4. Select **FusionBatchSTL** and click **Run**. Tick **Run on Startup** to load it automatically.

The commands appear in the **Design** workspace under **Utilities > Make**. If
that panel can't be found, they go under **Utilities > Add-Ins**.

## Commands

### Batch STL Export
This dialog has three tabs:

- **Bodies**
  - A list of every body in the design, each with a tick box and an editable **Bundle** name. **All** and **None** buttons tick or untick everything.
  - Type the same bundle name on several bodies to merge them into one STL; clear it to export the body on its own. Bundle changes are saved in the design when you click Export.
  - Only ticked bodies are exported. An unticked body is also left out of its bundle's file.
  - The ticks are saved in the design file when you click Export, so they are remembered next time. New bodies start ticked.
  - Include hidden bodies.
  - Skip surface bodies.
  - Also export bundled bodies as their own files.
  - A summary of what will be exported, updated as you tick.
- **Output**
  - Output folder (with a Browse button).
  - "Remember folder for this design": stores the folder inside the `.f3d`, so each design can have its own location.
  - File-name templates for single bodies and for bundles, plus overwrite and "open folder when done" options.
  - "Save these settings as defaults": the dialog opens with them next time.
- **Mesh**
  - Units: mm by default, or the design's own units.
  - Binary or ASCII output.
  - Refinement: Low, Medium, High, Very high, or Custom (surface deviation, normal deviation, max edge length, aspect ratio).

File-name tokens: `{document} {component} {occurrence} {body} {bundle} {date} {time}`.
The default is `{body}` (and `{bundle}`), so files go straight into the output folder.
A `/` creates subfolders: for example, `{document}/{body}` gives each design its own
subfolder. When two files would get the same name,
the later ones get `_2`, `_3`, … added.

## Notes and limits

- Meshes are made with Fusion's mesh calculator and written by the add-in itself, which is what allows bodies to be merged. Positions come from the assembly, so bodies inside components end up where they sit in the assembly.
- Bundles are saved in the design file as attributes on the bodies. Membership is stored on the component's body. If a component is used more than once, every copy of that body is in the bundle.
- Bodies in linked (external) components can't be tagged, because those components are read-only.
- Mesh bodies are not exported. Only B-Rep solid bodies are, plus surface bodies if you allow them.
- Default settings are saved in `%APPDATA%\FusionBatchSTL\settings.json` on Windows and `~/Library/Application Support/FusionBatchSTL/settings.json` on macOS.

## Development

The STL writer and file-naming code don't depend on Fusion, so they can be tested outside it:

```
python -m unittest discover tests
```

The toolbar icon is drawn by `tools/make_icon.py`, which also has no dependencies. Run
`python tools/make_icon.py resources preview.png` to regenerate it and get an enlarged preview.
