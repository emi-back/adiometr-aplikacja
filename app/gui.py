"""Główne okno aplikacji audiogramu (Tkinter)."""
import datetime
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from .serial_reader import SerialReader, list_serial_ports, load_from_file
from .audiogram_plot import plot_audiogram
from .hearing_loss import calculate_pta4, classify
from .report_export import build_report_figure, export_png, export_pdf


class AudiogramApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Audiogram - odczyt i raport")
        self.root.geometry("1300x950")

        self.result_queue = queue.Queue()
        self.status_queue = queue.Queue()
        self.log_queue = queue.Queue()
        self.serial_reader = None

        self.thresholds = {"L": {}, "P": {}}
        self.pta4_result = None

        self._build_widgets()
        self._refresh_ports()
        self._poll_queues()

    # ---------- budowa interfejsu ----------
    def _build_widgets(self):
        top = ttk.Frame(self.root, padding=8)
        top.pack(side="top", fill="x")

        conn_frame = ttk.LabelFrame(top, text="Połączenie z urządzeniem", padding=8)
        conn_frame.pack(side="left", fill="y", padx=(0, 8))

        ttk.Label(conn_frame, text="Port:").grid(row=0, column=0, sticky="w")
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(
            conn_frame, textvariable=self.port_var, width=12, state="readonly"
        )
        self.port_combo.grid(row=0, column=1, padx=4, pady=2)
        ttk.Button(conn_frame, text="Odśwież", command=self._refresh_ports).grid(
            row=0, column=2, padx=2
        )

        self.connect_btn = ttk.Button(
            conn_frame, text="Połącz", command=self._toggle_connection
        )
        self.connect_btn.grid(row=1, column=0, columnspan=2, sticky="we", pady=(4, 0))
        ttk.Button(conn_frame, text="Wczytaj z pliku...", command=self._load_file).grid(
            row=1, column=2, sticky="we", pady=(4, 0), padx=2
        )

        self.status_var = tk.StringVar(value="Brak połączenia.")
        ttk.Label(
            conn_frame, textvariable=self.status_var, foreground="gray", wraplength=260
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))

        patient_frame = ttk.LabelFrame(top, text="Dane pacjenta", padding=8)
        patient_frame.pack(side="left", fill="y", padx=(0, 8))

        self.patient_vars = {}
        fields = [
            ("name", "Imię i nazwisko"),
            ("birth_date", "Data urodzenia"),
            ("patient_id", "Nr pacjenta"),
            ("exam_date", "Data badania"),
            ("examiner", "Badający"),
        ]
        for i, (key, label) in enumerate(fields):
            ttk.Label(patient_frame, text=label + ":").grid(row=i, column=0, sticky="w", pady=2)
            var = tk.StringVar()
            ttk.Entry(patient_frame, textvariable=var, width=26).grid(
                row=i, column=1, sticky="we", pady=2, padx=4
            )
            self.patient_vars[key] = var
        self.patient_vars["exam_date"].set(datetime.date.today().isoformat())

        export_frame = ttk.LabelFrame(top, text="Eksport raportu", padding=8)
        export_frame.pack(side="left", fill="y")
        ttk.Button(export_frame, text="Eksportuj do PNG", command=self._export_png).pack(
            fill="x", pady=2
        )
        ttk.Button(export_frame, text="Eksportuj do PDF", command=self._export_pdf).pack(
            fill="x", pady=2
        )

        # Log z portu pakowany przed treścią (side="bottom"), żeby miał stałe miejsce
        # na dole okna niezależnie od rozmiaru wykresu.
        log_frame = ttk.LabelFrame(self.root, text="Log z portu", padding=6)
        log_frame.pack(side="bottom", fill="x", padx=8, pady=(0, 8))
        log_buttons = ttk.Frame(log_frame)
        log_buttons.pack(side="right", fill="y", padx=(6, 0))
        ttk.Button(log_buttons, text="Zapisz log...", command=self._save_log).pack(fill="x")
        ttk.Button(log_buttons, text="Wyczyść", command=self._clear_log).pack(fill="x", pady=(4, 0))
        self.log_text = tk.Text(log_frame, height=8, state="disabled", wrap="none")
        log_scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side="right", fill="y")
        self.log_text.pack(side="left", fill="both", expand=True)

        content = ttk.Frame(self.root)
        content.pack(side="top", fill="both", expand=True)

        # Panel wyniku pakowany jako pierwszy, żeby zarezerwować sobie stałą
        # szerokość po prawej stronie, zanim wykres (z expand=True) zajmie
        # całą pozostałą przestrzeń.
        result_frame = ttk.LabelFrame(content, text="Wynik", padding=10)
        result_frame.pack(side="right", fill="y", padx=(0, 8), pady=8)
        result_frame.configure(width=320)
        result_frame.pack_propagate(False)

        self.result_var = tk.StringVar(value="Brak danych. Wczytaj wynik badania.")
        ttk.Label(
            result_frame,
            textvariable=self.result_var,
            justify="left",
            anchor="nw",
            wraplength=290,
        ).pack(side="top", fill="x", anchor="n")

        plot_frame = ttk.Frame(content, padding=8)
        plot_frame.pack(side="left", fill="both", expand=True)

        self.figure = Figure(figsize=(7, 6), dpi=100)
        self.ax = self.figure.add_subplot(111)
        plot_audiogram(self.ax, self.thresholds)
        self.canvas = FigureCanvasTkAgg(self.figure, master=plot_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    # ---------- port szeregowy ----------
    def _refresh_ports(self):
        ports = list_serial_ports()
        self.port_combo["values"] = ports
        if ports and not self.port_var.get():
            self.port_var.set(ports[0])

    def _toggle_connection(self):
        if self.serial_reader is not None:
            self.serial_reader.stop()
            self.serial_reader = None
            self.connect_btn.config(text="Połącz")
            self.status_var.set("Rozłączono.")
            return

        port = self.port_var.get()
        if not port:
            messagebox.showwarning("Brak portu", "Wybierz port szeregowy.")
            return

        self.serial_reader = SerialReader(
            port, self.result_queue, self.status_queue, self.log_queue
        )
        self.serial_reader.start()
        self.connect_btn.config(text="Rozłącz")
        self.status_var.set(f"Łączenie z {port}...")

    def _load_file(self):
        path = filedialog.askopenfilename(
            title="Wczytaj plik z wynikami",
            filetypes=[("Pliki tekstowe/CSV", "*.txt *.csv *.log"), ("Wszystkie pliki", "*.*")],
        )
        if not path:
            return
        try:
            thresholds, errors = load_from_file(path)
        except OSError as exc:
            messagebox.showerror("Błąd wczytywania", str(exc))
            return

        if not thresholds.get("L") and not thresholds.get("P"):
            messagebox.showwarning("Brak danych", "Nie znaleziono poprawnych danych w pliku.")
            return

        if errors:
            self.status_var.set(f"Wczytano plik. Pominięto {len(errors)} błędnych wierszy.")
        else:
            self.status_var.set("Wczytano dane z pliku.")
        self._update_data(thresholds)

    # ---------- odbieranie danych w tle ----------
    def _poll_queues(self):
        # Wyjątek tutaj nie może przerwać odpytywania - inaczej po pierwszym błędzie
        # aplikacja przestaje reagować na cokolwiek z portu.
        try:
            self._drain_queues()
        except Exception as exc:
            self.status_var.set(f"Błąd aplikacji: {exc}")
            self._append_log("!", f"Błąd aplikacji: {exc!r}")
        finally:
            self.root.after(200, self._poll_queues)

    def _drain_queues(self):
        while True:
            try:
                kind, text = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self._append_log("»" if kind == "parsed" else " ", text)

        while True:
            try:
                thresholds = self.result_queue.get_nowait()
            except queue.Empty:
                break
            try:
                self._update_data(thresholds)
            except Exception as exc:
                self.status_var.set(f"Błąd rysowania wykresu: {exc}")
                self._append_log("!", f"Błąd rysowania wykresu: {exc!r}")

        while True:
            try:
                level, message = self.status_queue.get_nowait()
            except queue.Empty:
                break
            self.status_var.set(message)
            if level in ("warning", "stopped"):
                self._append_log("!", message)
            if level == "stopped":
                # wątek odczytu zakończył się sam - wróć do stanu "Połącz"
                self.serial_reader = None
                self.connect_btn.config(text="Połącz")

    # ---------- log z portu ----------
    LOG_MAX_LINES = 500

    def _append_log(self, prefix, text):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{prefix} {text}\n")
        total = int(self.log_text.index("end-1c").split(".")[0])
        if total > self.LOG_MAX_LINES:
            self.log_text.delete("1.0", f"{total - self.LOG_MAX_LINES + 1}.0")
        self.log_text.configure(state="disabled")
        self.log_text.see("end")

    def _clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _save_log(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Plik tekstowy", "*.txt"), ("Wszystkie pliki", "*.*")],
        )
        if not path:
            return
        # Zapisujemy tylko linie odebrane z portu (prefiks " "), żeby plik dało się
        # wczytać z powrotem przez "Wczytaj z pliku...".
        lines = [
            line[2:] for line in self.log_text.get("1.0", "end-1c").splitlines()
            if line.startswith("  ")
        ]
        try:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write("\n".join(lines) + "\n")
        except OSError as exc:
            messagebox.showerror("Błąd zapisu", str(exc))

    # ---------- aktualizacja danych/wykresu/wyniku ----------
    def _update_data(self, thresholds):
        self.thresholds = thresholds
        plot_audiogram(self.ax, self.thresholds)
        self.canvas.draw()

        pta4_l = calculate_pta4(self.thresholds.get("L", {}))
        pta4_p = calculate_pta4(self.thresholds.get("P", {}))
        self.pta4_result = classify(pta4_l, pta4_p)

        if self.pta4_result:
            l_txt = f"{pta4_l:.1f} dB HL" if pta4_l is not None else "brak danych"
            p_txt = f"{pta4_p:.1f} dB HL" if pta4_p is not None else "brak danych"
            self.result_var.set(
                f"PTA4 (500/1000/2000/4000 Hz)\n"
                f"Ucho lewe: {l_txt}\n"
                f"Ucho prawe: {p_txt}\n\n"
                f"Stopień ubytku słuchu:\n{self.pta4_result['degree']}\n\n"
                f"Cisza:\n{self.pta4_result['quiet_description']}\n\n"
                f"Hałas:\n{self.pta4_result['noise_description']}"
            )
        else:
            self.result_var.set("Brak wystarczających danych do obliczenia PTA4.")

    # ---------- eksport ----------
    def _collect_patient_data(self):
        return {key: var.get() for key, var in self.patient_vars.items()}

    def _export(self, extension, export_func, filetypes):
        if not self.thresholds.get("L") and not self.thresholds.get("P"):
            messagebox.showwarning("Brak danych", "Najpierw wczytaj wynik badania.")
            return
        path = filedialog.asksaveasfilename(defaultextension=extension, filetypes=filetypes)
        if not path:
            return
        fig = build_report_figure(self._collect_patient_data(), self.thresholds, self.pta4_result)
        try:
            export_func(fig, path)
        except OSError as exc:
            messagebox.showerror("Błąd zapisu", str(exc))
            return
        messagebox.showinfo("Eksport zakończony", f"Zapisano raport:\n{path}")

    def _export_png(self):
        self._export(".png", export_png, [("Obraz PNG", "*.png")])

    def _export_pdf(self):
        self._export(".pdf", export_pdf, [("Dokument PDF", "*.pdf")])

    def on_close(self):
        if self.serial_reader is not None:
            self.serial_reader.stop()
        self.root.destroy()


def run():
    root = tk.Tk()
    app = AudiogramApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
