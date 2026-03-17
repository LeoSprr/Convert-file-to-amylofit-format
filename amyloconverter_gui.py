import os
import sys
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import amyloconverter as core


class QueueStream:
    def __init__(self, q):
        self.q = q

    def write(self, text):
        if text:
            self.q.put(("log", text))

    def flush(self):
        pass


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, current_settings):
        super().__init__(parent)
        self.title("Settings")
        self.resizable(False, False)
        self.result = None
        self._build(current_settings)
        self.lift()
        self.focus_force()
        self.grab_set()
        self.wait_window()

    def _build(self, s):
        pad = {"padx": 12, "pady": 6}

        tk.Label(self, text="Plate reader", font=("", 10, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", **pad)

        self.reader_var = tk.StringVar(value=s.get("plate_reader", "fluostar"))
        tk.Radiobutton(self, text="FLUOstar Omega", variable=self.reader_var,
                       value="fluostar", command=self._toggle_roof).grid(
            row=1, column=0, columnspan=2, sticky="w", padx=24)
        tk.Radiobutton(self, text="Other / auto-detect", variable=self.reader_var,
                       value="auto", command=self._toggle_roof).grid(
            row=2, column=0, columnspan=2, sticky="w", padx=24)

        tk.Label(self, text=f"Using a different reader? Send an example file to {core.CONTACT_EMAIL}",
                 font=("", 8), fg="gray").grid(row=3, column=0, columnspan=2, sticky="w", padx=24, pady=(0, 4))

        ttk.Separator(self, orient="horizontal").grid(row=4, column=0, columnspan=2, sticky="ew", pady=8)

        tk.Label(self, text="Roof value", font=("", 10, "bold")).grid(
            row=5, column=0, columnspan=2, sticky="w", **pad)

        self.roof_auto_var = tk.BooleanVar(value=s.get("roof_mode", "fixed") == "auto")
        self.roof_auto_cb = tk.Checkbutton(self, text="Auto-detect from data",
                                            variable=self.roof_auto_var, command=self._toggle_roof)
        self.roof_auto_cb.grid(row=6, column=0, columnspan=2, sticky="w", padx=24)

        tk.Label(self, text="Fixed value:").grid(row=7, column=0, sticky="w", padx=24)
        self.roof_entry = tk.Entry(self, width=12)
        self.roof_entry.insert(0, str(s.get("roof_value", 260000)))
        self.roof_entry.grid(row=7, column=1, sticky="w", pady=4)

        ttk.Separator(self, orient="horizontal").grid(row=8, column=0, columnspan=2, sticky="ew", pady=8)

        tk.Label(self, text="Chromatic selection", font=("", 10, "bold")).grid(
            row=9, column=0, columnspan=2, sticky="w", **pad)

        self.chrom_var = tk.StringVar(value=s.get("chromatic_mode", "auto"))
        tk.Radiobutton(self, text="Auto (pick best chromatic automatically)",
                       variable=self.chrom_var, value="auto").grid(
            row=10, column=0, columnspan=2, sticky="w", padx=24)
        tk.Radiobutton(self, text="Manual (choose from table each run)",
                       variable=self.chrom_var, value="manual").grid(
            row=11, column=0, columnspan=2, sticky="w", padx=24)

        ttk.Separator(self, orient="horizontal").grid(row=12, column=0, columnspan=2, sticky="ew", pady=8)

        btn_frame = tk.Frame(self)
        btn_frame.grid(row=13, column=0, columnspan=2, pady=(0, 12))
        tk.Button(btn_frame, text="Save", width=10, command=self._save).pack(side="left", padx=6)
        tk.Button(btn_frame, text="Cancel", width=10, command=self.destroy).pack(side="left", padx=6)

        self._toggle_roof()

    def _toggle_roof(self):
        is_fluostar = self.reader_var.get() == "fluostar"
        is_auto = self.roof_auto_var.get()
        self.roof_auto_cb.config(state="disabled" if is_fluostar else "normal")
        self.roof_entry.config(state="disabled" if (is_fluostar or is_auto) else "normal")

    def _save(self):
        settings = {}
        settings["plate_reader"] = self.reader_var.get()

        if settings["plate_reader"] == "fluostar":
            settings["roof_mode"] = "fixed"
            settings["roof_value"] = 260000
        elif self.roof_auto_var.get():
            settings["roof_mode"] = "auto"
        else:
            raw = self.roof_entry.get().strip()
            if not raw.isdigit():
                messagebox.showerror("Invalid", "Roof value must be a whole number.", parent=self)
                return
            settings["roof_mode"] = "fixed"
            settings["roof_value"] = int(raw)

        settings["chromatic_mode"] = self.chrom_var.get()
        self.result = settings
        self.destroy()


class ChromaticDialog(tk.Toplevel):
    def __init__(self, parent, table, all_chroms):
        super().__init__(parent)
        self.title("Select Chromatic")
        self.resizable(False, False)
        self.result = None
        self._build(table, all_chroms)
        self.grab_set()
        self.wait_window()

    def _build(self, table, all_chroms):
        tk.Label(self, text="Select which chromatic to export:",
                 font=("", 10, "bold")).grid(row=0, column=0, columnspan=4, padx=12, pady=(12, 4), sticky="w")

        for col, heading in enumerate(("", "Chromatic", "Saturated Wells", "Total Wells")):
            tk.Label(self, text=heading, font=("", 9, "bold")).grid(row=1, column=col, padx=8)

        self.chrom_var = tk.StringVar(value=all_chroms[0])

        for i, (chrom, saturated, total) in enumerate(table):
            tk.Radiobutton(self, variable=self.chrom_var, value=chrom).grid(row=i + 2, column=0, padx=(12, 0))
            tk.Label(self, text=chrom).grid(row=i + 2, column=1, padx=8, pady=2)
            tk.Label(self, text=str(saturated)).grid(row=i + 2, column=2, padx=8)
            tk.Label(self, text=str(total)).grid(row=i + 2, column=3, padx=8)

        btn_frame = tk.Frame(self)
        btn_frame.grid(row=len(table) + 2, column=0, columnspan=4, pady=12)
        tk.Button(btn_frame, text="Select", width=10, command=self._confirm).pack(side="left", padx=6)
        tk.Button(btn_frame, text="Cancel", width=10, command=self.destroy).pack(side="left", padx=6)

    def _confirm(self):
        self.result = self.chrom_var.get()
        self.destroy()


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("AmyloConverter")
        self.root.minsize(580, 520)

        self.log_queue = queue.Queue()
        self.chromatic_request_queue = queue.Queue()
        self.chromatic_result_queue = queue.Queue()
        self._file_list = []

        self._build_ui()
        self._poll()

        if core.load_settings() is None:
            self._log("No settings found — please configure before converting.\n")
            self.root.after(200, self._open_settings)

    def _build_ui(self):
        # ── File list section ──────────────────────────────────────────────────
        file_frame = tk.LabelFrame(self.root, text="Input files", padx=8, pady=6)
        file_frame.pack(fill="both", expand=False, padx=12, pady=(12, 4))

        btn_row = tk.Frame(file_frame)
        btn_row.pack(fill="x", pady=(0, 6))
        tk.Button(btn_row, text="Add Files", command=self._add_files).pack(side="left", padx=(0, 4))
        tk.Button(btn_row, text="Add Folder", command=self._add_folder).pack(side="left", padx=(0, 4))
        tk.Button(btn_row, text="Remove Selected", command=self._remove_selected).pack(side="left", padx=(0, 4))
        tk.Button(btn_row, text="Clear All", command=self._clear_files).pack(side="left")

        list_frame = tk.Frame(file_frame)
        list_frame.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical")
        self.file_listbox = tk.Listbox(list_frame, height=6, selectmode="single",
                                        yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.file_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.file_listbox.pack(side="left", fill="both", expand=True)

        tk.Label(file_frame,
                 text="⚠  Files are merged in the order shown. Name them part1, part2... or add them in sequence.",
                 font=("", 8), fg="#b05000").pack(anchor="w", pady=(6, 0))

        # ── Action buttons ─────────────────────────────────────────────────────
        action_row = tk.Frame(self.root)
        action_row.pack(fill="x", padx=12, pady=6)
        self.convert_btn = tk.Button(action_row, text="Convert", width=12, command=self._convert)
        self.convert_btn.pack(side="left", padx=(0, 6))
        tk.Button(action_row, text="Settings", width=12, command=self._open_settings).pack(side="left")

        # ── Log area ───────────────────────────────────────────────────────────
        log_frame = tk.LabelFrame(self.root, text="Log", padx=4, pady=4)
        log_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.log_text = tk.Text(log_frame, state="disabled", wrap="word",
                                 bg="#1e1e1e", fg="#d4d4d4", font=("Courier", 10),
                                 relief="flat")
        log_scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.config(yscrollcommand=log_scroll.set)
        log_scroll.pack(side="right", fill="y")
        self.log_text.pack(side="left", fill="both", expand=True)

    def _add_files(self):
        paths = filedialog.askopenfilenames(
            title="Select CSV files",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        for p in paths:
            if p not in self._file_list:
                self._file_list.append(p)
        self._refresh_listbox()

    def _add_folder(self):
        import glob as _glob
        folder = filedialog.askdirectory(title="Select folder containing CSV files")
        if not folder:
            return
        found = sorted(_glob.glob(os.path.join(folder, "*.csv")))
        if not found:
            messagebox.showwarning("No CSV files", "No CSV files found in that folder.")
            return
        for p in found:
            if p not in self._file_list:
                self._file_list.append(p)
        self._refresh_listbox()

    def _remove_selected(self):
        sel = self.file_listbox.curselection()
        if sel:
            self._file_list.pop(sel[0])
            self._refresh_listbox()

    def _clear_files(self):
        self._file_list.clear()
        self._refresh_listbox()

    def _refresh_listbox(self):
        self._file_list = sorted(self._file_list, key=lambda p: os.path.basename(p).lower())
        self.file_listbox.delete(0, "end")
        for p in self._file_list:
            self.file_listbox.insert("end", os.path.basename(p))

    def _open_settings(self):
        current = core.load_settings() or {}
        dlg = SettingsDialog(self.root, current)
        if dlg.result:
            core.save_settings(dlg.result)
            self._log("Settings saved.\n")

    def _convert(self):
        if not self._file_list:
            messagebox.showwarning("No files", "Please add CSV files first.")
            return

        settings = core.load_settings()
        if settings is None:
            self._log("No settings found — opening setup.\n")
            self._open_settings()
            settings = core.load_settings()
            if settings is None:
                return

        self.convert_btn.config(state="disabled")
        self._log(f"\n--- Starting conversion ({len(self._file_list)} file(s)) ---\n")

        files = list(self._file_list)
        t = threading.Thread(target=self._worker, args=(files, settings), daemon=True)
        t.start()

    def _worker(self, files, settings):
        old_stdout = sys.stdout
        sys.stdout = QueueStream(self.log_queue)
        try:
            self._run_conversion(files, settings)
        except Exception as e:
            self.log_queue.put(("log", f"\nUnexpected error: {e}\n"))
        finally:
            sys.stdout = old_stdout
            self.log_queue.put(("done",))

    def _run_conversion(self, files, settings):
        output_dir = os.path.dirname(os.path.abspath(files[0]))
        original_dir = os.getcwd()
        try:
            os.chdir(output_dir)

            print("Files being processed:")
            for f in files:
                print(f"  {os.path.basename(f)}")

            reader = settings.get("plate_reader", "auto")

            try:
                data = core.merge_files(files, reader)
            except ValueError as e:
                print(f"Error reading files: {e}")
                return

            if not data:
                print("No chromatic data could be read from the files.")
                print("Try opening Settings and switching to auto-detect mode.")
                return

            if settings.get("roof_mode") == "fixed":
                roof_value = settings["roof_value"]
                print(f"Roof value (from settings): {roof_value}")
            else:
                roof_value = core.detect_roof_value(data)
                print(f"Roof value (auto-detected): {roof_value}")

            all_chroms = sorted(data.keys(), key=core._chrom_sort_key)

            if settings.get("chromatic_mode", "auto") == "auto":
                selected = core.auto_select_chromatic(data, roof_value)
                print(f"\n{'Chromatic':<12} {'Saturated Wells':<18} {'Total Wells'}")
                print("-" * 44)
                for chrom in all_chroms:
                    total = len(data[chrom]["wells"])
                    saturated = core.count_saturated_wells(data[chrom], roof_value)
                    marker = " <-- selected" if chrom == selected else ""
                    print(f"{chrom:<12} {saturated:<18} {total}{marker}")
                print(f"\nAuto-selected chromatic: {selected}")
            else:
                table = [
                    (chrom,
                     core.count_saturated_wells(data[chrom], roof_value),
                     len(data[chrom]["wells"]))
                    for chrom in all_chroms
                ]
                self.chromatic_request_queue.put((table, all_chroms))
                selected = self.chromatic_result_queue.get()
                if selected is None:
                    print("Conversion cancelled.")
                    return
                print(f"Selected chromatic: {selected}")

            core.export_split_files(data[selected]["time"], data[selected]["wells"])
            print(f"\nDone. Output files saved to: {output_dir}")

        finally:
            os.chdir(original_dir)

    def _poll(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                if msg[0] == "done":
                    self.convert_btn.config(state="normal")
                else:
                    self._log(msg[1])
        except queue.Empty:
            pass

        try:
            table, all_chroms = self.chromatic_request_queue.get_nowait()
            dlg = ChromaticDialog(self.root, table, all_chroms)
            self.chromatic_result_queue.put(dlg.result)
        except queue.Empty:
            pass

        self.root.after(100, self._poll)

    def _log(self, text):
        self.log_text.config(state="normal")
        self.log_text.insert("end", text)
        self.log_text.see("end")
        self.log_text.config(state="disabled")


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
