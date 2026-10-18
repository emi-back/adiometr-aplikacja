"""Odczyt danych z portu szeregowego (Arduino) oraz z plików."""
import re
import threading

import serial
from serial.tools import list_ports

from .audiogram_data import (
    parse_csv_block,
    load_rows_from_text,
    build_thresholds,
    is_start_marker,
    is_end_marker,
)

BAUDRATE = 115200
READ_TIMEOUT = 0.1

# Urządzenie może kończyć linie jako \r\n, \n albo samo \r.
_LINE_SPLIT = re.compile(rb"[\r\n]+")


def list_serial_ports():
    return [p.device for p in list_ports.comports()]


class SerialReader(threading.Thread):
    """Wątek nasłuchujący na porcie szeregowym i wykrywający pełny blok CSV.

    Linie spoza znaczników ===CSV_START===/===CSV_END=== (logi, komunikaty
    debug urządzenia) są ignorowane przy budowie wyniku, zgodnie z formatem
    opisanym w plans/format_csv.md, ale trafiają do log_queue, żeby było
    widać, co faktycznie przyszło z portu.

    Kolejki:
    - result_queue: gotowy słownik progów {"L": {...}, "P": {...}},
    - status_queue: krotki (poziom, tekst); poziom "stopped" oznacza, że wątek
      zakończył się sam (błąd portu) i GUI powinno wrócić do stanu "Połącz",
    - log_queue (opcjonalna): krotki ("raw" | "parsed", tekst).
    """

    def __init__(self, port, result_queue, status_queue, log_queue=None, baudrate=BAUDRATE):
        super().__init__(daemon=True)
        self.port = port
        self.baudrate = baudrate
        self.result_queue = result_queue
        self.status_queue = status_queue
        self.log_queue = log_queue
        self._stop_event = threading.Event()
        self._serial = None
        self._collecting = False
        self._block_lines = []

    def stop(self):
        self._stop_event.set()

    def _log(self, kind, text):
        if self.log_queue is not None:
            self.log_queue.put((kind, text))

    def run(self):
        try:
            self._serial = serial.Serial(self.port, self.baudrate, timeout=READ_TIMEOUT)
        except serial.SerialException as exc:
            self.status_queue.put(
                ("stopped", f"Nie udało się otworzyć portu {self.port}: {exc}")
            )
            return

        self.status_queue.put(("info", f"Połączono z {self.port}. Oczekiwanie na dane..."))
        try:
            self._read_loop()
        except serial.SerialException as exc:
            self.status_queue.put(("stopped", f"Błąd portu szeregowego: {exc}"))
        except Exception as exc:  # wątek nie może umrzeć po cichu
            self.status_queue.put(("stopped", f"Nieoczekiwany błąd odczytu: {exc!r}"))
        finally:
            try:
                self._serial.close()
            except Exception:
                pass

    def _read_loop(self):
        buffer = b""
        while not self._stop_event.is_set():
            data = self._serial.read(max(1, self._serial.in_waiting))
            if not data:
                continue

            buffer += data
            *complete, buffer = _LINE_SPLIT.split(buffer)
            for raw in complete:
                self._handle_line(raw.decode("utf-8", errors="replace").lstrip("﻿").strip())

    def _handle_line(self, line):
        if not line:
            return
        self._log("raw", line)

        if is_start_marker(line):
            self._collecting = True
            self._block_lines = []
            self.status_queue.put(("info", "Odbieranie wyników badania..."))
            return

        if is_end_marker(line):
            if self._collecting:
                self._finish_block()
            self._collecting = False
            return

        if self._collecting:
            self._block_lines.append(line)
        # linie poza znacznikami (logi/debug urządzenia) są ignorowane

    def _finish_block(self):
        rows, errors = parse_csv_block("\n".join(self._block_lines))

        self._log("parsed", f"Sparsowano wierszy: {len(rows)}, błędnych: {len(errors)}")
        for ear, freq, db in rows:
            self._log("parsed", f"  {ear} {freq} Hz -> {db} dB")
        for bad in errors:
            self._log("parsed", f"  BŁĘDNY WIERSZ: {bad!r}")

        if not rows:
            self.status_queue.put(("warning", "Blok CSV nie zawierał poprawnych wierszy."))
            return

        thresholds = build_thresholds(rows)
        self.result_queue.put(thresholds)

        summary = f"Odebrano wynik: L {len(thresholds['L'])} pkt, P {len(thresholds['P'])} pkt"
        if errors:
            summary += f" (pominięto {len(errors)} błędnych wierszy)"
        self.status_queue.put(("success", summary + "."))


def load_from_file(path):
    """Wczytuje dane z pliku tekstowego (zapisany log z portu albo sam blok CSV).

    Zwraca (thresholds, errors).
    """
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    rows, errors = load_rows_from_text(text)
    thresholds = build_thresholds(rows)
    return thresholds, errors
