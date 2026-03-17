# AmyloConverter

Converts raw plate reader CSV exports into clean time-series files ready for downstream analysis. It merges multiple run files, detects which wells have saturated (hit the plate reader ceiling), and exports the data split into tab-separated `.txt` files under 1 MB each.

---

## Requirements

- Python 3.6 or later
- No external packages — standard library only

---

## Getting started

1. Download `amyloconverter.py` and place it in a folder of your choice
2. Open a terminal in that folder
3. Run the command below with your data folder name — setup starts automatically on first run:

```
python amyloconverter.py <folder_name>
```

Setup asks two questions and saves your answers to `settings.json` next to the script. You will not be asked again unless you run `--setup`.

---

## Usage

```
python amyloconverter.py <folder_name>
```

`folder_name` is the name of a folder **in the parent directory** of wherever `amyloconverter.py` lives, containing your raw `.csv` files.

**Example — if your folder structure looks like this:**
```
lab/
├── Amyloconert/
│   └── amyloconverter.py
└── my_experiment/
    ├── run1.csv
    └── run2.csv
```

Run from inside `Amyloconert/`:
```
python amyloconverter.py my_experiment
```

Output `.txt` files are written into the data folder.

---

## Settings

On first run, `settings.json` is created automatically next to the script. It stores your preferences so you are not asked every time.

To redo setup at any time:
```
python amyloconverter.py --setup
```

See `settings.example.json` in this repo for a full description of every available setting and its valid values.

`settings.json` is excluded from version control via `.gitignore` — your personal settings will never be overwritten by a repo update.

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
