"""Budowa raportu (wykres + dane pacjenta + wynik) i eksport do PNG/PDF."""
from matplotlib.figure import Figure

from .audiogram_plot import plot_audiogram


def build_report_figure(patient_data, thresholds, pta4_result):
    """Buduje pojedynczą figurę A4 z nagłówkiem (dane pacjenta), audiogramem
    i stopką (wynik PTA4 oraz opis stopnia ubytku słuchu).

    patient_data: dict z kluczami name, birth_date, patient_id, exam_date, examiner.
    thresholds: {"L": {...}, "P": {...}}
    pta4_result: wynik app.hearing_loss.classify(...) albo None.
    """
    fig = Figure(figsize=(8.27, 11.69), dpi=150)  # A4 w pionie

    header_ax = fig.add_axes([0.06, 0.88, 0.88, 0.09])
    header_ax.axis("off")
    header_text = (
        "Raport badania audiometrycznego\n\n"
        f"Pacjent: {patient_data.get('name', '')}\n"
        f"Data urodzenia: {patient_data.get('birth_date', '')}"
        f"          Nr pacjenta: {patient_data.get('patient_id', '')}\n"
        f"Data badania: {patient_data.get('exam_date', '')}"
        f"          Badający: {patient_data.get('examiner', '')}"
    )
    header_ax.text(0, 1, header_text, va="top", ha="left", fontsize=11)

    # Między dolną krawędzią wykresu a stopką zostawiamy spory margines
    # (0.40 - 0.31 = 0.09 wysokości figury), bo etykieta osi X i podpisy
    # częstotliwości muszą zmieścić się w tym pasie bez nachodzenia na tekst
    # stopki.
    plot_ax = fig.add_axes([0.12, 0.40, 0.76, 0.42])
    plot_audiogram(plot_ax, thresholds)

    footer_ax = fig.add_axes([0.06, 0.03, 0.88, 0.28])
    footer_ax.axis("off")

    if pta4_result:
        pta4_l = pta4_result["pta4_left"]
        pta4_p = pta4_result["pta4_right"]
        pta4_l_txt = f"{pta4_l:.1f} dB HL" if pta4_l is not None else "brak danych"
        pta4_p_txt = f"{pta4_p:.1f} dB HL" if pta4_p is not None else "brak danych"
        footer_text = (
            "Wskaźnik PTA4 (średnia progów dla 500, 1000, 2000, 4000 Hz):\n"
            f"  Ucho lewe (L): {pta4_l_txt}          Ucho prawe (P): {pta4_p_txt}\n\n"
            f"Stopień ubytku słuchu (wg ucha lepiej słyszącego): {pta4_result['degree']}\n\n"
            "Zdolność słyszenia w cichym otoczeniu:\n"
            f"  {pta4_result['quiet_description']}\n\n"
            "Zdolność słyszenia w hałaśliwym otoczeniu:\n"
            f"  {pta4_result['noise_description']}"
        )
    else:
        footer_text = "Brak wystarczających danych do obliczenia wskaźnika PTA4."

    footer_ax.text(0, 1, footer_text, va="top", ha="left", fontsize=10, wrap=True)

    return fig


def export_png(fig, path):
    fig.savefig(path, format="png", dpi=300)


def export_pdf(fig, path):
    fig.savefig(path, format="pdf")
