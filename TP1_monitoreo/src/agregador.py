"""Agregador de resultados y escritor único del snapshot."""

import queue


def aggregator_loop(result_queue, snapshot, snapshot_lock, stop_event):
    while not stop_event.is_set():
        try:
            name, data, timestamp = result_queue.get(timeout=0.25)
        except queue.Empty:
            continue
        with snapshot_lock:
            if name == "sistema":
                summary = snapshot.get("resumen", {}).get("datos", {})
                processes = list(summary.values())
                data["top_cpu"] = [
                    {"pid": item["pid"], "cpu": item.get("cpu", 0),
                     "comando": item.get("comando", "")}
                    for item in sorted(
                        processes, key=lambda item: item.get("cpu", 0),
                        reverse=True)[:3]
                ]
                data["top_memoria"] = [
                    {"pid": item["pid"], "rss": item.get("rss", 0),
                     "comando": item.get("comando", "")}
                    for item in sorted(
                        processes, key=lambda item: item.get("rss", 0),
                        reverse=True)[:3]
                ]
            snapshot[name] = {"datos": data, "ts": timestamp}
