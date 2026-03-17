import os
import re
import sys
import math
import glob
import json

TARGET_FILE_BYTES    = 1_000_000
MIN_CONSECUTIVE_ROOF = 5
MIN_ROOF_IN_LAST_10  = 5
MIN_ROOF_WELL_COUNT  = 2

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
CONTACT_EMAIL = "leo.sparr@chem.lu.se"

CHROMATIC_HEADER_RE = re.compile(
    r'^(chromatic|wavelength|lambda|λ|\$\\lambda\$|read|label|'
    r'measurement|meas\.?|channel|ch|filter\s*set|step|'
    r'excitation|emission|ex\.?/em\.?|optical\s*path|acquisition)'
    r'\s*[:\s]\s*(.+)$',
    re.IGNORECASE
)

WELL_RE = re.compile(r'^[A-Ha-h]\d{0,2}$')


def parse_file_fluostar(filename):
    chromatics = {}
    current_chromatic = None

    with open(filename, "r", encoding="latin-1") as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if line.startswith("Chromatic:"):
            current_chromatic = line.split(":")[1].strip()
            chromatics[current_chromatic] = {"time": [], "wells": {}}
            i += 1
            continue

        if line.startswith("Time") and current_chromatic is not None:
            i += 1
            time_values = []
            while i < len(lines):
                tline = lines[i].strip()
                if not re.match(r'^[\d\s]+$', tline):
                    break
                time_values.extend([int(x) for x in tline.split()])
                i += 1
            chromatics[current_chromatic]["time"] = time_values
            continue

        if re.match(r'^[A-H]\d{2}', line) and current_chromatic is not None:
            parts = line.split()
            well = parts[0]
            values = list(map(int, parts[1:]))
            chromatics[current_chromatic]["wells"][well] = values

        i += 1

    return chromatics


def _detect_delimiter(content):
    candidates = ['\t', ',', ';']
    lines = [l for l in content.splitlines()[:30] if l.strip()]
    scores = {}
    for delim in candidates:
        counts = [line.count(delim) for line in lines]
        mean = sum(counts) / len(counts) if counts else 0
        if mean > 0:
            variance = sum((c - mean) ** 2 for c in counts) / len(counts)
            scores[delim] = mean / (1 + variance)
    return max(scores, key=scores.get) if scores else '\t'


def _normalize_well(name):
    m = re.match(r'^([A-Ha-h])(\d*)$', name.strip())
    if not m:
        return None
    letter = m.group(1).upper()
    digits = m.group(2)
    return f"{letter}{int(digits):02d}" if digits else letter


def _split(line, delimiter):
    return [c.strip() for c in line.split(delimiter)]


def _parse_num(s):
    try:
        return int(float(s.replace(',', '.')))
    except ValueError:
        return None


def _parse_block_format(lines, delimiter):
    chromatics = {}
    current_chromatic = None

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        m = CHROMATIC_HEADER_RE.match(line)
        if m:
            current_chromatic = m.group(2).strip()
            chromatics[current_chromatic] = {"time": [], "wells": {}}
            i += 1
            continue

        if re.match(r'^[Tt]ime', line) and current_chromatic is not None:
            parts = _split(line, delimiter)
            inline = [_parse_num(p) for p in parts[1:] if p]
            inline = [v for v in inline if v is not None]

            if inline:
                chromatics[current_chromatic]["time"] = inline
                i += 1
            else:
                i += 1
                time_values = []
                while i < len(lines):
                    tline = lines[i].strip()
                    if not tline:
                        i += 1
                        continue
                    tokens = _split(tline, delimiter)
                    parsed = [_parse_num(t) for t in tokens if t]
                    if any(v is None for v in parsed) or not parsed:
                        break
                    time_values.extend(parsed)
                    i += 1
                chromatics[current_chromatic]["time"] = time_values
            continue

        if current_chromatic is not None:
            parts = _split(line, delimiter) if delimiter != ' ' else line.split()
            if parts and WELL_RE.match(parts[0]):
                well = _normalize_well(parts[0])
                if well:
                    values = [_parse_num(v) for v in parts[1:] if v]
                    values = [v if v is not None else 0 for v in values]
                    chromatics[current_chromatic]["wells"][well] = values

        i += 1

    return chromatics


