#!/usr/bin/env python3
"""GUI CSV reader - tkinter-based table viewer with search and keyboard navigation."""

import csv
import sys
import os
import argparse
import tkinter as tk
from tkinter import ttk, filedialog


class CsvViewer(tk.Tk):
    """Tkinter-based CSV table viewer."""

    def __init__(self, filepath=None, delimiter=',', encoding='utf-8',
                 max_width=50, head=0):
        super().__init__()
        self.title('CSV Reader')
        self.geometry('1100x700')
        self.delimiter = delimiter
        self.encoding = encoding
        self.max_width = max_width
        self.head = head

        self._build_ui()
        self._bind_keys()

        if filepath:
            self.load_file(filepath)

    def _build_ui(self):
        # Top bar: file info + search
        top = tk.Frame(self, bg='#2b2b2b')
        top.pack(fill=tk.X)

        self.file_label = tk.Label(top, text='No file loaded', fg='#aaaaaa',
                                   bg='#2b2b2b', font=('monospace', 10),
                                   anchor='w', padx=8)
        self.file_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Search mode toggle
        self.search_mode = tk.StringVar(value='partial')
        mode_btn = tk.Button(top, textvariable=self.search_mode,
                             command=self._toggle_search_mode,
                             bg='#3c3c3c', fg='#aaaaaa',
                             font=('monospace', 9), width=7,
                             relief=tk.FLAT, activebackground='#4c4c4c')
        mode_btn.pack(side=tk.RIGHT, padx=(0, 8), pady=4)

        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', self._on_search_change)
        search_entry = tk.Entry(top, textvariable=self.search_var,
                                bg='#3c3c3c', fg='white',
                                insertbackground='white',
                                font=('monospace', 10), width=25)
        search_entry.pack(side=tk.RIGHT, padx=(0, 4), pady=4)
        self.search_entry = search_entry

        search_label = tk.Label(top, text='Search:', fg='#aaaaaa',
                                bg='#2b2b2b', font=('monospace', 10))
        search_label.pack(side=tk.RIGHT)

        self.match_label = tk.Label(top, text='', fg='#aaaaaa',
                                    bg='#2b2b2b', font=('monospace', 9))
        self.match_label.pack(side=tk.RIGHT, padx=(0, 8))

        # Table area using Treeview
        table_frame = tk.Frame(self)
        table_frame.pack(fill=tk.BOTH, expand=True)

        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Treeview',
                        background='#1e1e1e',
                        foreground='#d4d4d4',
                        fieldbackground='#1e1e1e',
                        font=('monospace', 11),
                        rowheight=24)
        style.configure('Treeview.Heading',
                        background='#264f78',
                        foreground='white',
                        font=('monospace', 11, 'bold'))
        style.map('Treeview',
                  background=[('selected', '#264f78')],
                  foreground=[('selected', 'white')])
        style.map('Treeview.Heading',
                  background=[('active', '#1e6fbf')])

        self.tree = ttk.Treeview(table_frame, show='headings',
                                 selectmode='browse')

        vsb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL,
                            command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL,
                            command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Status bar
        self.status = tk.Label(self, text='Press Ctrl+O to open a file',
                               bg='#007acc', fg='white',
                               font=('monospace', 10), anchor='w', padx=8)
        self.status.pack(fill=tk.X)

        # Data storage
        self.header = []
        self.rows = []
        self.all_iids = []
        self.search_matches = []  # list of (iid, col_idx)
        self.current_match = -1

    def _is_search_focused(self):
        return self.focus_get() == self.search_entry

    def _bind_keys(self):
        self.bind('<Control-o>', lambda e: self._open_file())
        self.bind('<Control-q>', lambda e: self.destroy())
        self.bind('<Escape>', lambda e: self._clear_search())
        self.bind('<F3>', lambda e: self._next_match())
        self.bind('<Shift-F3>', lambda e: self._prev_match())
        self.search_entry.bind('<Return>', lambda e: self._next_match())
        self.search_entry.bind('<Shift-Return>', lambda e: self._prev_match())

        # Vim-like navigation
        self.bind('j', lambda e: self._move_down() if not self._is_search_focused() else None)
        self.bind('k', lambda e: self._move_up() if not self._is_search_focused() else None)
        self.bind('<Down>', lambda e: self._move_down())
        self.bind('<Up>', lambda e: self._move_up())
        self.bind('<Control-d>', lambda e: self._half_page_down())
        self.bind('<space>', lambda e: self._page_down() if not self._is_search_focused() else None)
        self.bind('<Control-f>', lambda e: self._page_down())
        self.bind('<Next>', lambda e: self._page_down())
        self.bind('<Prior>', lambda e: self._page_up())
        self.bind('<Control-u>', lambda e: self._page_up())
        self.bind('g', lambda e: self._goto_top() if not self._is_search_focused() else None)
        self.bind('<Home>', lambda e: self._goto_top())
        self.bind('G', lambda e: self._goto_bottom() if not self._is_search_focused() else None)
        self.bind('<End>', lambda e: self._goto_bottom())
        self.bind('n', lambda e: self._next_match() if not self._is_search_focused() else None)
        self.bind('N', lambda e: self._prev_match() if not self._is_search_focused() else None)
        self.bind('/', lambda e: self._focus_search() if not self._is_search_focused() else None)
        self.bind('=', lambda e: self._toggle_and_focus_exact() if not self._is_search_focused() else None)
        self.bind('q', lambda e: self.destroy() if not self._is_search_focused() else None)

    def _move_down(self):
        sel = self.tree.selection()
        if sel:
            idx = self.all_iids.index(sel[0])
            if idx < len(self.all_iids) - 1:
                nxt = self.all_iids[idx + 1]
                self.tree.selection_set(nxt)
                self.tree.see(nxt)
                self._update_status_row(idx + 1)
        elif self.all_iids:
            self.tree.selection_set(self.all_iids[0])
            self.tree.see(self.all_iids[0])
            self._update_status_row(0)
        return 'break'

    def _move_up(self):
        sel = self.tree.selection()
        if sel:
            idx = self.all_iids.index(sel[0])
            if idx > 0:
                prev = self.all_iids[idx - 1]
                self.tree.selection_set(prev)
                self.tree.see(prev)
                self._update_status_row(idx - 1)
        return 'break'

    def _half_page_down(self):
        sel = self.tree.selection()
        half = max(1, self._visible_rows() // 2)
        if sel:
            idx = min(len(self.all_iids) - 1,
                      self.all_iids.index(sel[0]) + half)
        else:
            idx = min(len(self.all_iids) - 1, half)
        if self.all_iids:
            self.tree.selection_set(self.all_iids[idx])
            self.tree.see(self.all_iids[idx])
            self._update_status_row(idx)
        return 'break'

    def _page_down(self):
        sel = self.tree.selection()
        page = max(1, self._visible_rows())
        if sel:
            idx = min(len(self.all_iids) - 1,
                      self.all_iids.index(sel[0]) + page)
        else:
            idx = min(len(self.all_iids) - 1, page)
        if self.all_iids:
            self.tree.selection_set(self.all_iids[idx])
            self.tree.see(self.all_iids[idx])
            self._update_status_row(idx)
        return 'break'

    def _page_up(self):
        sel = self.tree.selection()
        page = max(1, self._visible_rows())
        if sel:
            idx = max(0, self.all_iids.index(sel[0]) - page)
        else:
            idx = 0
        if self.all_iids:
            self.tree.selection_set(self.all_iids[idx])
            self.tree.see(self.all_iids[idx])
            self._update_status_row(idx)
        return 'break'

    def _goto_top(self):
        if self.all_iids:
            self.tree.selection_set(self.all_iids[0])
            self.tree.see(self.all_iids[0])
            self._update_status_row(0)
        return 'break'

    def _goto_bottom(self):
        if self.all_iids:
            self.tree.selection_set(self.all_iids[-1])
            self.tree.see(self.all_iids[-1])
            self._update_status_row(len(self.all_iids) - 1)
        return 'break'

    def _visible_rows(self):
        try:
            h = self.tree.winfo_height()
            return max(1, h // 24)
        except Exception:
            return 20

    def _update_status_row(self, idx):
        fname = self.file_label.cget('text')
        total = len(self.all_iids)
        self.status.config(text=f' {fname}  Row {idx + 1}/{total}'
                           f'  ({len(self.header)} columns)')

    def _open_file(self):
        path = filedialog.askopenfilename(
            filetypes=[('CSV', '*.csv'), ('TSV', '*.tsv'),
                       ('Table', '*.table'), ('All', '*.*')])
        if path:
            self.load_file(path)

    def _focus_search(self):
        self.search_entry.focus_set()
        self.search_entry.select_range(0, tk.END)

    def _toggle_search_mode(self):
        if self.search_mode.get() == 'partial':
            self.search_mode.set('exact')
        else:
            self.search_mode.set('partial')
        self._on_search_change()

    def _toggle_and_focus_exact(self):
        self.search_mode.set('exact')
        self._focus_search()

    def load_file(self, filepath):
        if filepath.endswith('.table'):
            header, rows = self._read_table(filepath)
        else:
            header, rows = self._read_csv(filepath)

        if not header:
            self.status.config(text=' Error: empty file')
            return

        if self.head > 0:
            rows = rows[:self.head]

        self.header = header
        self.rows = rows
        self.title(f'CSV Reader - {os.path.basename(filepath)}')
        self.file_label.config(text=os.path.basename(filepath))
        self._populate_table()
        self.status.config(
            text=f' {filepath}  ({len(rows)} rows x {len(header)} columns)')

    def _read_csv(self, filepath):
        with open(filepath, newline='', encoding=self.encoding) as f:
            reader = csv.reader(f, delimiter=self.delimiter)
            rows = list(reader)
        if not rows:
            return [], []
        return rows[0], rows[1:]

    def _read_table(self, filepath):
        with open(filepath, encoding=self.encoding) as f:
            lines = f.read().splitlines()
        header = []
        rows = []
        for line in lines:
            if line.startswith('+') or line.strip().endswith('columns'):
                continue
            if not line.startswith('|'):
                continue
            cells = [p.strip() for p in line.split('|')[1:-1]]
            if not header:
                header = cells
            else:
                rows.append(cells)
        return header, rows

    def _populate_table(self):
        # Clear existing
        self.tree.delete(*self.tree.get_children())
        self.tree['columns'] = []

        num_cols = len(self.header)
        col_ids = [f'c{i}' for i in range(num_cols)]
        self.tree['columns'] = col_ids

        # Calculate column widths
        widths = [len(str(h)) for h in self.header]
        for row in self.rows:
            for i, cell in enumerate(row):
                if i < num_cols:
                    widths[i] = max(widths[i], len(str(cell)))
        widths = [min(w, self.max_width) for w in widths]

        for i, col_id in enumerate(col_ids):
            heading = self.header[i] if i < len(self.header) else ''
            px_width = max(80, (widths[i] + 2) * 9)
            self.tree.heading(col_id, text=heading, anchor='w')
            self.tree.column(col_id, width=px_width, minwidth=50,
                             anchor='w', stretch=False)

        # Insert rows
        self.all_iids = []
        for ri, row in enumerate(self.rows):
            values = []
            for i in range(num_cols):
                cell = str(row[i]) if i < len(row) else ''
                values.append(cell)
            iid = self.tree.insert('', tk.END, values=values,
                                   tags=('even' if ri % 2 == 0 else 'odd',))
            self.all_iids.append(iid)

        # Alternating row colors
        self.tree.tag_configure('even', background='#1e1e1e')
        self.tree.tag_configure('odd', background='#252526')
        self.tree.tag_configure('match', background='#614d00')
        self.tree.tag_configure('current_match', background='#515c00')

        # Select first row
        if self.all_iids:
            self.tree.selection_set(self.all_iids[0])
            self.tree.see(self.all_iids[0])

    def _on_search_change(self, *args):
        self._do_search()

    def _do_search(self):
        term = self.search_var.get()
        exact = self.search_mode.get() == 'exact'

        # Reset tags
        for iid in self.all_iids:
            ri = self.all_iids.index(iid)
            self.tree.item(iid, tags=('even' if ri % 2 == 0 else 'odd',))

        self.search_matches = []
        self.current_match = -1

        if not term:
            self.match_label.config(text='')
            return

        t = term.lower()
        for ri, row in enumerate(self.rows):
            for ci, cell in enumerate(row):
                cell_str = str(cell).lower()
                if exact:
                    if cell_str == t:
                        self.search_matches.append((self.all_iids[ri], ci))
                else:
                    if t in cell_str:
                        self.search_matches.append((self.all_iids[ri], ci))

        # Highlight matching rows
        match_iids = set(m[0] for m in self.search_matches)
        for iid in match_iids:
            self.tree.item(iid, tags=('match',))

        count = len(self.search_matches)
        if count > 0:
            self.current_match = 0
            self._show_current_match()
        else:
            mode_str = 'Exact' if exact else 'Pattern'
            self.match_label.config(text=f'{mode_str} not found')

    def _show_current_match(self):
        if not self.search_matches or self.current_match < 0:
            return

        # Reset previous current_match highlight
        match_iids = set(m[0] for m in self.search_matches)
        for iid in match_iids:
            self.tree.item(iid, tags=('match',))

        iid, col_idx = self.search_matches[self.current_match]
        self.tree.item(iid, tags=('current_match',))
        self.tree.selection_set(iid)
        self.tree.see(iid)

        total = len(self.search_matches)
        mode_str = 'exact' if self.search_mode.get() == 'exact' else 'partial'
        self.match_label.config(
            text=f'{self.current_match + 1}/{total} ({mode_str})')

    def _next_match(self):
        if self.search_matches:
            self.current_match = ((self.current_match + 1)
                                  % len(self.search_matches))
            self._show_current_match()

    def _prev_match(self):
        if self.search_matches:
            self.current_match = ((self.current_match - 1)
                                  % len(self.search_matches))
            self._show_current_match()

    def _clear_search(self):
        self.search_var.set('')
        for iid in self.all_iids:
            ri = self.all_iids.index(iid)
            self.tree.item(iid, tags=('even' if ri % 2 == 0 else 'odd',))
        self.search_matches = []
        self.current_match = -1
        self.match_label.config(text='')
        self.tree.focus_set()


def main():
    parser = argparse.ArgumentParser(description='GUI CSV table viewer')
    parser.add_argument('file', nargs='?', help='CSV file path')
    parser.add_argument('-d', '--delimiter', default=',',
                        help='Delimiter (default: comma)')
    parser.add_argument('-e', '--encoding', default='utf-8',
                        help='File encoding (default: utf-8)')
    parser.add_argument('-w', '--max-width', type=int, default=50,
                        help='Max column width (default: 50)')
    parser.add_argument('-n', '--head', type=int, default=0,
                        help='Show only first N rows')
    args = parser.parse_args()

    if args.file and not os.path.isfile(args.file):
        print(f'Error: file not found: {args.file}', file=sys.stderr)
        sys.exit(1)

    app = CsvViewer(filepath=args.file, delimiter=args.delimiter,
                    encoding=args.encoding, max_width=args.max_width,
                    head=args.head)
    app.mainloop()


if __name__ == '__main__':
    main()
