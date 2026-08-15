"""
src/ui/dashboard_recap.py
Dedicated module for the Post-Draft Recap screen.
Calculates and displays Pool Grades, Steals, Reaches, and Synergies.
"""

import tkinter
from tkinter import ttk
import threading
from src.recap_actions import build_recap_data, fetch_draft_record
from src.ui.styles import Theme
from src.utils import open_file
from src.ui.components import ManaCurvePlot, TypePieChart


class DraftRecapScreen(ttk.Frame):
    def __init__(self, parent, launch_sealed_callback=None):
        super().__init__(parent)
        self.launch_sealed_callback = launch_sealed_callback
        self._dynamic_wrap_labels = []
        self._build_ui()
        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, event):
        if event.widget == self and event.width > 100:
            wrap_len = min(550, max(300, event.width - 60))
            for lbl in self._dynamic_wrap_labels:
                if lbl.winfo_exists():
                    lbl.configure(wraplength=wrap_len)

    def _create_stat_box(self, parent, title, text_var_name):
        frame = ttk.Labelframe(parent, text=title, padding=Theme.scaled_val(8))
        lbl = ttk.Label(frame, text="", font=Theme.scaled_font(9), justify="left")
        lbl.pack(anchor="nw", fill="both", expand=True)
        setattr(self, text_var_name, lbl)
        self._dynamic_wrap_labels.append(lbl)
        return frame

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # HEADER
        header_frame = ttk.Frame(
            self, padding=Theme.scaled_val(10), style="Card.TFrame"
        )
        header_frame.grid(row=0, column=0, sticky="ew")

        self.lbl_recovery_title = ttk.Label(
            header_frame,
            text="Draft Completed",
            font=Theme.scaled_font(18, "bold"),
            bootstyle="success",
        )
        self.lbl_recovery_title.pack(side="left")

        self.btn_17lands_link = ttk.Button(
            header_frame, text="View Draft on 17Lands 🌐", bootstyle="info-outline"
        )

        self.btn_sealed_studio = ttk.Button(
            header_frame,
            text="⚔️ Enter Sealed Studio",
            bootstyle="warning",
            command=self.launch_sealed_callback,
        )

        # TABBED CONTENT
        self.recap_notebook = ttk.Notebook(self)
        self.recap_notebook.grid(
            row=1,
            column=0,
            sticky="nsew",
            padx=Theme.scaled_val(10),
            pady=Theme.scaled_val((10, 0)),
        )

        # --- TAB 1: DRAFT RECAP ---
        tab_recap = ttk.Frame(self.recap_notebook, padding=Theme.scaled_val(15))
        self.recap_notebook.add(tab_recap, text=" 🏆 Draft Recap ")

        top_recap = ttk.Frame(tab_recap)
        top_recap.pack(fill="x", pady=Theme.scaled_val((0, 10)))

        self.lbl_recovery_grade = ttk.Label(
            top_recap,
            text="Pool Power Grade: --",
            font=Theme.scaled_font(16, "bold"),
            bootstyle="primary",
        )
        self.lbl_recovery_grade.pack(anchor="center", pady=Theme.scaled_val((0, 2)))

        self.lbl_recovery_stats = ttk.Label(
            top_recap, text="Top 23 Cards Avg Win Rate: --%", font=Theme.scaled_font(11)
        )
        self.lbl_recovery_stats.pack(anchor="center")

        self.lbl_actual_record = ttk.Label(
            top_recap, text="", font=Theme.scaled_font(11, "bold")
        )

        grid_recap = ttk.Frame(tab_recap)
        grid_recap.pack(fill="both", expand=True)
        grid_recap.columnconfigure((0, 1), weight=1)
        grid_recap.rowconfigure((0, 1), weight=1)

        self._create_stat_box(
            grid_recap, "TOP ARCHETYPES", "lbl_recap_archetypes"
        ).grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self._create_stat_box(grid_recap, "BEST CARDS DRAFTED", "lbl_recap_best").grid(
            row=0, column=1, sticky="nsew", padx=5, pady=5
        )
        self._create_stat_box(
            grid_recap, "BIGGEST STEALS (LATE PICKS)", "lbl_recap_steals"
        ).grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self._create_stat_box(
            grid_recap, "BIGGEST REACHES (EARLY PICKS)", "lbl_recap_reaches"
        ).grid(row=1, column=1, sticky="nsew", padx=5, pady=5)

        # --- TAB 2: SYNERGY & ROLES ---
        tab_synergy = ttk.Frame(self.recap_notebook, padding=Theme.scaled_val(15))
        self.recap_notebook.add(tab_synergy, text=" 🧩 Synergy & Roles ")

        grid_synergy = ttk.Frame(tab_synergy)
        grid_synergy.pack(fill="both", expand=True)
        grid_synergy.columnconfigure((0, 1), weight=1)
        grid_synergy.rowconfigure((0, 1), weight=1)

        self._create_stat_box(
            grid_synergy, "TOP CREATURE TYPES", "lbl_synergy_tribes"
        ).grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self._create_stat_box(grid_synergy, "CARD ROLES", "lbl_synergy_roles").grid(
            row=0, column=1, sticky="nsew", padx=5, pady=5
        )
        self._create_stat_box(
            grid_synergy, "PREMIUM STAPLES", "lbl_synergy_staples"
        ).grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self._create_stat_box(
            grid_synergy, "NON-BASIC LANDS", "lbl_synergy_lands"
        ).grid(row=1, column=1, sticky="nsew", padx=5, pady=5)

        # --- TAB 3: MANA & CURVE ---
        tab_analysis = ttk.Frame(self.recap_notebook, padding=Theme.scaled_val(15))
        self.recap_notebook.add(tab_analysis, text=" 📊 Mana & Curve ")
        tab_analysis.columnconfigure((0, 1), weight=1)
        tab_analysis.rowconfigure(0, weight=1)

        charts_frame = ttk.Frame(tab_analysis)
        charts_frame.grid(
            row=0, column=0, sticky="nsew", padx=Theme.scaled_val((0, 10))
        )

        ttk.Label(
            charts_frame,
            text="MANA CURVE",
            font=Theme.scaled_font(10, "bold"),
            bootstyle="primary",
        ).pack(anchor="w", pady=Theme.scaled_val((0, 5)))
        self.recap_curve_plot = ManaCurvePlot(charts_frame, ideal_distribution=[])
        self.recap_curve_plot.pack(fill="x", pady=Theme.scaled_val((0, 15)))

        ttk.Label(
            charts_frame,
            text="POOL BALANCE",
            font=Theme.scaled_font(10, "bold"),
            bootstyle="primary",
        ).pack(anchor="w", pady=Theme.scaled_val((0, 5)))
        self.recap_type_chart = TypePieChart(charts_frame)
        self.recap_type_chart.pack(fill="x")

        stats_col = ttk.Frame(tab_analysis)
        stats_col.grid(row=0, column=1, sticky="nsew")
        self._create_stat_box(stats_col, "RARES & MYTHICS", "lbl_recap_rares").pack(
            fill="both", expand=True, pady=Theme.scaled_val((0, 10))
        )
    def update_summary(self, taken_cards, metrics, draft_id, event_type):
        data = build_recap_data(taken_cards, metrics, draft_id, event_type)
        if not data.has_data:
            return

        self.lbl_actual_record.pack_forget()
        self.btn_17lands_link.pack_forget()

        self.lbl_recovery_grade.config(
            text=f"Pool Quality: {data.pool_power:.0f}/100 [{data.grade}]",
            bootstyle=data.grade_style,
        )
        self.lbl_recovery_stats.config(
            text=(
                f"Top 23 Avg Win Rate: {data.top_23_avg:.1f}% "
                f"(Format Avg: {data.format_avg:.1f}%)"
            )
        )

        arch_text = "".join(
            [
                f"• {n} ({w:.1f}%)\n" if w > 0 else f"• {n}\n"
                for n, w in data.archetypes
            ]
        )
        self.lbl_recap_archetypes.config(
            text=arch_text if arch_text else "None Identified"
        )

        self.lbl_recap_best.config(
            text="".join([f"• {n} ({w:.1f}%)\n" for n, w in data.best_cards])
        )

        self.lbl_recap_steals.config(
            text="".join(
                [
                    f"• {n} (P{pa}P{pi} | ALSA {a:.1f} | +{d:.1f})\n"
                    for n, pa, pi, a, d in data.steals
                ]
            )
            or "No major steals detected."
        )
        self.lbl_recap_reaches.config(
            text="".join(
                [
                    f"• {n} (P{pa}P{pi} | ATA {a:.1f} | -{d:.1f})\n"
                    for n, pa, pi, a, d in data.reaches
                ]
            )
            or "No major reaches detected."
        )

        self.lbl_synergy_tribes.config(
            text="".join([f"• {t} ({c})\n" for t, c in data.tribes])
            or "No creature types with 3+ cards."
        )
        self.lbl_synergy_roles.config(
            text="".join([f"• {t} ({c})\n" for t, c in data.roles])
            or "No Scryfall tags matched."
        )
        self.lbl_synergy_staples.config(
            text="".join([f"• {n} ({w:.1f}%)\n" for n, w in data.staples])
            or "No premium staples drafted."
        )
        self.lbl_synergy_lands.config(
            text="".join([f"• {n} ({w:.1f}%)\n" for n, w in data.non_basic_lands])
            or "No non-basic lands drafted."
        )
        self.lbl_recap_rares.config(
            text="".join([f"• {n} ({w:.1f}%)\n" for n, w in data.rares])
            or "No Rares or Mythics drafted."
        )

        # 7. CHARTS
        self.recap_curve_plot.update_curve(data.cmc_distribution)
        self.recap_type_chart.update_counts(data.type_counts)

        # 8. SEALED STUDIO BTN
        if data.is_sealed:
            self.btn_sealed_studio.pack(side="right", padx=Theme.scaled_val(10))
        else:
            self.btn_sealed_studio.pack_forget()

        # 9. 17LANDS API FETCH
        if data.draft_id:

            def fetch_17lands_record():
                record = fetch_draft_record(data.draft_id)

                def apply_ui():
                    if record:
                        w, l, url = record
                        self.lbl_actual_record.config(
                            text=f"Actual 17Lands Record: {w} Wins - {l} Losses",
                            bootstyle=(
                                "success"
                                if w >= 3
                                else ("warning" if w >= 1 else "danger")
                            ),
                        )
                        self.lbl_actual_record.pack(
                            anchor="center", pady=Theme.scaled_val((5, 0))
                        )
                        self.btn_17lands_link.config(
                            command=lambda: open_file(url)
                        )
                        self.btn_17lands_link.pack(
                            side="right", padx=Theme.scaled_val((0, 10))
                        )

                try:
                    self.after(0, apply_ui)
                except RuntimeError:
                    pass

            threading.Thread(target=fetch_17lands_record, daemon=True).start()