def _parse_column_format(lines, delimiter):
    time_re = re.compile(r'^[Tt]ime$')

    header_idx = None
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        cells = _split(line, delimiter)
        has_time = any(time_re.match(c) for c in cells)
        has_wells = any(WELL_RE.match(c) for c in cells)
        if has_time or has_wells:
            header_idx = i
            break

    if header_idx is None:
        raise ValueError("Could not identify a data header in the file")

    header = _split(lines[header_idx], delimiter)
    time_col = next((i for i, h in enumerate(header) if time_re.match(h)), None)

    well_cols = {i: _normalize_well(h) for i, h in enumerate(header) if WELL_RE.match(h)}
    well_cols = {k: v for k, v in well_cols.items() if v is not None}

    if not well_cols:
        raise ValueError("No well-named columns (e.g. A, A1, A01) found in the file")

    time_values = []
    well_data = {name: [] for name in well_cols.values()}

    for line in lines[header_idx + 1:]:
        if not line.strip():
            continue
        cells = _split(line, delimiter)

        if time_col is not None and time_col < len(cells):
            t = _parse_num(cells[time_col])
            if t is None:
                continue
        else:
            t = len(time_values)

        time_values.append(t)

        for col_idx, well_name in well_cols.items():
            val = _parse_num(cells[col_idx]) if col_idx < len(cells) else 0
            well_data[well_name].append(val if val is not None else 0)

    if not time_values:
        raise ValueError("No numeric data rows found in the file")

    return {"1": {"time": time_values, "wells": well_data}}


def parse_file_auto(filename):
    with open(filename, "r", encoding="latin-1") as f:
        content = f.read()

    delimiter = _detect_delimiter(content)
    lines = content.splitlines()

    if any(CHROMATIC_HEADER_RE.match(line.strip()) for line in lines):
        result = _parse_block_format(lines, delimiter)
        if result:
            return result

    return _parse_column_format(lines, delimiter)


def parse_file(filename, reader):
    if reader == "fluostar":
        return parse_file_fluostar(filename)
    return parse_file_auto(filename)


def merge_files(file_list, reader):
    merged = {}

    for file in file_list:
        data = parse_file(file, reader)

        for chrom in data:
            if chrom not in merged:
                merged[chrom] = {"time": [], "wells": {}}

            original_time = data[chrom]["time"]
            time_offset = merged[chrom]["time"][-1] if merged[chrom]["time"] else 0
            adjusted_time = [t + time_offset for t in original_time]
            merged[chrom]["time"].extend(adjusted_time)

            for well in data[chrom]["wells"]:
                if well not in merged[chrom]["wells"]:
                    merged[chrom]["wells"][well] = []
                merged[chrom]["wells"][well].extend(data[chrom]["wells"][well])

    return merged


def detect_roof_value(data):
    all_values = []
    for chrom in data:
        for well in data[chrom]["wells"]:
            all_values.extend(data[chrom]["wells"][well])

    if not all_values:
        return None

    global_max = max(all_values)
    wells_with_max = sum(
        1 for chrom in data
        for well in data[chrom]["wells"]
        if global_max in data[chrom]["wells"][well]
    )

    return global_max if wells_with_max >= MIN_ROOF_WELL_COUNT else global_max


def is_well_saturated(values, roof_value):
    max_consecutive = 0
    current_run = 0
    for v in values:
        if v == roof_value:
            current_run += 1
            if current_run > max_consecutive:
                max_consecutive = current_run
        else:
            current_run = 0

    last_10 = values[-10:]
    roof_in_last_10 = sum(1 for v in last_10 if v == roof_value)

    return max_consecutive >= MIN_CONSECUTIVE_ROOF and roof_in_last_10 >= MIN_ROOF_IN_LAST_10


def count_saturated_wells(chrom_data, roof_value):
    return sum(
        1 for well in chrom_data["wells"]
        if is_well_saturated(chrom_data["wells"][well], roof_value)
    )


def _chrom_sort_key(x):
    return int(x) if x.isdigit() else x


