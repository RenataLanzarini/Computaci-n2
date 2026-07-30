"""Interfaz curses con lista superior y detalle inferior."""

import curses
import os
import time

VIEWS = ["resumen", "memoria", "fds", "threads", "senales", "scheduling",
         "sistema"]
ALIASES = {"r": 0, "m": 1, "f": 2, "t": 3, "s": 4, "p": 5, "g": 6}


def display_process(snapshot, lock, intervals, minimums, control, stop_event,
                    verbose, filters):
    terminal_fd = None
    try:
        # multiprocessing redirige stdin de los hijos a /dev/null. El display
        # necesita recuperar la terminal controladora para recibir teclado.
        terminal_fd = os.open("/dev/tty", os.O_RDWR)
        os.dup2(terminal_fd, 0)
        os.dup2(terminal_fd, 1)
        curses.wrapper(_run, snapshot, lock, intervals, minimums, control,
                       stop_event, verbose, filters)
    finally:
        if terminal_fd is not None and terminal_fd > 2:
            os.close(terminal_fd)


def _safe_add(screen, row, col, text, width=None):
    height, screen_width = screen.getmaxyx()
    if 0 <= row < height and col < screen_width:
        try:
            screen.addnstr(row, col, str(text),
                           max(0, (width or screen_width) - col))
        except curses.error:
            pass


def _run(screen, snapshot, lock, intervals, minimums, control, stop_event,
         verbose, filters):
    curses.curs_set(0)
    screen.nodelay(True)
    selected = 0
    view = 0
    sort_mode = 0
    pinned = None
    help_visible = False
    while not stop_event.is_set():
        with lock:
            local = dict(snapshot)
        summary = local.get("resumen", {}).get("datos", {})
        rows = list(summary.values())
        command_filter = str(filters.get("comando", ""))
        user_filter = str(filters.get("usuario", ""))
        if command_filter:
            rows = [x for x in rows if command_filter.lower()
                    in x.get("comando", "").lower()]
        if user_filter:
            rows = [x for x in rows if user_filter.lower()
                    in x.get("usuario", "").lower()]
        keys = [
            lambda x: -x.get("cpu", 0),
            lambda x: -x.get("rss", 0),
            lambda x: x.get("pid", 0),
        ]
        rows.sort(key=keys[sort_mode])
        if pinned is not None:
            for index, item in enumerate(rows):
                if item["pid"] == pinned:
                    selected = index
                    break
        selected = min(max(0, selected), max(0, len(rows) - 1))
        screen.erase()
        _safe_add(screen, 0, 0, "MONITOR /proc  "
                  f"Vista {view + 1}:{VIEWS[view]}  "
                  f"intervalo={intervals[view].value:.1f}s  "
                  f"orden={('CPU','RSS','PID')[sort_mode]}")
        _safe_add(screen, 1, 0,
                  " PID   USER       ST  CPU%    RSS KiB  THR  COMANDO")
        height, width = screen.getmaxyx()
        list_height = max(3, height // 2)
        start = max(0, selected - (list_height - 3))
        for row_number, item in enumerate(rows[start:start + list_height - 2],
                                          start=2):
            marker = ">" if start + row_number - 2 == selected else " "
            line = (f"{marker}{item['pid']:5} {item.get('usuario','?')[:10]:10} "
                    f"{item.get('estado','?'):2} {item.get('cpu',0):6.1f} "
                    f"{item.get('rss',0):9} {item.get('threads',0):4} "
                    f"{item.get('comando','')}")
            _safe_add(screen, row_number, 0, line, width)
        detail_row = list_height + 1
        _safe_add(screen, detail_row, 0, "DETALLE " + "-" * max(0, width - 8))
        selected_pid = str(rows[selected]["pid"]) if rows else ""
        section = local.get(VIEWS[view], {}).get("datos", {})
        detail = section if view == 6 else section.get(selected_pid, {})
        lines = _format_detail(detail, verbose.value)
        for offset, line in enumerate(lines[:max(0, height - detail_row - 2)]):
            _safe_add(screen, detail_row + 1 + offset, 0, line, width)
        if help_visible:
            _safe_add(screen, height - 1, 0,
                      "1-7/rmftspg vistas ↑↓ Enter pin / filtro u usuario "
                      "c orden +/- intervalo q salir h ayuda", width)
        screen.refresh()
        key = screen.getch()
        if key != -1:
            char = chr(key).lower() if 0 <= key < 256 else ""
            if char == "/":
                filters["comando"] = _prompt(screen, "Filtrar comando: ")
            elif char == "u":
                filters["usuario"] = _prompt(screen, "Filtrar usuario: ")
            else:
                view, selected, pinned, sort_mode, help_visible = _key(
                    key, view, selected, rows, pinned, sort_mode, help_visible,
                    intervals, minimums, control)
        time.sleep(0.05)


def _format_detail(value, verbose):
    if not isinstance(value, dict):
        return [str(value)]
    lines = []
    for key, item in value.items():
        if key == "fds" and isinstance(item, list):
            limit = 30 if verbose else 10
            lines.extend(f"fd {x['fd']}: {x['tipo']} -> {x['destino']}"
                         for x in item[:limit])
        elif key == "threads" and isinstance(item, list):
            lines.extend(f"TID {x['tid']} {x['estado']} CPU={x['cpu']:.1f}% "
                         f"CTX={x.get('voluntary', 0)}/"
                         f"{x.get('involuntary', 0)} {x['nombre']}"
                         for x in item[:20])
        else:
            lines.append(f"{key}: {item}")
    return lines or ["Sin datos (esperando próximo ciclo o sin permisos)"]


def _prompt(screen, label):
    curses.echo()
    screen.nodelay(False)
    height, _ = screen.getmaxyx()
    _safe_add(screen, height - 1, 0, label)
    value = screen.getstr(height - 1, len(label), 80).decode(errors="replace")
    screen.nodelay(True)
    curses.noecho()
    return value


def _key(key, view, selected, rows, pinned, sort_mode, help_visible,
         intervals, minimums, control):
    char = chr(key).lower() if 0 <= key < 256 else ""
    if char and char in "1234567":
        view = int(char) - 1
    elif char in ALIASES:
        view = ALIASES[char]
    elif key == curses.KEY_UP:
        selected = max(0, selected - 1)
    elif key == curses.KEY_DOWN:
        selected = min(max(0, len(rows) - 1), selected + 1)
    elif key in (10, 13) and rows:
        pid = rows[selected]["pid"]
        pinned = None if pinned == pid else pid
    elif char == "c":
        sort_mode = (sort_mode + 1) % 3
    elif char in "+-":
        with intervals[view].get_lock():
            step = 0.5
            intervals[view].value = max(
                minimums[view],
                intervals[view].value + (step if char == "+" else -step))
    elif char in ("h", "?"):
        help_visible = not help_visible
    elif char == "q":
        control.send({"action": "quit"})
    return view, selected, pinned, sort_mode, help_visible
