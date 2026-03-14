#!/usr/bin/env python3
"""Terminal CSV reader - interactive table viewer with vim-like keybindings."""

import csv
import sys
import os
import re
import argparse
import curses


def detect_delimiter(filepath, encoding='utf-8'):
    """Auto-detect CSV delimiter using csv.Sniffer."""
    try:
        with open(filepath, encoding=encoding) as f:
            sample = f.read(8192)
        return csv.Sniffer().sniff(sample).delimiter
    except (csv.Error, UnicodeDecodeError):
        return ','


def read_csv(filepath, delimiter=',', encoding='utf-8'):
    """Read CSV file and return header + rows."""
    with open(filepath, newline='', encoding=encoding) as f:
        reader = csv.reader(f, delimiter=delimiter)
        rows = list(reader)
    if not rows:
        return [], []
    return rows[0], rows[1:]


def calc_col_widths(header, rows, max_width=50):
    """Calculate column widths based on content."""
    num_cols = len(header)
    widths = [len(str(h)) for h in header]
    for row in rows:
        for i, cell in enumerate(row):
            if i < num_cols:
                widths[i] = max(widths[i], len(str(cell)))
    return [min(w, max_width) for w in widths]


def truncate(text, width):
    """Truncate text with ellipsis if too long."""
    if len(text) <= width:
        return text
    return text[:width - 1] + '~'


def format_row(cells, widths, num_cols):
    """Format a single row into a table line string."""
    line = '|'
    for i in range(num_cols):
        cell = str(cells[i]) if i < len(cells) else ''
        line += ' ' + truncate(cell, widths[i]).ljust(widths[i]) + ' |'
    return line


def make_separator(widths, char='-'):
    """Build a separator line."""
    sep = '+'
    for w in widths:
        sep += char * (w + 2) + '+'
    return sep


def read_search_input(stdscr, prompt_char, color_pair):
    """Read a line of input from user at status bar. Returns string or None."""
    h, w = stdscr.getmaxyx()
    curses.curs_set(1)
    stdscr.move(h - 1, 0)
    stdscr.clrtoeol()
    stdscr.addnstr(h - 1, 0, prompt_char, w - 1, color_pair)
    stdscr.refresh()

    buf = []
    while True:
        ch = stdscr.getch()
        if ch in (10, 13, curses.KEY_ENTER):
            break
        elif ch == 27:
            buf = None
            break
        elif ch in (curses.KEY_BACKSPACE, 127, 8):
            if buf:
                buf.pop()
        else:
            if 32 <= ch <= 126:
                buf.append(chr(ch))
        prompt = prompt_char + ''.join(buf) if buf is not None else ''
        stdscr.move(h - 1, 0)
        stdscr.clrtoeol()
        try:
            stdscr.addnstr(h - 1, 0, prompt, w - 1, color_pair)
        except curses.error:
            pass
        stdscr.refresh()

    curses.curs_set(0)
    if buf is not None:
        return ''.join(buf)
    return None