def auto_select_chromatic(data, roof_value):
    all_chroms = sorted(data.keys(), key=_chrom_sort_key)
    valid = [c for c in all_chroms if count_saturated_wells(data[c], roof_value) == 0]
    return min(valid, key=_chrom_sort_key) if valid else max(all_chroms, key=_chrom_sort_key)


def prompt_chromatic_selection(data, roof_value):
    all_chroms = sorted(data.keys(), key=_chrom_sort_key)

    print(f"\n{'Chromatic':<12} {'Saturated Wells':<18} {'Total Wells'}")
    print("-" * 44)
    for chrom in all_chroms:
        total = len(data[chrom]["wells"])
        saturated = count_saturated_wells(data[chrom], roof_value)
        print(f"{chrom:<12} {saturated:<18} {total}")

    options = "/".join(all_chroms)
    while True:
        choice = input(f"\nSelect chromatic [{options}]: ").strip()
        if choice in data:
            return choice
        print(f"Invalid input. Please enter one of: {options}")


def calc_wells_per_file(time, wells_dict):
    num_rows = len(time)
    if num_rows == 0:
        return 25

    start_time = time[0]
    sample_times = [(t - start_time) / 3600 for t in time[:20]]
    avg_time_width = sum(len(str(t)) for t in sample_times) / len(sample_times)

    sample_vals = []
    for well in list(wells_dict.keys())[:5]:
        sample_vals.extend(wells_dict[well][:20])
    avg_val_width = sum(len(str(v)) for v in sample_vals) / len(sample_vals) if sample_vals else 6

    bytes_per_row_base = avg_time_width + 2
    bytes_per_well = avg_val_width + 1

    max_wells = int((TARGET_FILE_BYTES / num_rows - bytes_per_row_base) / bytes_per_well)
    return max(1, max_wells)


def export_split_files(time, wells_dict):
    lab_name = os.path.basename(os.getcwd())
    wells_sorted = sorted(wells_dict.keys())
    total_wells = len(wells_sorted)
    start_time = time[0]

    wells_per_file = calc_wells_per_file(time, wells_dict)
    n_files = math.ceil(total_wells / wells_per_file)

    print(f"\nTotal wells: {total_wells}")
    print(f"Wells per file: {wells_per_file} (targeting <1 MB per file)")
    print(f"Creating {n_files} file(s)")

    for file_index in range(n_files):
        start = file_index * wells_per_file
        subset_wells = wells_sorted[start:start + wells_per_file]
        filename = f"{lab_name}_amylo_part{file_index + 1}.txt"

        with open(filename, "w") as f:
            f.write("Time\t" + "\t".join(subset_wells) + "\n")
            for i, t in enumerate(time):
                row = [str((t - start_time) / 3600)]
                row.extend(str(wells_dict[well][i]) for well in subset_wells)
                f.write("\t".join(row) + "\n")

        print(f"Exported: {filename}")


def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return None
    with open(SETTINGS_FILE, "r") as f:
        return json.load(f)


def save_settings(settings):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


