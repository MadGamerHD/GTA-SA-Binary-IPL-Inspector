# Binary IPL Inspector — README

A small, safe GUI tool for inspecting, editing (in text form), and *safely* rebuilding binary `.ipl` ("bnry") files used by certain game/modding workflows.

> This README describes the tools, how the program works, how to use it, and simple command‑prompt installation/running instructions. It does **not** mention cloning or repositories — save or copy the script file and run it locally.

---

## What this tool does

* Opens **binary IPL** files that begin with the `bnry` magic header.
* Parses two editable sections into tabs: `INST` and `CARS`.
* Lets you edit those entries in plain text and **rebuild & save** a compact, consistent binary IPL file.
* Provides a **Batch Rebuild** mode that processes all `.ipl` files in a folder, creating `.bak` backups and safely replacing files using atomic temp files.
* Includes a safer repack path that preserves numeric values (including the `interior` field) from the original file when possible; if the file contains unknown/extra sections the tool will skip rewriting and instead save a `.bak`.

---

## Requirements

* **Python 3.8+** (should work on 3.8, 3.9, 3.10, 3.11+)
* `tkinter` (standard GUI library for Python). On most Windows installs it comes bundled; on some Linux distributions you may need to install it separately.

No external pip packages are required.

---

## Quick install & run (command prompt / terminal)

1. (Optional) Create and activate a virtual environment:

```bash
# Windows (Command Prompt)
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

2. Ensure `tkinter` is available. Example for Debian/Ubuntu:

```bash
sudo apt update
sudo apt install python3-tk
```

On Windows and many macOS Python installers `tkinter` is already present.

3. Run the script from the command line: (replace `ipl_inspector.py` with whatever you named the script)

```bash
python ipl_inspector.py
```

A GUI window titled **Binary IPL Inspector** will open.

---

## GUI overview / workflow

* **File → Open Binary IPL** — choose a `.ipl` file. The tool verifies the `bnry` magic and reads the 18×uint32 header.
* Two tabs appear: **INST** and **CARS**. Each contains simple editable text lines representing entries.
* Make edits directly in the text areas.
* **File → Rebuild & Save (and Reload)** — packs your edited lines into a clean/compact binary file and prompts where to save it. The tool writes to a temporary file and atomically replaces the destination (safer). Then it attempts to reload the saved file so you can verify the result.
* **File → Batch Rebuild Folder** — choose a folder. All `.ipl` files in that folder (non-recursive) will be scanned and safely repacked when possible. For skipped/complex files the original will be copied to `.bak` and left untouched. A log/progress window shows status and allows cancelling.

---

## Text formats (how to edit lines)

When editing, each line must follow the exact whitespace-separated format below. The GUI uses these when packing.

### INST (one line per instance)

```
<obj_id> <posx> <posy> <posz> <rotx> <roty> <rotz> <rotw> <flags>
```

* `obj_id` — integer object/model ID.
* `posx posy posz` — floats, world position.
* `rotx roty rotz rotw` — rotation quaternion floats (4 floats).
* `flags` — unsigned integer flags.

**Example:**

```
123 102.000000 256.500000 -5.000000 0.000000 0.000000 0.707107 0.707107 0
```

> Note: The GUI **omits** the `interior` value in the editable text (the manual rebuild path sets `interior=0` for new files). The batch/`repack_preserve` path will preserve original `interior` values when possible.

### CARS (one line per vehicle spawn)

```
<veh_id> <posx> <posy> <posz> <angle> <f1> <f2> <f3> <f4> <f5> <f6> <f7>
```

* `veh_id` — integer vehicle model ID.
* `posx posy posz` — floats, spawn position.
* `angle` — float, facing/heading.
* `f1..f7` — seven integer flags/values included in the original binary structure.

**Example:**

```
26 500.000000 600.000000 12.000000 90.000000 0 0 0 0 0 0 0
```

---

## Safety & behavior notes

* The script verifies file size and structure and will raise errors if header values or entry sizes don't match expected lengths (e.g. truncated entries).
* **Atomic writes**: saves are written to a temporary file then atomically moved into place (`os.replace`) to reduce the risk of half-written files.
* **Backups**: Batch operation always copies the original file to `*.bak` before attempting replacement. Manual rebuild also writes safely but you should keep your own backups if needed.
* **Preservation**: The `repack_preserve_from_original` code path keeps the original `interior` field and numeric fields when rebuilding. However, if the file contains other non-zero/unknown offsets/sections the script refuses to rewrite the file to avoid corruption and instead creates a `.bak`.
* **Skip behavior**: Files judged "complex" (contain unknown non-zero offsets) will be skipped and backed up during batch operations — this avoids accidental corruption of uncommon or extended formats.
* **Error messages**: If you see errors like "magic 'bnry' missing" or "truncated entry", the file is likely not the expected format or is corrupted.

---

## Troubleshooting tips

* If a file fails to open with "magic 'bnry' missing", ensure it's the correct binary `.ipl` format and not a plain-text `.ipl`.
* If lines fail to rebuild, inspect the line count and whitespace-separated values — the UI expects the exact number of numeric fields per line (9 for INST, 12 for CARS).
* Use Batch Rebuild to process many files safely; examine the per-file log to see which files were skipped and why.
* If the GUI hangs while batch processing, try cancelling using the Batch window "Cancel" button; the tool supports cooperative cancellation.

---

## Limitations

* The editable UI omits the `interior` field for manual rebuilds and sets it to `0`. Use the batch "preserve" path when you need to keep original interior values.
* The tool assumes a fairly compact file format — files with additional custom sections or non-zero unknown offsets will not be rewritten.
* Parsing and packing are strictly size-checked; malformed files will be rejected rather than silently corrupted.

---

## Example workflow

1. Open `myfile.ipl` via **File → Open Binary IPL**.
2. Edit `INST` entries to adjust positions/rotations or `CARS` spawns.
3. Use **File → Rebuild & Save (and Reload)** and pick a filename (you’ll get a prompt to save).
4. The tool will save atomically, attempt to reload the saved file, and show a success message.

For bulk fixes, use **File → Batch Rebuild Folder** and pick the folder containing `.ipl` files.

---

## License
This README and the accompanying script are provided under the **MIT License** — feel free to reuse and modify with attribution.
