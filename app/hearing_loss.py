"""Obliczanie wskaźnika PTA4 i klasyfikacja stopnia ubytku słuchu.

Klasyfikacja wg progu słyszenia w uchu lepiej słyszącym, zgodnie z tabelą
stopni ubytku słuchu (WHO).
"""

PTA4_FREQS = (500, 1000, 2000, 4000)


def calculate_pta4(thresholds_for_ear):
    """Średnia arytmetyczna progów dla 500, 1000, 2000 i 4000 Hz.

    Zwraca None, jeśli w danych brakuje którejkolwiek z tych częstotliwości.
    """
    values = []
    for freq in PTA4_FREQS:
        if freq not in thresholds_for_ear:
            return None
        values.append(thresholds_for_ear[freq])
    return sum(values) / len(values)


# (nazwa stopnia, próg_min włącznie, próg_max wyłącznie,
#  opis w cichym otoczeniu, opis w hałaśliwym otoczeniu)
CLASSIFICATION_TABLE = [
    ("Słuch prawidłowy", None, 20,
     "Brak problemów ze słyszeniem dźwięków.",
     "Brak lub minimalne problemy ze słyszeniem dźwięków."),
    ("Lekki", 20, 35,
     "Brak problemów ze słyszeniem mowy o normalnym natężeniu.",
     "Mogą pojawić się trudności ze słyszeniem mowy o normalnym natężeniu."),
    ("Umiarkowany", 35, 50,
     "Mogą pojawić się trudności ze słyszeniem mowy o normalnym natężeniu.",
     "Trudności ze słyszeniem i braniem udziału w rozmowie."),
    ("Umiarkowanie głęboki", 50, 65,
     "Trudności ze słyszeniem mowy o normalnym natężeniu; brak trudności "
     "przy podniesionym głosie.",
     "Trudności ze słyszeniem większości wypowiedzi i braniem udziału w "
     "rozmowie."),
    ("Głęboki", 65, 80,
     "Brak słyszalności większości mowy o normalnym natężeniu; trudności "
     "ze słyszeniem i zrozumieniem podniesionego głosu.",
     "Skrajne trudności ze słyszeniem mowy i braniem udziału w rozmowie."),
    ("Głęboki / Resztki słuchowe", 80, 95,
     "Skrajne trudności ze słyszeniem podniesionego głosu.",
     "Mowa o normalnym natężeniu jest całkowicie niesłyszalna."),
    ("Całkowity lub pełna głuchota", 95, None,
     "Brak możliwości usłyszenia mowy oraz większości dźwięków otoczenia.",
     "Brak możliwości usłyszenia mowy oraz większości dźwięków otoczenia."),
]

UNILATERAL_DEGREE = "Jednostronny"
UNILATERAL_QUIET = (
    "Brak problemów, chyba że źródło dźwięku znajduje się blisko ucha "
    "gorszego. Możliwe trudności z lokalizacją dźwięku."
)
UNILATERAL_NOISE = (
    "Mogą wystąpić trudności ze słyszeniem mowy, braniem udziału w "
    "rozmowie oraz z lokalizacją dźwięków."
)


def _classify_value(value):
    for name, lo, hi, quiet, noise in CLASSIFICATION_TABLE:
        if (lo is None or value >= lo) and (hi is None or value < hi):
            return name, quiet, noise
    raise ValueError(f"Nie udało się sklasyfikować wartości PTA4: {value}")


def classify(pta4_left, pta4_right):
    """Klasyfikuje stopień ubytku słuchu na podstawie ucha lepiej słyszącego.

    pta4_left / pta4_right mogą być None, jeśli w danych brakuje wymaganych
    częstotliwości dla danego ucha. Zwraca None, jeśli nie da się policzyć
    żadnego z dwóch wskaźników.
    """
    candidates = [v for v in (pta4_left, pta4_right) if v is not None]
    if not candidates:
        return None

    if pta4_left is not None and pta4_right is not None:
        better = min(pta4_left, pta4_right)
        worse = max(pta4_left, pta4_right)
        # Przypadek jednostronny ma priorytet nad klasyfikacją samego
        # lepszego ucha, bo opisuje asymetrię między uszami.
        if better < 20 and worse >= 35:
            return {
                "pta4_left": pta4_left,
                "pta4_right": pta4_right,
                "better_ear_pta4": better,
                "degree": UNILATERAL_DEGREE,
                "quiet_description": UNILATERAL_QUIET,
                "noise_description": UNILATERAL_NOISE,
            }
    else:
        better = candidates[0]

    name, quiet, noise = _classify_value(better)
    return {
        "pta4_left": pta4_left,
        "pta4_right": pta4_right,
        "better_ear_pta4": better,
        "degree": name,
        "quiet_description": quiet,
        "noise_description": noise,
    }
