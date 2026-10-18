"""Parsowanie danych z audiometru (blok CSV) i budowa modelu progów słyszenia."""

START_MARKER = "===CSV_START==="
END_MARKER = "===CSV_END==="
HEADER = "ear,frequency_hz,threshold_db"

VALID_EARS = ("L", "P")


def is_start_marker(line):
    """Znacznik startu jest rozpoznawany też wtedy, gdy w linii jest coś jeszcze
    (np. BOM albo resztka poprzedniego komunikatu)."""
    return START_MARKER in line


def is_end_marker(line):
    return END_MARKER in line


def extract_csv_block(text):
    """Wyszukuje blok między znacznikami CSV_START/CSV_END.

    Zwraca surowy tekst bloku (bez znaczników) albo None, jeśli znaczniki
    nie zostały znalezione w tekście.
    """
    lines = text.splitlines()
    start = end = None
    for i, line in enumerate(lines):
        if is_start_marker(line):
            start = i
        elif is_end_marker(line) and start is not None:
            end = i
            break
    if start is None or end is None:
        return None
    return "\n".join(lines[start + 1:end])


def parse_csv_block(block_text):
    """Parsuje wiersze 'ear,frequency_hz,threshold_db'.

    Pomija nagłówek i puste linie. Zwraca (rows, errors), gdzie rows to
    lista krotek (ear, freq, db) w oryginalnej kolejności, a errors to
    lista surowych, niepoprawnych linii.
    """
    rows = []
    errors = []
    for raw_line in block_text.splitlines():
        line = raw_line.strip()
        if not line or line == HEADER:
            continue
        parts = line.split(",")
        if len(parts) != 3:
            errors.append(raw_line)
            continue
        ear, freq_s, db_s = (p.strip() for p in parts)
        if ear not in VALID_EARS:
            errors.append(raw_line)
            continue
        try:
            freq = int(freq_s)
            db = int(db_s)
        except ValueError:
            errors.append(raw_line)
            continue
        rows.append((ear, freq, db))
    return rows, errors


def load_rows_from_text(text):
    """Próbuje znaleźć blok CSV między znacznikami; jeśli ich brak,
    traktuje cały tekst jako blok CSV (np. plik zawierający tylko dane)."""
    block = extract_csv_block(text)
    if block is None:
        block = text
    return parse_csv_block(block)


def build_thresholds(rows):
    """Grupuje wiersze wg ucha -> {frequency_hz: threshold_db}.

    1000 Hz występuje dwukrotnie w danych z urządzenia (pomiar i retest,
    w tej właśnie kolejności). Ponieważ przypisania do słownika nadpisują
    wcześniejsze wartości dla tego samego klucza, a wiersze są przetwarzane
    w oryginalnej kolejności z urządzenia, w wyniku zachowywana jest
    wartość z DRUGIEGO (retest) pomiaru przy 1000 Hz.
    """
    thresholds = {"L": {}, "P": {}}
    for ear, freq, db in rows:
        thresholds.setdefault(ear, {})[freq] = db
    return thresholds
