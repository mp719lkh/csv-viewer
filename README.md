# csv-viewer

A fast, interactive CSV viewer for the terminal with vim-like keybindings. Zero dependencies — just Python 3 standard library.

Both **terminal (curses)** and **GUI (tkinter)** versions included.

## Why?

Sometimes you just need to look at a CSV on a remote server. You don't want to `pip install` a heavy library, you don't have admin access, and `cat data.csv` is unreadable. csv-viewer is a single Python file that works anywhere Python 3.6+ is installed — no setup, no dependencies, no nonsense.

> See also: **[md-viewer](https://github.com/keonho-lee/md-viewer)** — a zero-dependency Markdown viewer with the same philosophy.

## Features

- **Interactive terminal viewer** with curses — no external dependencies
- **Vim-like navigation** — `j`/`k`, `Ctrl+D`/`Ctrl+U`, `g`/`G`, and more
- **Search** — partial (`/`) and exact (`=`) match with highlighting
- **Sort & filter** — sort by any column, regex row filter
- **Column operations** — resize columns, cell detail popup
- **Auto-detect delimiter** — CSV, TSV, and custom delimiters
- **Format conversion** — CSV to `.table` (pretty-printed) and back
- **Mouse support** — scroll wheel and click
- **GUI version** — tkinter-based viewer with dark theme
- **Static output** — pipe-friendly mode for scripts and CI

## Installation

No installation required. Just download and run:

```bash
# One-liner install
curl -sSL https://raw.githubusercontent.com/keonho-lee/csv-viewer/main/csv_reader.py -o csv_reader && chmod +x csv_reader

# Or clone the full repo (includes GUI version + examples)
git clone https://github.com/keonho-lee/csv-viewer.git
```

**Requirements:** Python 3.6+ (standard library only — no pip install needed)

## Quick Start

```bash
# Interactive terminal viewer (default)
python3 csv_reader.py data.csv

# GUI viewer
python3 csv_reader_gui.py data.csv

# Static output (print table and exit)
python3 csv_reader.py data.csv -s

# View TSV file (auto-detected)
python3 csv_reader.py data.tsv

# First 20 rows only
python3 csv_reader.py data.csv -n 20
```

## Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `-d`, `--delimiter` | Column delimiter | auto-detect |
| `-e`, `--encoding` | File encoding | `utf-8` |
| `-w`, `--max-width` | Max column width (chars) | `50` |
| `-n`, `--head` | Show only first N rows | all |
| `-s`, `--static` | Non-interactive table output | off |
| `-o`, `--output` | Export to `.table` file | — |

## Key Bindings

Press `?` inside the viewer for the full help popup.

### Navigation

| Key | Action |
|-----|--------|
| `j` / `Down` | Move down |
| `k` / `Up` | Move up |
| `h` / `Left` | Scroll left |
| `l` / `Right` | Scroll right |
| `Tab` / `Shift+Tab` | Next / previous column |
| `Ctrl+D` | Half page down |
| `Ctrl+U` | Half page up |
| `Space` / `Ctrl+F` | Page down |
| `Ctrl+B` / `PgUp` | Page up |
| `g` / `Home` | Go to top |
| `G` / `End` | Go to bottom |

### Search & Filter

| Key | Action |
|-----|--------|
| `/` | Search (partial match) |
| `=` | Search (exact match) |
| `n` / `N` | Next / previous match |
| `&` | Filter rows (regex) |
| `Esc` | Clear search |
| `r` | Reset sort & filter |

### Column Operations

| Key | Action |
|-----|--------|
| `s` | Sort ascending (cursor column) |
| `S` | Sort descending (cursor column) |
| `<` / `>` | Resize column narrower / wider |
| `Enter` | Cell detail popup |

### Other

| Key | Action |
|-----|--------|
| `R` | Reload file |
| `?` | Help |
| `q` | Quit |

## Search Modes

**Partial match** (`/`): Matches any cell containing the search term.

```
/smith  →  matches "Smith", "Blacksmith", "smith@email.com"
```

**Exact match** (`=`): Matches only cells whose entire value equals the term.

```
=Smith  →  matches "Smith" only (not "Blacksmith")
```

Matched cells are highlighted in yellow; the current match is highlighted in green.

## Format Conversion

### CSV to Table

```bash
# Export to pretty-printed .table format
python3 csv_reader.py data.csv -o output

# Output:
#   +------------------+-------------+--------+
#   | name             | department  | salary |
#   +==================+=============+========+
# 1 | Alice Johnson    | Engineering | 95000  |
# 2 | Bob Smith        | Marketing   | 72000  |
#   +------------------+-------------+--------+
#   2 rows x 3 columns
```

### Table to CSV

```bash
# .table input automatically converts back to CSV
python3 csv_reader.py output.table
```

## GUI Mode

```bash
# Open file directly
python3 csv_reader_gui.py data.csv

# Open with options
python3 csv_reader_gui.py data.tsv -d '\t'

# Launch without file (use Ctrl+O to open)
python3 csv_reader_gui.py
```

GUI features:
- Dark theme with alternating row colors
- Treeview-based table with column resize and scrollbars
- Real-time search with partial/exact mode toggle
- Vim-like keybindings (same as terminal version)

## Examples

```bash
# View with custom delimiter
python3 csv_reader.py data.csv -d ';'

# View file with different encoding
python3 csv_reader.py data.csv -e euc-kr

# Limit column width to 30 characters
python3 csv_reader.py data.csv -w 30

# Pipe-friendly output
python3 csv_reader.py data.csv -s | head -20

# Round-trip conversion
python3 csv_reader.py data.csv -o data        # csv → table
python3 csv_reader.py data.table              # table → csv
```

## License

[MIT](LICENSE)
