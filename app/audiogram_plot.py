"""Rysowanie audiogramu tonalnego zgodnie z normą ISO 8253-1.

Reguły:
- oś X (częstotliwość, Hz): skala logarytmiczna, 125-8000 Hz;
- oś Y (poziom słyszenia, dB HL): odwrócona, od -10 dB (góra) do 120 dB (dół);
- proporcje wykresu: odstęp odpowiadający jednej oktawie na osi X musi być
  wizualnie równy odstępowi odpowiadającemu 20 dB na osi Y;
- ucho prawe (P): kolor czerwony, symbol okręgu (O), linia ciągła;
- ucho lewe (L): kolor niebieski, symbol krzyżyka (X), linia ciągła.
"""
import math

from matplotlib.ticker import NullLocator

FREQ_MIN = 125
FREQ_MAX = 8000
DB_MIN = -10
DB_MAX = 120

STANDARD_FREQS = [125, 250, 500, 1000, 2000, 3000, 4000, 8000]

EAR_STYLE = {
    "P": {"color": "red", "marker": "o", "label": "Ucho prawe (P)"},
    "L": {"color": "blue", "marker": "x", "label": "Ucho lewe (L)"},
}

# Niewielki margines wokół 125-8000 Hz / -10-120 dB, żeby symbole pomiarowe
# na skrajnych częstotliwościach (np. 8000 Hz) nie były przycinane przez
# ramkę wykresu. Margines osi Y jest wyliczany z tej samej proporcji co
# margines osi X (log2(FREQ_AXIS_PAD_RATIO) oktawy == tyle samo * 20 dB),
# więc reguła ISO 8253-1 (1 oktawa == 20 dB) obowiązuje również w marginesie.
FREQ_AXIS_PAD_RATIO = 1.05
_DB_AXIS_PAD = 20 * math.log2(FREQ_AXIS_PAD_RATIO)

X_MIN_DISPLAY = FREQ_MIN / FREQ_AXIS_PAD_RATIO
X_MAX_DISPLAY = FREQ_MAX * FREQ_AXIS_PAD_RATIO
Y_TOP_DISPLAY = DB_MIN - _DB_AXIS_PAD
Y_BOTTOM_DISPLAY = DB_MAX + _DB_AXIS_PAD

# Fizyczna wysokość/szerokość osi wynikająca z reguły ISO 8253-1:
# 1 oktawa na osi X == 20 dB na osi Y (liczona na podstawie faktycznie
# wyświetlanego zakresu, razem z marginesem).
_N_OCTAVES = math.log2(X_MAX_DISPLAY / X_MIN_DISPLAY)
_N_20DB_UNITS = (Y_BOTTOM_DISPLAY - Y_TOP_DISPLAY) / 20.0
BOX_ASPECT = _N_20DB_UNITS / _N_OCTAVES


def plot_audiogram(ax, thresholds):
    """Rysuje audiogram na przekazanych osiach matplotlib.

    thresholds: {"L": {frequency_hz: threshold_db, ...}, "P": {...}}
    """
    ax.clear()

    ax.set_xscale("log")
    ax.set_xlim(X_MIN_DISPLAY, X_MAX_DISPLAY)
    ax.set_ylim(Y_BOTTOM_DISPLAY, Y_TOP_DISPLAY)  # odwrócona oś Y

    ax.set_xticks(STANDARD_FREQS)
    ax.set_xticklabels([str(f) for f in STANDARD_FREQS], fontsize=8)
    ax.xaxis.set_minor_locator(NullLocator())

    ax.set_yticks(range(DB_MIN, DB_MAX + 1, 10))
    ax.tick_params(axis="y", labelsize=8)

    ax.set_box_aspect(BOX_ASPECT)

    ax.grid(True, which="major", linestyle="-", linewidth=0.5, color="gray", alpha=0.5)
    ax.set_xlabel("Częstotliwość (Hz)", fontsize=9, labelpad=8)
    ax.set_ylabel("Poziom słyszenia (dB HL)", fontsize=9)
    ax.set_title("Audiogram tonalny (przewodnictwo powietrzne)", fontsize=10, pad=10)

    plotted_any = False
    for ear in ("P", "L"):
        ear_data = thresholds.get(ear) or {}
        if not ear_data:
            continue
        freqs = sorted(ear_data)
        dbs = [ear_data[f] for f in freqs]
        style = EAR_STYLE[ear]
        ax.plot(
            freqs,
            dbs,
            color=style["color"],
            marker=style["marker"],
            markerfacecolor="none" if style["marker"] == "o" else style["color"],
            markeredgecolor=style["color"],
            markeredgewidth=2,
            markersize=9,
            linestyle="-",
            linewidth=1.5,
            label=style["label"],
        )
        plotted_any = True

    if plotted_any:
        ax.legend(loc="lower left", fontsize=8)
