from __future__ import annotations

import argparse
import queue
import threading
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .asc_header import read_header
from .csv_export import export_csv
from .dxf_export import automatic_datum, export_dxf
from .extent_scan import GK_CHOICES, ExtentScanResult, choice_for_epsg, discover_gk_folders, parse_user_float, scan_extent
from .index import AscGridIndex
from .models import SamplePoint2d
from .sampler import SectionSampler

ROOT_EXAMPLE = r"\\grid.inet\data\Proj_K\EGIS_Vermessung\Laserscan\OpenData Geländemodelle\DGM\1m\asc\2025.07"


class GuiLauncher(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("ASC_SCHNITT GUI Launcher")
        self.geometry("1020x760")
        self._queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._scan_result: ExtentScanResult | None = None
        self._busy = False

        self.root_var = tk.StringVar()
        self.epsg_var = tk.StringVar(value=str(GK_CHOICES[0].epsg))
        self.start_x_var = tk.StringVar()
        self.start_y_var = tk.StringVar()
        self.end_x_var = tk.StringVar()
        self.end_y_var = tk.StringVar()
        self.output_folder_var = tk.StringVar(value=str(Path.cwd() / "output"))
        self.spacing_var = tk.StringVar(value="1.0")
        self.vertical_exaggeration_var = tk.StringVar(value="1.0")
        self.insertion_x_var = tk.StringVar(value="0.0")
        self.insertion_y_var = tk.StringVar(value="0.0")
        self.basename_var = tk.StringVar(value=self._default_basename())

        self._build_widgets()
        self.after(100, self._poll_queue)

    def _build_widgets(self) -> None:
        main = ttk.Frame(self, padding=12)
        main.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(7, weight=1)

        ttk.Label(main, text="ASC root folder").grid(row=0, column=0, sticky="w")
        ttk.Entry(main, textvariable=self.root_var).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(main, text="Browse…", command=self._browse_root).grid(row=0, column=2, sticky="ew")
        ttk.Label(main, text=f"Example: {ROOT_EXAMPLE}", foreground="gray").grid(row=1, column=1, sticky="w", pady=(0, 8))

        epsg_frame = ttk.LabelFrame(main, text="Coordinate system / ASC folder (no coordinate transformation is performed)", padding=8)
        epsg_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=4)
        for index, choice in enumerate(GK_CHOICES):
            ttk.Radiobutton(
                epsg_frame,
                text=choice.display_name,
                value=str(choice.epsg),
                variable=self.epsg_var,
                command=self._epsg_changed,
            ).grid(row=0, column=index, sticky="w", padx=(0, 24))

        buttons = ttk.Frame(main)
        buttons.grid(row=3, column=0, columnspan=3, sticky="ew", pady=6)
        self.scan_button = ttk.Button(buttons, text="Scan ASC folders", command=self._start_scan)
        self.scan_button.pack(side="left")
        self.run_button = ttk.Button(buttons, text="Run Schnitt", command=self._start_run)
        self.run_button.pack(side="left", padx=8)

        coord_frame = ttk.LabelFrame(main, text="Section coordinates", padding=8)
        coord_frame.grid(row=4, column=0, columnspan=3, sticky="ew", pady=4)
        for col in range(4):
            coord_frame.columnconfigure(col, weight=1)
        self._labeled_entry(coord_frame, "Start X", self.start_x_var, 0, 0)
        self._labeled_entry(coord_frame, "Start Y", self.start_y_var, 0, 1)
        self._labeled_entry(coord_frame, "End X", self.end_x_var, 0, 2)
        self._labeled_entry(coord_frame, "End Y", self.end_y_var, 0, 3)

        output_frame = ttk.LabelFrame(main, text="Output", padding=8)
        output_frame.grid(row=5, column=0, columnspan=3, sticky="ew", pady=4)
        output_frame.columnconfigure(1, weight=1)
        ttk.Label(output_frame, text="Output folder").grid(row=0, column=0, sticky="w")
        ttk.Entry(output_frame, textvariable=self.output_folder_var).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(output_frame, text="Browse…", command=self._browse_output).grid(row=0, column=2, sticky="ew")
        ttk.Label(output_frame, text="Output base name").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(output_frame, textvariable=self.basename_var).grid(row=1, column=1, sticky="ew", padx=6, pady=(6, 0))

        options_frame = ttk.LabelFrame(main, text="Options", padding=8)
        options_frame.grid(row=6, column=0, columnspan=3, sticky="ew", pady=4)
        for col in range(4):
            options_frame.columnconfigure(col, weight=1)
        self._labeled_entry(options_frame, "Sample spacing", self.spacing_var, 0, 0)
        self._labeled_entry(options_frame, "Vertical exaggeration", self.vertical_exaggeration_var, 0, 1)
        self._labeled_entry(options_frame, "Insertion X", self.insertion_x_var, 0, 2)
        self._labeled_entry(options_frame, "Insertion Y", self.insertion_y_var, 0, 3)

        log_frame = ttk.LabelFrame(main, text="Status / log", padding=8)
        log_frame.grid(row=7, column=0, columnspan=3, sticky="nsew", pady=4)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, height=18, wrap="word")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scroll.set)
        self._log("Select the ASC root folder, choose an EPSG/GK zone, then click 'Scan ASC folders'.")
        self._log("Folders m28/m31/m34 contain terrain ASC data; prjxml metadata folders are ignored by default.")

    def _labeled_entry(self, parent: ttk.Frame, label: str, variable: tk.StringVar, row: int, column: int) -> None:
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=column, sticky="ew", padx=4)
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, text=label).grid(row=0, column=0, sticky="w")
        ttk.Entry(frame, textvariable=variable).grid(row=1, column=0, sticky="ew")

    def _default_basename(self) -> str:
        return "schnitt_" + datetime.now().strftime("%Y%m%d_%H%M%S")

    def _browse_root(self) -> None:
        folder = filedialog.askdirectory(title="Select ASC root folder")
        if folder:
            self.root_var.set(folder)
            self._scan_result = None

    def _browse_output(self) -> None:
        folder = filedialog.askdirectory(title="Select output folder")
        if folder:
            self.output_folder_var.set(folder)

    def _epsg_changed(self) -> None:
        self._scan_result = None
        choice = choice_for_epsg(self.epsg_var.get())
        self._log(f"Selected EPSG:{choice.epsg}. This uses folder '{choice.folder_name}' only; no coordinate transformation will be performed.")
        if self.root_var.get().strip():
            self._start_scan()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        self.scan_button.configure(state=state)
        self.run_button.configure(state=state)

    def _start_scan(self) -> None:
        if self._busy:
            return
        root = self.root_var.get().strip()
        if not root:
            messagebox.showerror("Missing ASC root folder", "Please select the root folder where m28, m31 and m34 are located.")
            return
        epsg = self.epsg_var.get()
        self._set_busy(True)
        self._log("Scanning ASC files…")
        threading.Thread(target=self._scan_worker, args=(root, epsg), daemon=True).start()

    def _scan_worker(self, root: str, epsg: str) -> None:
        try:
            found = discover_gk_folders(root)
            self._queue.put(("log", "Detected GK folders: " + (", ".join(f"EPSG:{key} -> {value}" for key, value in sorted(found.items())) or "none")))
            result = scan_extent(root, epsg)
            self._queue.put(("scan_result", result))
        except Exception as exc:  # noqa: BLE001 - show unexpected network/permission errors in GUI
            self._queue.put(("error", exc))

    def _start_run(self) -> None:
        if self._busy:
            return
        try:
            params = self._validated_run_parameters()
        except ValueError as exc:
            messagebox.showerror("Invalid input", str(exc))
            self._log(f"Input error: {exc}")
            return

        result = params["scan_result"]
        start_x = params["start_x"]
        start_y = params["start_y"]
        end_x = params["end_x"]
        end_y = params["end_y"]
        start_tile = result.point_tile(start_x, start_y)
        end_tile = result.point_tile(end_x, end_y)
        bbox_tiles = result.line_bbox_tiles(start_x, start_y, end_x, end_y)

        if not bbox_tiles:
            messagebox.showerror(
                "Coordinates outside ASC tiles",
                f"The section line does not intersect available ASC tiles for EPSG:{result.epsg}. "
                "Please check whether the coordinates are in the correct GK zone or choose another coordinate system.",
            )
            self._log("Blocked run: line bounding box does not intersect any scanned ASC tile.")
            return

        outside_messages = []
        if start_tile is None:
            outside_messages.append("start point")
        if end_tile is None:
            outside_messages.append("end point")
        if outside_messages:
            warning = (
                f"The {' and '.join(outside_messages)} are outside the available ASC tiles for EPSG:{result.epsg}. "
                "Please check whether the coordinates are in the correct GK zone or choose another coordinate system."
            )
            if not messagebox.askyesno(
                "Coordinates outside tile boundaries",
                warning + "\n\nThe line still intersects scanned ASC tiles. Continue anyway?",
            ):
                self._log("Run cancelled by user after outside-coordinate warning.")
                return
            self._log(f"User continued after warning: {warning}")

        self._set_busy(True)
        self._log(f"Start point is inside tile: {start_tile.file_path if start_tile else 'outside'}")
        self._log(f"End point is inside tile: {end_tile.file_path if end_tile else 'outside'}")
        self._log(f"Line bounding box intersects {len(bbox_tiles)} tile(s).")
        threading.Thread(target=self._run_worker, args=(params,), daemon=True).start()

    def _validated_run_parameters(self) -> dict[str, object]:
        if self._scan_result is None or self._scan_result.epsg != int(self.epsg_var.get()):
            raise ValueError("Please scan the selected EPSG/GK folder before running.")
        if not self._scan_result.tiles:
            raise ValueError(f"No ASC files are available in {self._scan_result.scan_folder}.")
        output_folder = Path(self.output_folder_var.get().strip())
        if not str(output_folder):
            raise ValueError("Please select an output folder.")
        basename = self.basename_var.get().strip() or self._default_basename()
        if any(char in basename for char in '<>:"/\\|?*'):
            raise ValueError("Output base name contains characters that are invalid in file names.")
        start_x = parse_user_float(self.start_x_var.get(), "Start X")
        start_y = parse_user_float(self.start_y_var.get(), "Start Y")
        end_x = parse_user_float(self.end_x_var.get(), "End X")
        end_y = parse_user_float(self.end_y_var.get(), "End Y")
        spacing = parse_user_float(self.spacing_var.get(), "Sample spacing")
        vertical_exaggeration = parse_user_float(self.vertical_exaggeration_var.get(), "Vertical exaggeration")
        insertion_x = parse_user_float(self.insertion_x_var.get(), "Insertion X")
        insertion_y = parse_user_float(self.insertion_y_var.get(), "Insertion Y")
        if spacing <= 0:
            raise ValueError("Sample spacing must be greater than zero.")
        if vertical_exaggeration <= 0:
            raise ValueError("Vertical exaggeration must be greater than zero.")
        try:
            output_folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ValueError(f"Output folder cannot be created or accessed: {output_folder} ({exc})") from exc
        csv_path = output_folder / f"{basename}.csv"
        dxf_path = output_folder / f"{basename}.dxf"
        return {
            "scan_result": self._scan_result,
            "output_folder": output_folder,
            "csv_path": csv_path,
            "dxf_path": dxf_path,
            "start_x": start_x,
            "start_y": start_y,
            "end_x": end_x,
            "end_y": end_y,
            "spacing": spacing,
            "vertical_exaggeration": vertical_exaggeration,
            "insertion_x": insertion_x,
            "insertion_y": insertion_y,
        }

    def _run_worker(self, params: dict[str, object]) -> None:
        try:
            result = params["scan_result"]
            assert isinstance(result, ExtentScanResult)
            self._queue.put(("log", "Building ASC tile index…"))
            index = AscGridIndex(headers=[read_header(tile.file_path) for tile in result.tiles])
            if not index.headers:
                raise RuntimeError(f"No .asc files found under {result.scan_folder}")
            start = SamplePoint2d(float(params["start_x"]), float(params["start_y"]))
            end = SamplePoint2d(float(params["end_x"]), float(params["end_y"]))
            insertion = SamplePoint2d(float(params["insertion_x"]), float(params["insertion_y"]))
            sampler = SectionSampler(index)
            self._queue.put(("log", "Sampling section…"))
            samples = sampler.sample_line(start, end, float(params["spacing"]))
            valid_count = sum(1 for sample in samples if sample.z is not None)
            if valid_count == 0:
                raise RuntimeError("No valid terrain samples found along the section line. Please check the coordinates and selected GK zone.")
            datum = automatic_datum(samples)
            csv_path = Path(params["csv_path"])
            dxf_path = Path(params["dxf_path"])
            export_csv(csv_path, samples)
            self._queue.put(("log", f"CSV exported: {csv_path}"))
            export_dxf(dxf_path, samples, start, end, insertion, datum, float(params["vertical_exaggeration"]))
            self._queue.put(("log", f"DXF exported: {dxf_path}"))
            self._queue.put(("done", (csv_path, dxf_path, valid_count, len(samples), sampler.last_candidate_count, sampler.loaded_tile_count)))
        except Exception as exc:  # noqa: BLE001 - show unexpected processing errors in GUI
            self._queue.put(("error", exc))

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "log":
                    self._log(str(payload))
                elif kind == "scan_result":
                    assert isinstance(payload, ExtentScanResult)
                    self._scan_result = payload
                    self._show_scan_result(payload)
                    self._set_busy(False)
                elif kind == "done":
                    csv_path, dxf_path, valid_count, sample_count, candidate_count, loaded_count = payload  # type: ignore[misc]
                    self._log(f"Tiles intersecting section bounding box: {candidate_count}")
                    self._log(f"Tiles loaded: {loaded_count}")
                    self._log(f"Samples: {sample_count}; valid samples: {valid_count}; invalid/NODATA samples: {sample_count - valid_count}")
                    self._log("Done.")
                    self._set_busy(False)
                    messagebox.showinfo("ASC_SCHNITT complete", f"Output files saved:\n\nCSV: {csv_path}\nDXF: {dxf_path}")
                elif kind == "error":
                    self._set_busy(False)
                    self._log(f"ERROR: {payload}")
                    messagebox.showerror("ASC_SCHNITT error", str(payload))
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    def _show_scan_result(self, result: ExtentScanResult) -> None:
        self._log(f"Selected EPSG:{result.epsg} uses folder '{result.folder_name}': {result.scan_folder}")
        self._log(f"Found {result.asc_file_count:,} ASC files in {result.folder_name}.")
        if result.tiles:
            self._log(f"Overall extent: X {result.xmin:g} to {result.xmax:g}, Y {result.ymin:g} to {result.ymax:g}")
            self._log(f"Cellsize range: {result.min_cellsize:g} to {result.max_cellsize:g}")
        for warning in result.warnings:
            self._log(f"WARNING: {warning}")
        if not result.tiles:
            messagebox.showwarning("No ASC files found", f"No valid .asc files were found in {result.scan_folder}.")

    def _log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{timestamp}] {message}\n")
        self.log_text.see("end")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start the ASC_SCHNITT Tkinter GUI launcher.")
    parser.parse_args(argv)
    app = GuiLauncher()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
