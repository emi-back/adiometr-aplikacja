"""Testy SerialReader na atrapie portu szeregowego (bez sprzętu)."""
import os
import queue
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import serial_reader  # noqa: E402

CSV_BLOCK = """===CSV_START===
ear,frequency_hz,threshold_db
L,1000,5
L,2000,5
L,3000,20
L,4000,10
L,8000,10
L,1000,5
L,250,5
L,500,5
P,1000,5
P,2000,5
P,3000,10
P,4000,45
P,8000,45
P,1000,35
P,250,53
P,500,35
===CSV_END===
"""

STREAM = (
    "=== START TESTU MANUALNEGO ===\n\n"
    "--- Ustawiono częstotliwość: 1000 Hz ---\n"
    "Manualnie: 1000 Hz -> prog 50 dB HL\n"
    "=== TEST MANUALNY ZAKONCZONY ===\n"
    "=== TEST ZAKOŃCZONY ===\n"
    + CSV_BLOCK
    + "Naciśnij OK, aby wrócić do wyboru trybu...\n"
)

EXPECTED = {
    "L": {1000: 5, 2000: 5, 3000: 20, 4000: 10, 8000: 10, 250: 5, 500: 5},
    "P": {1000: 35, 2000: 5, 3000: 10, 4000: 45, 8000: 45, 250: 53, 500: 35},
}


class FakeSerial:
    """Oddaje dane porcjami (chunks), a potem puste odczyty, jak port z timeoutem."""

    def __init__(self, chunks):
        self._chunks = list(chunks)
        self.closed = False

    @property
    def in_waiting(self):
        return len(self._chunks[0]) if self._chunks else 0

    def read(self, size=1):
        if self._chunks:
            return self._chunks.pop(0)
        time.sleep(0.01)
        return b""

    def close(self):
        self.closed = True

    def drained(self):
        return not self._chunks


def run_reader(chunks):
    """Uruchamia SerialReader na atrapie i zwraca (wyniki, statusy, log)."""
    fake = FakeSerial(chunks)
    result_q, status_q, log_q = queue.Queue(), queue.Queue(), queue.Queue()
    with mock.patch.object(serial_reader.serial, "Serial", return_value=fake):
        reader = serial_reader.SerialReader("COMX", result_q, status_q, log_q)
        reader.start()
        deadline = time.time() + 3
        while not fake.drained() and time.time() < deadline:
            time.sleep(0.01)
        time.sleep(0.1)
        reader.stop()
        reader.join(2)
    assert not reader.is_alive()
    assert fake.closed

    def drain(q):
        items = []
        while not q.empty():
            items.append(q.get())
        return items

    return drain(result_q), drain(status_q), drain(log_q)


def chunked(data, size):
    return [data[i:i + size] for i in range(0, len(data), size)]


class SerialReaderTest(unittest.TestCase):
    def check_full_stream(self, eol, chunk_size):
        data = STREAM.replace("\n", eol).encode("utf-8")
        results, statuses, log = run_reader(chunked(data, chunk_size))
        self.assertEqual(results, [EXPECTED])
        self.assertIn(("success", "Odebrano wynik: L 7 pkt, P 7 pkt."), statuses)
        self.assertIn(("raw", "===CSV_START==="), log)
        self.assertIn(("parsed", "  P 250 Hz -> 53 dB"), log)

    def test_crlf(self):
        self.check_full_stream("\r\n", 4096)

    def test_lf(self):
        self.check_full_stream("\n", 4096)

    def test_bare_cr(self):
        self.check_full_stream("\r", 4096)

    def test_split_across_reads_incl_polish_chars(self):
        # 7 bajtów: linie i wielobajtowe znaki (ń, ó, ż) są dzielone między odczyty
        self.check_full_stream("\r\n", 7)

    def test_marker_line_with_prefix_and_bom(self):
        data = ("﻿" + "debug: " + CSV_BLOCK.replace("===CSV_END===", "x ===CSV_END=== y")).encode("utf-8")
        results, _, _ = run_reader([data])
        self.assertEqual(results, [EXPECTED])

    def test_invalid_block_gives_warning_and_no_result(self):
        data = b"===CSV_START===\near,frequency_hz,threshold_db\nX,abc,def\n===CSV_END===\n"
        results, statuses, log = run_reader([data])
        self.assertEqual(results, [])
        self.assertEqual(statuses[-1][0], "warning")
        self.assertTrue(any("BŁĘDNY WIERSZ" in text for _, text in log))

    def test_end_marker_without_start_is_ignored(self):
        results, _, _ = run_reader([b"junk\n===CSV_END===\n"])
        self.assertEqual(results, [])

    def test_port_open_failure_reports_stopped(self):
        result_q, status_q = queue.Queue(), queue.Queue()
        exc = serial_reader.serial.SerialException("Access is denied")
        with mock.patch.object(serial_reader.serial, "Serial", side_effect=exc):
            reader = serial_reader.SerialReader("COMX", result_q, status_q)
            reader.start()
            reader.join(2)
        level, message = status_q.get_nowait()
        self.assertEqual(level, "stopped")
        self.assertIn("Access is denied", message)

    def test_unexpected_exception_reports_stopped_and_closes_port(self):
        fake = FakeSerial([])
        fake.read = mock.Mock(side_effect=ValueError("boom"))
        result_q, status_q = queue.Queue(), queue.Queue()
        with mock.patch.object(serial_reader.serial, "Serial", return_value=fake):
            reader = serial_reader.SerialReader("COMX", result_q, status_q)
            reader.start()
            reader.join(2)
        levels = []
        while not status_q.empty():
            levels.append(status_q.get()[0])
        self.assertEqual(levels[-1], "stopped")
        self.assertTrue(fake.closed)


if __name__ == "__main__":
    unittest.main()