def run_setup():
    print("=" * 56)
    print("  Welcome to AmyloConverter")
    print("=" * 56)
    print()
    print("This tool merges and converts raw plate reader CSV")
    print("exports into time-series files ready for analysis.")
    print()
    print("It reads chromatic data, detects which wells have")
    print("saturated (hit the ceiling of the plate reader),")
    print("and exports the data split into blocks of 25 wells.")
    print()
    print("Answer the questions below to configure the tool.")
    print("To redo this setup later, run:")
    print("  python amyloconverter.py --setup")
    print()

    settings = {}

    print("-" * 56)
    print("Plate reader")
    print("-" * 56)
    print()
    print("  1. FLUOstar Omega")
    print("  2. Other / I don't know")
    print()
    print("Using a different reader? Help expand AmyloConverter")
    print("by sending a raw example file and the reader name to:")
    print(f"  {CONTACT_EMAIL}")
    print()

    while True:
        choice = input("Your plate reader [1/2]: ").strip()
        if choice == "1":
            settings["plate_reader"] = "fluostar"
            settings["roof_mode"] = "fixed"
            settings["roof_value"] = 260000
            print("FLUOstar Omega selected. Roof value set to 260000.")
            break
        elif choice == "2":
            settings["plate_reader"] = "auto"
            print("Auto-detect selected.")
            break
        else:
            print("Please enter 1 or 2.")

    if settings["plate_reader"] == "auto":
        print()
        print("-" * 56)
        print("Plate reader roof value")
        print("-" * 56)
        print()
        print("Some plate readers cap readings at a fixed ceiling")
        print("value. If you know yours, enter it below.")
        print("If unsure, press Enter to auto-detect each run.")
        print()

        while True:
            raw = input("Roof value (or press Enter to auto-detect): ").strip()
            if raw == "":
                settings["roof_mode"] = "auto"
                print("Auto-detect enabled.")
                break
            elif raw.isdigit():
                settings["roof_mode"] = "fixed"
                settings["roof_value"] = int(raw)
                print(f"Roof value set to {settings['roof_value']}.")
                break
            else:
                print("Please enter a whole number or press Enter.")

    print()
    print("-" * 56)
    print("Chromatic selection")
    print("-" * 56)
    print()
    print("After loading your data the script shows a table of")
    print("chromatics and how many wells saturated in each.")
    print()
    print("  auto   — the script picks the best chromatic")
    print("           (lowest one with no saturated wells)")
    print("  manual — you choose from the table each run")
    print()

    while True:
        mode = input("Chromatic selection [auto/manual]: ").strip().lower()
        if mode in ("auto", "manual"):
            settings["chromatic_mode"] = mode
            break
        print("Please enter 'auto' or 'manual'.")

    print()
    save_settings(settings)
    print("Settings saved. You're all set!")
    print("=" * 56)
    print()

    return settings


if __name__ == "__main__":
    args = sys.argv[1:]

    if "--setup" in args:
        run_setup()
        sys.exit(0)

    if len(args) != 1:
        print("Usage: python amyloconverter.py <folder_name>")
        print("  folder_name: name of a folder in the parent directory containing .csv files")
        print("  Example:     python amyloconverter.py my_experiment")
        print()
        print("  First time?  Just run the above — setup starts automatically.")
        print("  Redo setup:  python amyloconverter.py --setup")
        sys.exit(1)

    settings = load_settings()
    if settings is None:
        settings = run_setup()

    folder_name = args[0]
    base_path = os.path.abspath(os.path.join(os.getcwd(), ".."))
    target_folder = os.path.join(base_path, folder_name)

    if not os.path.isdir(target_folder):
        print(f"Folder not found: {target_folder}")
        sys.exit(1)

    os.chdir(target_folder)

    files = sorted(glob.glob("*.csv"))

    if not files:
        print("No CSV files found in this folder.")
        sys.exit(1)

    print("Files being processed:", files)

    reader = settings.get("plate_reader", "auto")

    try:
        data = merge_files(files, reader)
    except ValueError as e:
        print(f"Error reading files: {e}")
        print("Try running --setup and selecting a different plate reader option.")
        sys.exit(1)

    if not data:
        print("No chromatic data could be read from the files.")
        print("This usually means the files do not match the expected format.")
        print("Try running --setup and selecting 'Other' to use auto-detect mode.")
        sys.exit(1)

    if settings["roof_mode"] == "fixed":
        roof_value = settings["roof_value"]
        print(f"Roof value (from settings): {roof_value}")
    else:
        roof_value = detect_roof_value(data)
        print(f"Roof value (auto-detected): {roof_value}")

    all_chroms = sorted(data.keys(), key=_chrom_sort_key)

    if settings["chromatic_mode"] == "auto":
        selected = auto_select_chromatic(data, roof_value)
        print(f"\n{'Chromatic':<12} {'Saturated Wells':<18} {'Total Wells'}")
        print("-" * 44)
        for chrom in all_chroms:
            total = len(data[chrom]["wells"])
            saturated = count_saturated_wells(data[chrom], roof_value)
            marker = " <-- selected" if chrom == selected else ""
            print(f"{chrom:<12} {saturated:<18} {total}{marker}")
        print(f"\nAuto-selected chromatic: {selected}")
    else:
        selected = prompt_chromatic_selection(data, roof_value)
        print(f"\nSelected chromatic: {selected}")

    time = data[selected]["time"]
    wells = data[selected]["wells"]

    export_split_files(time, wells)
