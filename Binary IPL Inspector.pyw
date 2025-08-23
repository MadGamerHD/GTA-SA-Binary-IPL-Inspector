# Full updated script (safe batch rebuild)
import struct
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import os
import tempfile
import shutil

HEADER_FORMAT = "<IIIIIIIIIIIIIIIIII"  # 18 x uint32 after 'bnry'
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
MAGIC = b"bnry"

# Entry sizes
INST_SIZE = 40  # 7f + i + i + I
CARS_SIZE = 48  # 4f + i + 7i


class IPLInspector(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Binary IPL Inspector")
        self.geometry("1000x600")

        # Menu
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open Binary IPL", command=self.open_file)
        file_menu.add_separator()
        file_menu.add_command(label="Rebuild & Save (and Reload)", command=self.rebuild_file)
        file_menu.add_command(label="Batch Rebuild Folder", command=self.batch_rebuild_folder)
        menubar.add_cascade(label="File", menu=file_menu)
        self.config(menu=menubar)

        # Tabs for INST and CARS
        self.tab_control = ttk.Notebook(self)
        self.inst_tab = tk.Frame(self.tab_control)
        self.cars_tab = tk.Frame(self.tab_control)
        self.tab_control.add(self.inst_tab, text="INST")
        self.tab_control.add(self.cars_tab, text="CARS")
        self.tab_control.pack(expand=1, fill="both")

        # INST Text (no visible scrollbar as requested)
        self.inst_text = tk.Text(self.inst_tab, wrap="none")
        self.inst_text.pack(expand=1, fill="both", padx=6, pady=6)

        # CARS Text (no visible scrollbar as requested)
        self.cars_text = tk.Text(self.cars_tab, wrap="none")
        self.cars_text.pack(expand=1, fill="both", padx=6, pady=6)

        # Keep last opened path
        self.current_path = None

        # Batch control
        self._batch_cancel_event = None
        self._batch_thread = None

    # -------------------------
    # Original file open / read
    # -------------------------
    def open_file(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("Binary IPL", "*.ipl"), ("All files", "*.*")]
        )
        if not file_path:
            return
        try:
            self.read_binary_ipl(file_path)
            self.current_path = file_path
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file:\n{e}")

    def read_binary_ipl(self, file_path):
        with open(file_path, "rb") as f:
            data = f.read()

        if len(data) < 4 + HEADER_SIZE:
            raise ValueError("File too small to be a valid binary IPL.")

        if data[:4] != MAGIC:
            raise ValueError("Not a valid binary IPL (magic 'bnry' missing).")

        # Unpack header right after 'bnry'
        header = struct.unpack(HEADER_FORMAT, data[4:4 + HEADER_SIZE])
        (
            num_instances, unk1, unk2, unk3, num_cars, unk4,
            offset_inst, unused1,
            offset_unk1, unused2,
            offset_unk2, unused3,
            offset_unk3, unused4,
            offset_cars, unused5,
            offset_unk4, unused6
        ) = header

        # Clear text boxes
        self.inst_text.delete("1.0", tk.END)
        self.cars_text.delete("1.0", tk.END)

        # ---- Parse INST ----
        if num_instances > 0:
            if offset_inst == 0:
                raise ValueError("Header says INST entries exist but offset_inst is 0.")
            for i in range(num_instances):
                start = offset_inst + i * INST_SIZE
                end = start + INST_SIZE
                chunk = data[start:end]
                if len(chunk) != INST_SIZE:
                    raise ValueError(f"INST entry {i} is truncated.")
                # <7f i i I -> pos(3f), rot(4f), obj_id(int), interior(int), flags(uint)
                posx, posy, posz, rotx, roty, rotz, rotw, obj_id, interior, flags = struct.unpack("<7f i i I", chunk)
                # Write in simple editable text format (interior omitted; always 0 in UI)
                self.inst_text.insert(
                    tk.END,
                    f"{obj_id} {posx:.6f} {posy:.6f} {posz:.6f} "
                    f"{rotx:.6f} {roty:.6f} {rotz:.6f} {rotw:.6f} "
                    f"{flags}\n"
                )

        # ---- Parse CARS ----
        if num_cars > 0:
            if offset_cars == 0:
                raise ValueError("Header says CARS entries exist but offset_cars is 0.")
            for i in range(num_cars):
                start = offset_cars + i * CARS_SIZE
                end = start + CARS_SIZE
                chunk = data[start:end]
                if len(chunk) != CARS_SIZE:
                    raise ValueError(f"CARS entry {i} is truncated.")
                # <4f i 7i -> pos(3f), angle(f), vehicle_id(int), flags[7]
                posx, posy, posz, angle, veh_id, f1, f2, f3, f4, f5, f6, f7 = struct.unpack("<4f i 7i", chunk)
                self.cars_text.insert(
                    tk.END,
                    f"{veh_id} {posx:.6f} {posy:.6f} {posz:.6f} "
                    f"{angle:.6f} {f1} {f2} {f3} {f4} {f5} {f6} {f7}\n"
                )

        messagebox.showinfo(
            "Loaded",
            f"Loaded {num_instances} INST and {num_cars} CARS from:\n{file_path}"
        )

    # -------------------------
    # GUI-triggered rebuild (original)
    # -------------------------
    def rebuild_file(self):
        # Read lines from text boxes
        inst_lines = [ln.strip() for ln in self.inst_text.get("1.0", tk.END).strip().splitlines() if ln.strip()]
        car_lines = [ln.strip() for ln in self.cars_text.get("1.0", tk.END).strip().splitlines() if ln.strip()]

        try:
            packed = self._pack_from_text_lines(inst_lines, car_lines)
        except ValueError as e:
            messagebox.showerror("Rebuild Error", str(e))
            return

        save_path = filedialog.asksaveasfilename(
            defaultextension=".ipl",
            filetypes=[("Binary IPL", "*.ipl"), ("All files", "*.*")]
        )
        if not save_path:
            return

        try:
            # write atomically
            dir_name = os.path.dirname(save_path) or "."
            fd, tmp = tempfile.mkstemp(prefix=".tmp_ipl_", dir=dir_name)
            os.close(fd)
            with open(tmp, "wb") as f:
                f.write(packed)
            os.replace(tmp, save_path)
        except Exception as e:
            messagebox.showerror("Rebuild Error", f"Could not write file:\n{e}")
            return

        # Auto-reload the newly saved file so you can verify immediately
        try:
            self.read_binary_ipl(save_path)
            self.current_path = save_path
        except Exception as e:
            messagebox.showwarning(
                "Saved (Reload Failed)",
                f"File saved to:\n{save_path}\n\nBut reload failed:\n{e}"
            )
            return

        messagebox.showinfo("Rebuilt", f"Recompiled, saved, and reloaded:\n{save_path}")

    # -------------------------
    # Helper: pack from lines (used by rebuild)
    # -------------------------
    def _pack_from_text_lines(self, inst_lines, car_lines):
        inst_blobs = []
        for i, line in enumerate(inst_lines):
            parts = line.split()
            if len(parts) < 9:
                raise ValueError(f"INST line {i+1} has too few values.\nExpected 9 values.")
            try:
                obj_id = int(parts[0])
                posx, posy, posz = map(float, parts[1:4])
                rotx, roty, rotz, rotw = map(float, parts[4:8])
                flags = int(parts[8])
            except ValueError:
                raise ValueError(f"INST line {i+1} contains invalid numbers.")
            interior = 0
            inst_blobs.append(struct.pack("<7f i i I", posx, posy, posz, rotx, roty, rotz, rotw, obj_id, interior, flags))

        car_blobs = []
        for i, line in enumerate(car_lines):
            parts = line.split()
            if len(parts) < 12:
                raise ValueError(f"CARS line {i+1} has too few values.\nExpected 12 values.")
            try:
                veh_id = int(parts[0])
                posx, posy, posz = map(float, parts[1:4])
                angle = float(parts[4])
                f1, f2, f3, f4, f5, f6, f7 = map(int, parts[5:12])
            except ValueError:
                raise ValueError(f"CARS line {i+1} contains invalid numbers.")
            car_blobs.append(struct.pack("<4f i 7i", posx, posy, posz, angle, veh_id, f1, f2, f3, f4, f5, f6, f7))

        num_instances = len(inst_blobs)
        num_cars = len(car_blobs)

        base_offset = 4 + HEADER_SIZE
        offset_inst = base_offset if num_instances > 0 else 0
        offset_cars = (offset_inst + num_instances * INST_SIZE) if num_cars > 0 else 0

        header = struct.pack(
            HEADER_FORMAT,
            num_instances, 0, 0, 0,
            num_cars, 0,
            offset_inst, 0,
            0, 0,
            0, 0,
            0, 0,
            offset_cars, 0,
            0, 0
        )

        out = bytearray()
        out += MAGIC
        out += header
        for blob in inst_blobs:
            out += blob
        for blob in car_blobs:
            out += blob
        return bytes(out)

    # -------------------------
    # New helper: repack by reusing numeric values from original file (preserve interior)
    # -------------------------
    def _repack_preserve_from_original(self, data):
        """Return packed bytes, preserving original interior values and numeric values.
        Raises ValueError if file is malformed or contains extra (non-zero) unknown offsets
        — in which case caller should skip or backup+copy the file instead of repacking."""
        if len(data) < 4 + HEADER_SIZE:
            raise ValueError("File too small to be a valid binary IPL.")
        if data[:4] != MAGIC:
            raise ValueError("Not a valid binary IPL (magic 'bnry' missing).")

        header = struct.unpack(HEADER_FORMAT, data[4:4 + HEADER_SIZE])
        (
            num_instances, unk1, unk2, unk3, num_cars, unk4,
            offset_inst, unused1,
            offset_unk1, unused2,
            offset_unk2, unused3,
            offset_unk3, unused4,
            offset_cars, unused5,
            offset_unk4, unused6
        ) = header

        # If file contains any other non-zero offsets/sections we don't understand,
        # avoid rewriting it (safer).
        # If your files always have 0 for those, this will be fine.
        other_offsets = (unk1, unk2, unk3, unk4, unused1, unused2, unused3, unused4, unused5, unused6,
                         offset_unk1, offset_unk2, offset_unk3, offset_unk4)
        # We allow those to be zero only. If any non-zero, raise to indicate "complex file".
        if any(v != 0 for v in other_offsets):
            raise ValueError("File contains extra/unknown sections; skipping rewrite to avoid corruption.")

        inst_blobs = []
        car_blobs = []

        # read INST raw entries and preserve interior when re-packing
        if num_instances > 0:
            if offset_inst == 0 or offset_inst + num_instances * INST_SIZE > len(data):
                raise ValueError("INST offset/size out of bounds.")
            for i in range(num_instances):
                start = offset_inst + i * INST_SIZE
                chunk = data[start:start + INST_SIZE]
                if len(chunk) != INST_SIZE:
                    raise ValueError(f"INST entry {i} is truncated.")
                # unpack: posx,posy,posz,rotx,roty,rotz,rotw,obj_id,interior,flags
                posx, posy, posz, rotx, roty, rotz, rotw, obj_id, interior, flags = struct.unpack("<7f i i I", chunk)
                # pack using original interior
                inst_blobs.append(struct.pack("<7f i i I", posx, posy, posz, rotx, roty, rotz, rotw, obj_id, interior, flags))

        if num_cars > 0:
            if offset_cars == 0 or offset_cars + num_cars * CARS_SIZE > len(data):
                raise ValueError("CARS offset/size out of bounds.")
            for i in range(num_cars):
                start = offset_cars + i * CARS_SIZE
                chunk = data[start:start + CARS_SIZE]
                if len(chunk) != CARS_SIZE:
                    raise ValueError(f"CARS entry {i} is truncated.")
                posx, posy, posz, angle, veh_id, f1, f2, f3, f4, f5, f6, f7 = struct.unpack("<4f i 7i", chunk)
                car_blobs.append(struct.pack("<4f i 7i", posx, posy, posz, angle, veh_id, f1, f2, f3, f4, f5, f6, f7))

        # Now rebuild header/offsets in the compact form (same as manual rebuild previously)
        num_instances = len(inst_blobs)
        num_cars = len(car_blobs)

        base_offset = 4 + HEADER_SIZE
        offset_inst_new = base_offset if num_instances > 0 else 0
        offset_cars_new = (offset_inst_new + num_instances * INST_SIZE) if num_cars > 0 else 0

        header_new = struct.pack(
            HEADER_FORMAT,
            num_instances, 0, 0, 0,   # num_instances, unk1..3
            num_cars, 0,              # num_cars, unk4
            offset_inst_new, 0,           # offset_inst, unused
            0, 0,                     # offset_unk1, unused
            0, 0,                     # offset_unk2, unused
            0, 0,                     # offset_unk3, unused
            offset_cars_new, 0,           # offset_cars, unused
            0, 0                      # offset_unk4, unused
        )

        out = bytearray()
        out += MAGIC
        out += header_new
        for blob in inst_blobs:
            out += blob
        for blob in car_blobs:
            out += blob
        return bytes(out)

    # -------------------------
    # Batch rebuild UI + logic (safe version)
    # -------------------------
    def batch_rebuild_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return

        # find .ipl files (non-recursive)
        files = [f for f in os.listdir(folder) if f.lower().endswith(".ipl")]
        if not files:
            messagebox.showinfo("Nothing to do", f"No .ipl files found in:\n{folder}")
            return

        # create progress window
        win = tk.Toplevel(self)
        win.title("Batch Rebuild")
        win.geometry("600x300")
        win.transient(self)

        lbl = tk.Label(win, text=f"Rebuilding {len(files)} .ipl files in:\n{folder}")
        lbl.pack(padx=8, pady=(8, 0))

        progress = ttk.Progressbar(win, maximum=len(files), mode="determinate")
        progress.pack(fill="x", padx=8, pady=8)

        log = tk.Text(win, height=10, wrap="word")
        log.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        btn_frame = tk.Frame(win)
        btn_frame.pack(fill="x", padx=8, pady=(0, 8))
        cancel_btn = tk.Button(btn_frame, text="Cancel", width=10)
        cancel_btn.pack(side="right")

        # cancellation event
        cancel_event = threading.Event()
        self._batch_cancel_event = cancel_event

        def append_log(msg):
            log.insert(tk.END, msg + "\n")
            log.see("end")

        def set_progress(val):
            progress["value"] = val

        def worker():
            succeeded = 0
            for idx, name in enumerate(files, start=1):
                if cancel_event.is_set():
                    self.after(0, append_log, "Batch cancelled by user.")
                    break
                full = os.path.join(folder, name)
                bak = full + ".bak"
                try:
                    with open(full, "rb") as f:
                        data = f.read()
                    try:
                        packed = self._repack_preserve_from_original(data)
                    except ValueError as ve:
                        # Don't rewrite complex files — instead make a backup and skip
                        shutil.copy2(full, bak)
                        self.after(0, append_log, f"[SKIP] {name} -> {ve} (backup .bak saved)")
                        self.after(0, set_progress, idx)
                        continue

                    # make a backup first
                    shutil.copy2(full, bak)

                    # write to temp then replace
                    fd, tmp = tempfile.mkstemp(prefix=".tmp_ipl_", dir=folder)
                    os.close(fd)
                    with open(tmp, "wb") as tf:
                        tf.write(packed)
                    os.replace(tmp, full)  # atomic replace
                    succeeded += 1
                    self.after(0, append_log, f"[OK] {name} -> backup: {os.path.basename(bak)}")
                except Exception as e:
                    try:
                        if 'tmp' in locals() and os.path.exists(tmp):
                            os.remove(tmp)
                    except Exception:
                        pass
                    self.after(0, append_log, f"[ERR] {name} -> {e}")
                # update progress
                self.after(0, set_progress, idx)
            # finished
            self.after(0, append_log, f"Batch finished. Succeeded: {succeeded}/{len(files)}")
            self.after(0, lambda: cancel_btn.config(text="Close", command=win.destroy))
            # clear event reference
            self._batch_cancel_event = None

        def on_cancel():
            if self._batch_cancel_event and not self._batch_cancel_event.is_set():
                # set to cancel and disable button
                self._batch_cancel_event.set()
                cancel_btn.config(state="disabled", text="Cancelling...")
            else:
                win.destroy()

        cancel_btn.config(command=on_cancel)

        # start thread
        self._batch_thread = threading.Thread(target=worker, daemon=True)
        self._batch_thread.start()

    # -------------------------
    # Clean exit: attempt to cancel background work
    # -------------------------
    def destroy(self):
        # If a batch is running, ask before exit
        if self._batch_thread and self._batch_thread.is_alive():
            if messagebox.askyesno("Exit", "A batch rebuild is running. Do you want to cancel and exit?"):
                if self._batch_cancel_event:
                    self._batch_cancel_event.set()
            else:
                return
        super().destroy()


if __name__ == "__main__":
    app = IPLInspector()
    app.mainloop()