def show_cell_popup(stdscr, title, content):
    """Show a popup window with full cell content."""
    h, w = stdscr.getmaxyx()
    max_pw = min(w - 4, 78)
    # Word wrap content
    wrapped = []
    for raw_line in content.split('\n'):
        if not raw_line:
            wrapped.append('')
            continue
        while len(raw_line) > max_pw - 4:
            wrapped.append(raw_line[:max_pw - 4])
            raw_line = raw_line[max_pw - 4:]
        wrapped.append(raw_line)

    popup_h = min(h - 2, len(wrapped) + 4)
    popup_w = max_pw
    sy = max(0, (h - popup_h) // 2)
    sx = max(0, (w - popup_w) // 2)

    win = curses.newwin(popup_h, popup_w, sy, sx)
    win.box()
    ttl = f' {title} '[:popup_w - 4]
    try:
        win.addnstr(0, 2, ttl, popup_w - 4, curses.A_BOLD)
    except curses.error:
        pass
    for i, line in enumerate(wrapped):
        y = i + 2
        if y >= popup_h - 1:
            break
        try:
            win.addnstr(y, 2, line[:popup_w - 4], popup_w - 4)
        except curses.error:
            pass
    footer = ' Press any key '
    try:
        win.addnstr(popup_h - 1, max(2, popup_w - len(footer) - 2),
                     footer, popup_w - 4, curses.A_DIM)
    except curses.error:
        pass
    win.refresh()
    stdscr.getch()


def interactive_view(stdscr, header, rows, widths, filepath,
                     delimiter=',', encoding='utf-8', max_width=50):
    """Curses-based interactive CSV viewer."""
    curses.curs_set(0)
    curses.use_default_colors()
    curses.mousemask(curses.ALL_MOUSE_EVENTS)
    stdscr.idlok(False)    # disable insert/delete line optimization (VTE artifact fix)
    BUTTON5 = getattr(curses, 'BUTTON5_PRESSED', 2097152)

    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)    # header
    curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_YELLOW)  # search match
    curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_BLUE)    # status bar
    curses.init_pair(4, curses.COLOR_BLACK, curses.COLOR_GREEN)   # current match
    curses.init_pair(5, curses.COLOR_WHITE, -1)                   # (unused)
    curses.init_pair(6, curses.COLOR_YELLOW, -1)                  # line number
    curses.init_pair(7, curses.COLOR_BLACK, curses.COLOR_MAGENTA) # cursor col

    num_cols = len(header)
    widths = list(widths)  # mutable copy
    original_rows = list(rows)
    display_rows = list(rows)
    num_rows = len(display_rows)

    row_offset = 0
    col_offset = 0
    cursor_row = 0
    cursor_col = 0

    search_term = ''
    search_exact = False
    search_matches = []
    current_match = -1
    match_set = set()

    filter_regex = ''
    sort_col = -1
    sort_reverse = False
    status_msg = ''

    def recompute():
        nonlocal display_rows, num_rows
        if filter_regex:
            try:
                pat = re.compile(filter_regex, re.IGNORECASE)
                display_rows = [r for r in original_rows
                                if any(pat.search(str(c)) for c in r)]
            except re.error:
                display_rows = list(original_rows)
        else:
            display_rows = list(original_rows)
        if 0 <= sort_col < num_cols:
            def skey(row):
                if sort_col >= len(row):
                    return (1, '', '')
                v = str(row[sort_col])
                try:
                    return (0, float(v), v.lower())
                except ValueError:
                    return (1, v.lower(), v.lower())
            display_rows.sort(key=skey, reverse=sort_reverse)
        num_rows = len(display_rows)

    def find_matches(term, exact=False):
        matches = []
        if not term:
            return matches
        t = term.lower()
        for ri, row in enumerate(display_rows):
            for ci, cell in enumerate(row):
                if exact:
                    if str(cell).lower() == t:
                        matches.append((ri, ci))
                else:
                    if t in str(cell).lower():
                        matches.append((ri, ci))
        return matches

    def rebuild_meta():
        nonlocal sep, header_line, table_width
        sep = make_separator(widths)
        header_line = format_row(header, widths, num_cols)
        table_width = len(sep)

    sep = make_separator(widths)
    header_line = format_row(header, widths, num_cols)
    table_width = len(sep)
    ln_width = max(len(str(len(original_rows))), 2)

    def draw():
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        data_area = max(1, h - 4)
        lnx = ln_width + 1
        tw = max(w - lnx, 1)

        def tline(y, text, attr=0):
            if 0 <= y < h:
                vis = text[col_offset:col_offset + tw]
                try:
                    stdscr.addnstr(y, lnx, vis, tw - 1, attr)
                except curses.error:
                    pass

        def draw_ln(y, num):
            s = str(num).rjust(ln_width) + ' '
            try:
                stdscr.addnstr(y, 0, s, min(len(s), w - 1), curses.color_pair(6))
            except curses.error:
                pass

        # Top separator
        tline(0, sep)

        # Header
        tline(1, header_line, curses.color_pair(1) | curses.A_BOLD)

        # Highlight cursor column in header
        if cursor_col < num_cols:
            cp = 1
            for ci in range(cursor_col):
                cp += widths[ci] + 3
            ct = truncate(str(header[cursor_col]), widths[cursor_col]).ljust(widths[cursor_col])
            cs = lnx + cp + 1 - col_offset
            if cs < w and cs + widths[cursor_col] > 0:
                ds = max(lnx, cs)
                to = ds - cs
                dt = ct[to:to + w - ds]
                if dt:
                    try:
                        stdscr.addnstr(1, ds, dt, w - ds - 1,
                                       curses.color_pair(7) | curses.A_BOLD)
                    except curses.error:
                        pass

        # Header separator
        tline(2, make_separator(widths, '='))

        # Data rows
        for i in range(data_area):
            ri = row_offset + i
            y = 3 + i
            if ri >= num_rows:
                break

            draw_ln(y, ri + 1)
            row = display_rows[ri]
            line = format_row(row, widths, num_cols)

            is_cursor = (ri == cursor_row)
            row_attr = curses.A_REVERSE if is_cursor else 0
            vis = line[col_offset:col_offset + tw]
            if y < h - 1 and tw > 0:
                try:
                    stdscr.addnstr(y, lnx, vis, tw - 1, row_attr)
                except curses.error:
                    pass

            # Search highlights
            if search_term:
                cp = 1
                for ci in range(num_cols):
                    cell = str(row[ci]) if ci < len(row) else ''
                    ct = truncate(cell, widths[ci]).ljust(widths[ci])
                    cs = lnx + cp + 1 - col_offset

                    is_current = (current_match >= 0 and
                                  current_match < len(search_matches) and
                                  search_matches[current_match] == (ri, ci))
                    is_match = (ri, ci) in match_set

                    if (is_current or is_match) and cs < w and cs + widths[ci] > 0:
                        attr = (curses.color_pair(4) | curses.A_BOLD) if is_current else curses.color_pair(2)
                        ds = max(lnx, cs)
                        to = ds - cs
                        dt = ct[to:to + w - ds]
                        if dt and y < h - 1:
                            try:
                                stdscr.addnstr(y, ds, dt, w - ds - 1, attr)
                            except curses.error:
                                pass
                    cp += widths[ci] + 3

        # Bottom separator
        by = min(3 + data_area, h - 2)
        if by < h - 1:
            tline(by, sep)

        # Status bar
        if status_msg:
            bar = status_msg
        else:
            fname = os.path.basename(filepath)
            pos = f'Row {cursor_row + 1}/{num_rows}'
            cname = header[cursor_col] if cursor_col < len(header) else ''
            col_info = f'  Col {cursor_col + 1}/{num_cols}:{cname}'
            parts = []
            if search_term:
                m = 'exact' if search_exact else 'partial'
                parts.append(f'{m}:{len(search_matches)}')
            if filter_regex:
                parts.append(f'filter:{filter_regex}')
            if sort_col >= 0:
                d = '↓' if sort_reverse else '↑'
                sn = header[sort_col] if sort_col < len(header) else ''
                parts.append(f'sort:{sn}{d}')
            extra = '  [' + ' '.join(parts) + ']' if parts else ''
            bar = f' {fname}  {pos}{col_info}{extra}'
            bar += ' ' * max(0, w - len(bar) - 1)
        try:
            stdscr.addnstr(h - 1, 0, bar[:w], w - 1,
                           curses.color_pair(3) | curses.A_BOLD)
        except curses.error:
            pass
        stdscr.refresh()

    def clamp_cursor():
        nonlocal cursor_row, row_offset, cursor_col
        if num_rows == 0:
            cursor_row = 0
            row_offset = 0
            return
        cursor_row = max(0, min(cursor_row, num_rows - 1))
        cursor_col = max(0, min(cursor_col, num_cols - 1))

    while True:
        draw()
        key = stdscr.getch()
        h, w = stdscr.getmaxyx()
        data_area = max(1, h - 4)
        status_msg = ''
        bar_pair = curses.color_pair(3)

        # Quit
        if key in (ord('q'), ord('Q')):
            break

        # Mouse: scroll moves viewport only, click moves cursor
        elif key == curses.KEY_MOUSE:
            try:
                _, mx, my, mz, bstate = curses.getmouse()
                if bstate & curses.BUTTON4_PRESSED:
                    row_offset = max(0, row_offset - 3)
                elif bstate & BUTTON5:
                    row_offset = min(max(0, num_rows - data_area), row_offset + 3)
                elif bstate & (curses.BUTTON1_PRESSED | curses.BUTTON1_CLICKED
                               | curses.BUTTON1_RELEASED):
                    # Click on data area (y >= 3) moves cursor to that row
                    if 3 <= my < 3 + data_area:
                        target = row_offset + (my - 3)
                        if 0 <= target < num_rows:
                            cursor_row = target
            except curses.error:
                pass

        # Down: j, arrow down
        elif key in (ord('j'), curses.KEY_DOWN):
            if cursor_row < num_rows - 1:
                cursor_row += 1
                if cursor_row >= row_offset + data_area:
                    row_offset = cursor_row - data_area + 1

        # Up: k, arrow up
        elif key in (ord('k'), curses.KEY_UP):
            if cursor_row > 0:
                cursor_row -= 1
                if cursor_row < row_offset:
                    row_offset = cursor_row

        # Right: l, arrow right (horizontal scroll)
        elif key in (ord('l'), curses.KEY_RIGHT):
            if col_offset < table_width - w + 1:
                col_offset += 4

        # Left: h, arrow left
        elif key in (ord('h'), curses.KEY_LEFT):
            col_offset = max(0, col_offset - 4)

        # Tab: next column
        elif key == 9:
            cursor_col = (cursor_col + 1) % num_cols

        # Shift+Tab: previous column
        elif key == curses.KEY_BTAB:
            cursor_col = (cursor_col - 1) % num_cols

        # Half page down: Ctrl+D
        elif key == 4:
            half = data_area // 2
            cursor_row = min(num_rows - 1, cursor_row + half)
            row_offset = min(num_rows - 1, row_offset + half)
            if cursor_row >= row_offset + data_area:
                row_offset = cursor_row - data_area + 1

        # Page down: Ctrl+F, Page Down, space
        elif key in (6, curses.KEY_NPAGE, ord(' ')):
            cursor_row = min(num_rows - 1, cursor_row + data_area)
            row_offset = min(num_rows - 1, row_offset + data_area)
            if cursor_row >= row_offset + data_area:
                row_offset = cursor_row - data_area + 1

        # Half page up: Ctrl+U
        elif key == 21:
            half = data_area // 2
            cursor_row = max(0, cursor_row - half)
            row_offset = max(0, row_offset - half)
            if cursor_row < row_offset:
                row_offset = cursor_row

        # Page up: Ctrl+B, Page Up
        elif key in (2, curses.KEY_PPAGE):
            cursor_row = max(0, cursor_row - data_area)
            row_offset = max(0, row_offset - data_area)
            if cursor_row < row_offset:
                row_offset = cursor_row

        # Top: g, Home
        elif key in (ord('g'), curses.KEY_HOME):
            cursor_row = 0
            row_offset = 0
            col_offset = 0

        # Bottom: G, End
        elif key in (ord('G'), curses.KEY_END):
            cursor_row = max(0, num_rows - 1)
            row_offset = max(0, num_rows - data_area)

        # Sort ascending: s
        elif key == ord('s'):
            if sort_col == cursor_col and not sort_reverse:
                sort_col = -1  # toggle off
            else:
                sort_col = cursor_col
                sort_reverse = False
            recompute()
            cursor_row = 0
            row_offset = 0
            search_matches = find_matches(search_term, search_exact) if search_term else []
            match_set = set(search_matches)
            current_match = 0 if search_matches else -1
            sn = header[cursor_col] if cursor_col < len(header) else ''
            status_msg = f' Sort: {sn} ↑' if sort_col >= 0 else ' Sort cleared'

        # Sort descending: S
        elif key == ord('S'):
            if sort_col == cursor_col and sort_reverse:
                sort_col = -1  # toggle off
            else:
                sort_col = cursor_col
                sort_reverse = True
            recompute()
            cursor_row = 0
            row_offset = 0
            search_matches = find_matches(search_term, search_exact) if search_term else []
            match_set = set(search_matches)
            current_match = 0 if search_matches else -1
            sn = header[cursor_col] if cursor_col < len(header) else ''
            status_msg = f' Sort: {sn} ↓' if sort_col >= 0 else ' Sort cleared'

        # Column resize: < >
        elif key == ord('<'):
            if widths[cursor_col] > 4:
                widths[cursor_col] -= 2
                rebuild_meta()
                status_msg = f' Col width: {widths[cursor_col]}'

        elif key == ord('>'):
            widths[cursor_col] += 2
            rebuild_meta()
            status_msg = f' Col width: {widths[cursor_col]}'

        # Cell detail: Enter
        elif key in (10, 13, curses.KEY_ENTER):
            if num_rows > 0 and cursor_row < num_rows:
                row = display_rows[cursor_row]
                cell = str(row[cursor_col]) if cursor_col < len(row) else ''
                cname = header[cursor_col] if cursor_col < len(header) else ''
                show_cell_popup(stdscr, cname, cell)

        # Row filter: &
        elif key == ord('&'):
            term = read_search_input(stdscr, '&', bar_pair)
            if term is not None:
                filter_regex = term
                recompute()
                cursor_row = 0
                row_offset = 0
                clamp_cursor()
                search_matches = find_matches(search_term, search_exact) if search_term else []
                match_set = set(search_matches)
                current_match = 0 if search_matches else -1
                if filter_regex:
                    status_msg = f' Filter: {num_rows}/{len(original_rows)} rows'
                else:
                    status_msg = ' Filter cleared'

        # Search: /
        elif key == ord('/'):
            term = read_search_input(stdscr, '/', bar_pair)
            if term is not None:
                search_term = term
                search_exact = False
                search_matches = find_matches(search_term, exact=False)
                match_set = set(search_matches)
                if search_matches:
                    current_match = 0
                    cursor_row = search_matches[0][0]
                    row_offset = cursor_row
                    status_msg = f' Match 1/{len(search_matches)}'
                else:
                    current_match = -1
                    if search_term:
                        status_msg = f' Pattern not found: {search_term}'

        # Exact search: =
        elif key == ord('='):
            term = read_search_input(stdscr, '=', bar_pair)
            if term is not None:
                search_term = term
                search_exact = True
                search_matches = find_matches(search_term, exact=True)
                match_set = set(search_matches)
                if search_matches:
                    current_match = 0
                    cursor_row = search_matches[0][0]
                    row_offset = cursor_row
                    status_msg = f' Exact 1/{len(search_matches)}'
                else:
                    current_match = -1
                    if search_term:
                        status_msg = f' Exact not found: {search_term}'

        # Next match: n
        elif key == ord('n'):
            if search_matches:
                current_match = (current_match + 1) % len(search_matches)
                cursor_row = search_matches[current_match][0]
                row_offset = cursor_row
                status_msg = f' Match {current_match + 1}/{len(search_matches)}'

        # Previous match: N
        elif key == ord('N'):
            if search_matches:
                current_match = (current_match - 1) % len(search_matches)
                cursor_row = search_matches[current_match][0]
                row_offset = cursor_row
                status_msg = f' Match {current_match + 1}/{len(search_matches)}'

        # Clear search: Escape
        elif key == 27:
            search_term = ''
            search_matches = []
            match_set = set()
            current_match = -1

        # Reload file: R
        elif key == ord('R'):
            try:
                new_header, new_rows = read_csv(filepath, delimiter, encoding)
                if new_header:
                    header = new_header
                    rows = new_rows
                    num_cols = len(header)
                    original_rows = list(rows)
                    widths = calc_col_widths(header, rows, max_width)
                    rebuild_meta()
                    ln_width = max(len(str(len(original_rows))), 2)
                    sort_col = -1
                    sort_reverse = False
                    filter_regex = ''
                    recompute()
                    cursor_row = 0
                    row_offset = 0
                    col_offset = 0
                    cursor_col = 0
                    search_term = ''
                    search_matches = []
                    match_set = set()
                    current_match = -1
                    status_msg = f' Reloaded ({num_rows} rows)'
                else:
                    status_msg = ' Reload failed: empty file'
            except Exception as e:
                status_msg = f' Reload error: {e}'

        # Reset sort + filter: r
        elif key == ord('r'):
            sort_col = -1
            sort_reverse = False
            filter_regex = ''
            recompute()
            cursor_row = 0
            row_offset = 0
            search_matches = find_matches(search_term, search_exact) if search_term else []
            match_set = set(search_matches)
            current_match = 0 if search_matches else -1
            status_msg = ' Reset sort & filter'

        # Help: ?
        elif key == ord('?'):
            help_lines = [
                'CSV Reader - Key Bindings',
                '',
                'Navigation',
                ' j/↓  k/↑      Row down / up',
                ' h/←  l/→      Scroll left / right',
                ' Tab / S-Tab    Next / prev column',
                ' Ctrl+D         Half page down',
                ' Ctrl+U         Half page up',
                ' Space/Ctrl+F   Page down',
                ' Ctrl+B/PgUp    Page up',
                ' g / Home       Top',
                ' G / End        Bottom',
                ' Mouse wheel    Scroll up / down',
                '',
                'Column Operations',
                ' s              Sort ascending (cursor col)',
                ' S              Sort descending (cursor col)',
                ' < / >          Resize column',
                ' Enter          Cell detail popup',
                '',
                'Search & Filter',
                ' /              Search (partial)',
                ' =              Search (exact)',
                ' n / N          Next / prev match',
                ' &              Filter rows (regex)',
                ' Esc            Clear search',
                ' r              Reset sort & filter',
                ' R              Reload file',
                '',
                ' ?  Help    q  Quit',
            ]
            popup_h = min(h - 2, len(help_lines) + 2)
            popup_w = min(w - 4, 50)
            sy = max(0, (h - popup_h) // 2)
            sx = max(0, (w - popup_w) // 2)
            win = curses.newwin(popup_h, popup_w, sy, sx)
            win.box()
            for i, line in enumerate(help_lines):
                y = i + 1
                if y >= popup_h - 1:
                    break
                try:
                    win.addnstr(y, 2, line[:popup_w - 4], popup_w - 4)
                except curses.error:
                    pass
            win.refresh()
            stdscr.getch()

        # Terminal resize
        elif key == curses.KEY_RESIZE:
            clamp_cursor()


def build_table_lines(header, rows, widths):
    """Build complete table as list of strings with line numbers."""
    num_cols = len(header)
    num_rows = len(rows)
    ln_width = len(str(num_rows))
    ln_pad = ' ' * (ln_width + 1)
    sep = make_separator(widths)
    lines = [ln_pad + sep,
             ln_pad + format_row(header, widths, num_cols),
             ln_pad + make_separator(widths, '=')]
    for i, row in enumerate(rows):
        ln = str(i + 1).rjust(ln_width) + ' '
        lines.append(ln + format_row(row, widths, num_cols))
    lines.append(ln_pad + sep)
    lines.append(f'  {num_rows} rows x {num_cols} columns')
    return lines


def static_view(header, rows, widths):
    """Non-interactive table output to stdout."""
    for line in build_table_lines(header, rows, widths):
        print(line)


def export_table(header, rows, widths, outpath):
    """Write table to .table file."""
    lines = build_table_lines(header, rows, widths)
    with open(outpath, 'w') as f:
        f.write('\n'.join(lines) + '\n')


def parse_table_line(line):
    """Parse a '| cell | cell |' line into stripped cell values."""
    if not line.startswith('|'):
        return None
    parts = line.split('|')
    return [p.strip() for p in parts[1:-1]]


def read_table(filepath, encoding='utf-8'):
    """Read .table file and return header + rows."""
    with open(filepath, encoding=encoding) as f:
        lines = f.read().splitlines()

    header = []
    rows = []
    for line in lines:
        if line.startswith('+') or line.strip().endswith('columns'):
            continue
        cells = parse_table_line(line)
        if cells is None:
            continue
        if not header:
            header = cells
        else:
            rows.append(cells)
    return header, rows


def table2csv(filepath, outpath, encoding='utf-8'):
    """Convert .table file to .csv file."""
    header, rows = read_table(filepath, encoding)
    if not header:
        print('Empty or invalid .table file.', file=sys.stderr)
        sys.exit(1)
    with open(outpath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for row in rows:
            writer.writerow(row)
    return len(rows), len(header)


def main():
    parser = argparse.ArgumentParser(description='Interactive CSV table viewer')
    parser.add_argument('file', help='CSV file path')
    parser.add_argument('-d', '--delimiter', default='', help='Delimiter (default: auto-detect)')
    parser.add_argument('-e', '--encoding', default='utf-8', help='File encoding (default: utf-8)')
    parser.add_argument('-w', '--max-width', type=int, default=50, help='Max column width (default: 50)')
    parser.add_argument('-n', '--head', type=int, default=0, help='Show only first N rows')
    parser.add_argument('-s', '--static', action='store_true', help='Static output (no interactive mode)')
    parser.add_argument('-o', '--output', default='', help='Export table to .table file')
    args = parser.parse_args()

    if not os.path.isfile(args.file):
        print(f'Error: file not found: {args.file}', file=sys.stderr)
        sys.exit(1)

    # .table → .csv reverse conversion
    if args.file.endswith('.table'):
        outpath = args.output if args.output else args.file.rsplit('.table', 1)[0] + '.csv'
        num_rows, num_cols = table2csv(args.file, outpath, args.encoding)
        print(f'Converted to {outpath} ({num_rows} rows x {num_cols} columns)')
        return

    # Auto-detect delimiter if not specified
    delimiter = args.delimiter if args.delimiter else detect_delimiter(args.file, args.encoding)

    header, rows = read_csv(args.file, delimiter, args.encoding)
    if not header:
        print('Empty CSV file.', file=sys.stderr)
        sys.exit(1)

    if args.head > 0:
        rows = rows[:args.head]

    widths = calc_col_widths(header, rows, args.max_width)

    if args.output:
        outpath = args.output
        if not outpath.endswith('.table'):
            outpath += '.table'
        export_table(header, rows, widths, outpath)
        print(f'Exported to {outpath}')
    elif args.static or not sys.stdout.isatty():
        static_view(header, rows, widths)
    else:
        curses.wrapper(interactive_view, header, rows, widths, args.file,
                       delimiter, args.encoding, args.max_width)


if __name__ == '__main__':
    main()
