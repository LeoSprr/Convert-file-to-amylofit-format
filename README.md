# AmyloConverter

Converts raw plate reader CSV exports into clean time-series files ready for downstream analysis. It merges multiple run files, detects which wells have saturated (hit the plate reader ceiling), and exports the data split into tab-separated `.txt` files under 1 MB each.

---

## Requirements

- Python 3.6 or later
- No external packages — standard library only

---

## Download and launch

1. Go to the repository on GitHub
2. Click the green **Code** button → **Download ZIP**
3. Unzip it anywhere on your computer
4. Open **Terminal** (search for it in Spotlight with `Cmd+Space`)
5. Navigate into the unzipped folder by running:
 
```
cd ~/Downloads/Convert-file-to-amylofit-format-main
```
 
> If you saved the ZIP somewhere other than Downloads, replace `~/Downloads` with the actual path. You can also type `cd ` (with a trailing space) and then drag the unzipped folder into the Terminal window, then press **Enter**.
6. Run:
   ```
   python3 amyloconverter_gui.py
   ```

Or if you have git installed:
```
git clone https://github.com/LeoSprr/Convert-file-to-amylofit-format.git
cd Convert-file-to-amylofit-format
python3 amyloconverter_gui.py
```

---

## Getting started

### GUI (recommended)

Run from Terminal inside the project folder:
```
python3 amyloconverter_gui.py
```

On first launch the Settings window opens automatically. Configure your plate reader and preferences, then:

1. Click **Add Files** to select individual CSV files, or **Add Folder** to load all CSVs from a folder
2. Make sure files are listed in the correct merge order (see note below)
3. Click **Convert**
4. Output files are saved to the same folder as your input files — the log shows the exact path

### Command line

```
python amyloconverter.py <folder_name>
```

`folder_name` is the name of a folder **in the parent directory** of wherever `amyloconverter.py` lives, containing your raw `.csv` files. Setup runs automatically on first use.

---

## File order

When merging multiple files, AmyloConverter processes them in alphabetical order. To ensure correct results:

- Name your files `part1.csv`, `part2.csv` ... or `run1.csv`, `run2.csv` ...
- Or add them manually in the correct sequence using **Add Files**

---

## Settings

Settings are saved to `settings.json` next to the script on first run. You will not be asked again unless you click **Settings** in the GUI or run:

```
python amyloconverter.py --setup
```

See `settings.example.json` for a description of every available option.

`settings.json` is personal and excluded from version control — it will never be overwritten by a repo update.

---

## Supported plate readers

| Reader | Support |
|---|---|
| FLUOstar Omega | Native — full chromatic and well parsing |
| Other readers | Auto-detect — handles common CSV/TXT formats with standard well naming |

Using a different plate reader? Help expand AmyloConverter by sending a raw example file and the reader name to:

**leo.sparr@chem.lu.se**

---

## Output format

Each exported file is a tab-separated `.txt` with one row per timepoint:

```
Time    A01    A02    A03    ...
0.0     1240   980    1105   ...
0.5     1380   1020   1190   ...
...
```

- **Time** is in hours, starting from 0
- Files are named `<folder>_amylo_part1.txt`, `_part2.txt`, etc.
- Each file stays under 1 MB (number of wells per file is calculated automatically)
