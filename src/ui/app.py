"""
src/ui/app.py
Main UI Orchestrator.
Coordinates the Draft State, Background Threads, and UI Panels.
"""

import queue
import logging
from typing import Dict, Optional
import tkinter
from tkinter import ttk
import os
import sys

from src import constants
from src.configuration import write_configuration
from src.card_logic import filter_options, get_deck_metrics
from src.ui.styles import Theme

from src.ui.dashboard import DashboardFrame
from src.ui.orchestrator import DraftOrchestrator
from src.notifications import Notifications

# UI Components
from src.ui.loading_overlay import LoadingOverlay
from src.ui.menu_bar import AppMenuBar
from src.ui.top_bar import TopBarControls
from src.ui.card_interactions import CardInteractionManager
from src.ui.windows.overlay import CompactOverlay

# Main Tab Panels
from src.ui.windows.taken_cards import TakenCardsPanel
from src.ui.windows.suggest_deck import SuggestDeckPanel
from src.ui.windows.custom_deck import CustomDeckPanel
from src.ui.windows.compare import ComparePanel
from src.ui.windows.download import DownloadWindow
from src.ui.windows.tier_list_panel import TierListWindow
from src.ui.windows.settings import SettingsWindow

# Logic Engines
from src.advisor.engine import DraftAdvisor
from src.signals import SignalCalculator

logger = logging.getLogger(__name__)


class DraftApp:
    """
    The Core Application Manager.
    Responsible for initializing the Tkinter root, drawing the layout,
    and managing the Event Loop to sync the UI with the background scanner.
    """

    def __init__(self, root: tkinter.Tk, scanner, configuration):
        self.root = root
        self.configuration = configuration

        # 1. IMMEDIATE STATE INITIALIZATION
        self.vars: Dict[str, tkinter.Variable] = {}
        self.deck_filter_map: Dict[str, str] = {}
        self.overlay_window: Optional[CompactOverlay] = None

        self._initialized = False
        self._rebuilding_ui = False
        self._loading = False
        self._update_task_id: Optional[str] = None
        self.previous_timestamp = 0

        self.current_pack_data = []
        self.current_missing_data = []
        self.tabs_visible = True

        # Event Tracking State
        self.current_set_data_map: Dict[str, Dict[str, str]] = {}
        self.detected_set_code = ""
        self.active_event_set = ""
        self.active_event_type = ""
        self.current_draft_id = ""

        # 2. CORE LOGIC SERVICE
        self.orchestrator = DraftOrchestrator(
            scanner, configuration, self._refresh_ui_data
        )

        # 3. INITIAL THEME APPLICATION
        current_scale = constants.UI_SIZE_DICT.get(
            self.configuration.settings.ui_size, 1.0
        )
        Theme.apply(
            self.root,
            palette=self.configuration.settings.theme,
            engine=getattr(self.configuration.settings, "theme_base", "clam"),
            custom_path=getattr(self.configuration.settings, "theme_custom_path", ""),
            scale=current_scale,
        )

        # 4. BUILD UI SHELL
        self._setup_variables()
        self.interactions = CardInteractionManager(self)
        self._build_layout()

        # Attach extracted modular components
        self.menu_bar = AppMenuBar(self.root, self)
        self.loading_overlay = LoadingOverlay(self.root)

        # 5. ATTACH INFRASTRUCTURE SERVICES
        self.notifications = Notifications(
            self.root, scanner.set_list, configuration, self.panel_data
        )

        # 6. VIRTUAL EVENT BINDINGS
        self.root.bind(
            "<<ShowDataTab>>",
            lambda e: self._ensure_tabs_visible()
            or self.notebook.select(self.panel_data),
        )

        # 7. FINAL WINDOW PROTOCOL & METADATA
        self.root.title(f"MTGA Draft Tool v{constants.APPLICATION_VERSION}")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.attributes("-topmost", self.configuration.settings.always_on_top)

        # 8. ENABLE LOGGING
        self.orchestrator.scanner.log_enable(
            self.configuration.settings.draft_log_enabled
        )

        self._loading = True
        self._initialized = True

    def _perform_boot_sync(self):
        """Phase 1: Immediate synchronization of critical UI components."""
        if not self._initialized:
            return

        try:
            self.vars["status_text"].set("Syncing with Arena...")

            # Apply user's saved window dimensions
            try:
                geom = self.configuration.settings.main_window_geometry
                if geom and "x" in geom and not geom.startswith("1x1"):
                    self.root.geometry(geom)
                else:
                    self.root.geometry(
                        f"{Theme.scaled_val(1200)}x{Theme.scaled_val(800)}"
                    )

                self.root.update_idletasks()

                def apply_sashes():
                    try:
                        sash_pos = self.configuration.settings.paned_window_sash
                        if sash_pos > Theme.scaled_val(50) and self.tabs_visible:
                            self.splitter.sashpos(0, sash_pos)

                        dash_sash = getattr(
                            self.configuration.settings,
                            "dashboard_sash",
                            Theme.scaled_val(800),
                        )
                        if dash_sash > Theme.scaled_val(50) and hasattr(
                            self.dashboard, "h_splitter"
                        ):
                            curr_w = self.dashboard.winfo_width()
                            if curr_w > Theme.scaled_val(200):
                                safe_sash = min(
                                    dash_sash, curr_w - Theme.scaled_val(280)
                                )
                                if safe_sash > Theme.scaled_val(50):
                                    self.dashboard.h_splitter.sashpos(0, safe_sash)
                    except Exception:
                        pass

                self.root.after(100, apply_sashes)
                self.root.after(500, apply_sashes)

            except Exception as e:
                logger.warning(f"Failed to apply window preferences: {e}")

            # START THE ENGINE
            self.orchestrator.start()

            try:
                self.top_bar.update_data_sources()
                self.top_bar.update_deck_filter_options()
            except Exception as e:
                logger.error(f"Dropdown sync failed: {e}", exc_info=True)

            self._refresh_ui_data()
            self.root.after(500, self._perform_deep_sync)
            self._schedule_update()

        finally:
            self._loading = False

    def _perform_deep_sync(self):
        """Phase 2: Population of heavy tabs (Deck Builder, Card Pool)."""
        self.vars["status_text"].set("Ready")

        for p in [self.panel_taken, self.panel_suggest]:
            try:
                p.refresh()
            except:
                pass

        if not self.configuration.card_data.latest_dataset:
            self.notebook.select(self.panel_data)
        elif os.path.basename(self.orchestrator.scanner.arena_file).startswith(
            "DraftLog_"
        ):
            self.notebook.select(self.panel_suggest)

        self.root.after(1500, self._background_update_checks)

    def _background_update_checks(self):
        """Executes non-critical network checks (e.g., GitHub Releases)."""
        if not hasattr(self, "notifications") or self.notifications is None:
            return

        import threading

        def _check_app():
            try:
                from src.app_update import AppUpdate

                v, _ = AppUpdate().retrieve_file_version()
                if v and float(v) > float(constants.APPLICATION_VERSION):
                    self.root.after(0, lambda: self.menu_bar.notify_app_update(v))
            except Exception as e:
                logger.error(f"App update check failed: {e}")

        threading.Thread(target=_check_app, daemon=True).start()

        try:
            self.notifications.check_dataset()
        except Exception as e:
            logger.error(f"Dataset update check failed: {e}")

    def _on_close(self):
        """Save geometry and sash state before closing."""
        try:
            if self.root.state() == "normal":
                self.configuration.settings.main_window_geometry = self.root.geometry()

            try:
                if self.tabs_visible:
                    self.configuration.settings.paned_window_sash = (
                        self.splitter.sashpos(0)
                    )
                if hasattr(self, "dashboard") and hasattr(self.dashboard, "h_splitter"):
                    if self.dashboard.sidebar_visible:
                        self.configuration.settings.dashboard_sash = (
                            self.dashboard.h_splitter.sashpos(0)
                        )
            except:
                pass

            write_configuration(self.configuration)

            if hasattr(self, "orchestrator"):
                self.orchestrator.stop()

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

        self.root.destroy()
        os._exit(0)

    def _setup_variables(self):
        """Initializes all bound Tkinter String/Int Vars."""
        self.vars["deck_filter"] = tkinter.StringVar(
            value=self.configuration.settings.deck_filter
        )
        self.vars["set_label"] = tkinter.StringVar(value="")
        self.vars["selected_event"] = tkinter.StringVar(value="")
        self.vars["selected_group"] = tkinter.StringVar(value="")
        self.vars["status_text"] = tkinter.StringVar(value="Ready")

    def _build_layout(self):
        """Constructs the primary shell (TopBar, Dashboard Pane, Tabs Pane)."""
        if hasattr(self, "main_container"):
            self.main_container.destroy()
        self.main_container = ttk.Frame(self.root, padding=Theme.scaled_val(8))
        self.main_container.pack(fill="both", expand=True)

        self.top_bar = TopBarControls(self.main_container, self)
        self.top_bar.pack(fill="x", pady=(0, Theme.scaled_val(10)))

        # Main Splitter
        self.splitter = ttk.PanedWindow(self.main_container, orient=tkinter.VERTICAL)
        self.splitter.pack(fill="both", expand=True)

        self.top_pane = ttk.Frame(self.splitter)
        self.splitter.add(self.top_pane, weight=4)

        self.dashboard = DashboardFrame(
            self.top_pane,
            self.configuration,
            self.interactions.on_card_select,
            self._refresh_ui_data,
            on_advisor_click=self.interactions.show_tooltip_from_advisor,
            on_context_menu=self.interactions.on_card_context_menu,
        )

        self.bottom_pane = ttk.Frame(self.splitter)
        self.splitter.add(self.bottom_pane, weight=2)

        self.tab_controls = ttk.Frame(
            self.top_pane, padding=Theme.scaled_val((10, 5, 10, 5))
        )
        self.tab_controls.pack(side="bottom", fill="x")

        self.footer_separator = ttk.Separator(self.top_pane, orient="horizontal")
        self.footer_separator.pack(side="bottom", fill="x")

        self.dashboard.pack(side="top", fill="both", expand=True)

        self.btn_toggle_tabs = ttk.Button(
            self.tab_controls,
            text="▼ Hide Tabs",
            bootstyle="secondary-outline",
            command=self._toggle_tabs,
            cursor="hand2",
        )
        self.btn_toggle_tabs.pack(side="right", padx=Theme.scaled_val(5))

        self.lbl_session_info = ttk.Label(
            self.tab_controls,
            font=Theme.scaled_font(9),
            bootstyle="secondary",
            anchor="w",
        )
        self.lbl_session_info.pack(
            side="left", fill="x", expand=True, padx=Theme.scaled_val(5)
        )

        # Tabs
        self.notebook = ttk.Notebook(self.bottom_pane)
        self.notebook.pack(fill="both", expand=True)

        self.panel_taken = TakenCardsPanel(
            self.notebook, self.orchestrator.scanner, self.configuration
        )
        self.panel_suggest = SuggestDeckPanel(
            self.notebook,
            self.orchestrator.scanner,
            self.configuration,
            on_export_custom=lambda deck, sb: [
                self.panel_custom.import_deck(deck, sb),
                self.notebook.select(self.panel_custom),
            ],
            app_context=self,
        )
        self.panel_custom = CustomDeckPanel(
            self.notebook, self.orchestrator.scanner, self.configuration, self
        )
        self.panel_compare = ComparePanel(
            self.notebook, self.orchestrator.scanner, self.configuration
        )
        self.panel_data = DownloadWindow(
            self.notebook,
            self.orchestrator.scanner.set_list,
            self.configuration,
            self._on_dataset_update,
        )
        self.panel_tiers = TierListWindow(
            self.notebook, self.configuration, self._refresh_ui_data
        )

        self.notebook.add(self.panel_data, text=" Datasets ")
        self.notebook.add(self.panel_taken, text=" Card Pool ")
        self.notebook.add(self.panel_suggest, text=" Deck Builder ")
        self.notebook.add(self.panel_custom, text=" Custom Deck ")
        self.notebook.add(self.panel_compare, text=" Comparisons ")
        self.notebook.add(self.panel_tiers, text=" Tier Lists ")

        # Safely trigger dataset UI refreshes if the panel supports it (prevents Pytest Mocking crashes)
        self.notebook.bind(
            "<<NotebookTabChanged>>",
            lambda e: (
                self.panel_data.refresh()
                if hasattr(self.panel_data, "refresh")
                and "Datasets" in self.notebook.tab(self.notebook.select(), "text")
                else None
            ),
        )

    def _force_reload(self):
        """Forces a deep scan of the active Arena Log."""
        self.vars["status_text"].set("Deep Scanning Log...")
        if hasattr(self, "loading_overlay"):
            self.loading_overlay.show("Reloading Application State")
            self.loading_overlay.update_status("Deep Scanning Log...")
        self.root.update_idletasks()

        with self.orchestrator.scanner.lock:
            self.orchestrator.scanner.clear_draft(True)
            if (
                hasattr(self.orchestrator.scanner, "set_data")
                and self.orchestrator.scanner.set_data
            ):
                self.orchestrator.scanner.set_data.unknown_id_cache.clear()

        self.orchestrator.trigger_full_scan()

    def update_session_info(self, event_name, draft_id, start_time):
        """Displays technical metadata silently in the footer."""
        if not hasattr(self, "lbl_session_info"):
            return
        parts = []
        if event_name:
            parts.append(str(event_name))
        if draft_id:
            parts.append(str(draft_id))
        if start_time:
            parts.append(str(start_time))
        self.lbl_session_info.config(text=" | ".join(parts))

    def _toggle_tabs(self):
        if self.tabs_visible:
            self.splitter.forget(self.bottom_pane)
            self.btn_toggle_tabs.config(text="▲ Show Tabs")
            self.tabs_visible = False
        else:
            self.splitter.add(self.bottom_pane, weight=2)
            self.btn_toggle_tabs.config(text="▼ Hide Tabs")
            self.tabs_visible = True

    def _ensure_tabs_visible(self):
        if not self.tabs_visible:
            self._toggle_tabs()

    def _open_settings(self):
        def _on_settings_changed(key=None):
            s = self.configuration.settings

            if key == "always_on_top" or key is None:
                self.root.attributes("-topmost", s.always_on_top)

            if key == "draft_log_enabled" or key is None:
                self.orchestrator.scanner.log_enable(s.draft_log_enabled)

            if (
                key in ["theme", "theme_base", "theme_custom_path", "ui_size"]
                or key is None
            ):
                current_scale = constants.UI_SIZE_DICT.get(s.ui_size, 1.0)
                Theme.apply(
                    self.root,
                    palette=s.theme,
                    engine=getattr(s, "theme_base", "clam"),
                    custom_path=s.theme_custom_path,
                    scale=current_scale,
                )

            if key in ["filter_format"] or key is None:
                self.top_bar.update_deck_filter_options()

            if key in ["result_format", "card_colors_enabled"] or key is None:
                self._refresh_ui_data()

        parent_window = self.overlay_window if self.overlay_window else self.root
        SettingsWindow(parent_window, self.configuration, _on_settings_changed)

    def _refresh_ui_data(self):
        """Core UI Synchronization Logic."""
        if not self._initialized or self._rebuilding_ui:
            return

        lock_acquired = self.orchestrator.scanner.lock.acquire(blocking=False)
        if not lock_acquired:
            self.root.after(100, self._refresh_ui_data)
            return

        try:
            # 1. SNAPSHOT STATE
            es, et = self.orchestrator.scanner.retrieve_current_limited_event()
            pk, pi = self.orchestrator.scanner.retrieve_current_pack_and_pick()
            metrics = self.orchestrator.scanner.retrieve_set_metrics()
            tier_data = self.orchestrator.scanner.retrieve_tier_data()
            taken_cards = self.orchestrator.scanner.retrieve_taken_cards()
            pack_cards = self.orchestrator.scanner.retrieve_current_pack_cards()
            missing_cards = self.orchestrator.scanner.retrieve_current_missing_cards()
            current_picked_cards = (
                self.orchestrator.scanner.retrieve_current_picked_cards()
            )
            history = self.orchestrator.scanner.retrieve_draft_history()
            draft_id = self.orchestrator.scanner.current_draft_id
            start_time = self.orchestrator.scanner.draft_start_time
            event_string = self.orchestrator.scanner.event_string
        finally:
            self.orchestrator.scanner.lock.release()

        # 2. ADVISOR & SIGNAL MATH
        sig_calc = SignalCalculator(metrics)
        scores = {c: 0.0 for c in constants.CARD_COLORS}
        for entry in history:
            if entry["Pack"] == 2:
                continue
            h_pack = self.orchestrator.scanner.set_data.get_data_by_id(entry["Cards"])
            for c, v in sig_calc.calculate_pack_signals(h_pack, entry["Pick"]).items():
                scores[c] += v

        # Pass signals securely into Advisor so it can weigh tie-breakers towards Open Lanes
        advisor = DraftAdvisor(metrics, taken_cards, signals=scores)
        recommendations = advisor.evaluate_pack(pack_cards, pi, current_pack=pk)

        # 3. DRAW UI
        if pk > 0:
            self.vars["status_text"].set(f"Pack {pk} Pick {pi}")
            if hasattr(self.top_bar, "lbl_status"):
                self.top_bar.lbl_status.configure(bootstyle="success")
        else:
            self.vars["status_text"].set("Waiting for draft...")
            if hasattr(self.top_bar, "lbl_status"):
                self.top_bar.lbl_status.configure(bootstyle="secondary")

        colors = filter_options(
            taken_cards,
            self.configuration.settings.deck_filter,
            metrics,
            self.configuration,
        )

        self.top_bar.update_auto_detect_label(colors)

        self.dashboard._current_event_set = es
        self.dashboard._current_event_type = et
        self.dashboard._current_pack = pk
        self.dashboard._current_pick = pi

        self.update_session_info(event_string, draft_id, start_time)
        self.dashboard.update_recommendations(recommendations)
        self.dashboard.update_signals(scores)

        self.dashboard.update_pack_data(
            pack_cards,
            colors,
            metrics,
            tier_data,
            pi,
            "pack",
            recommendations,
            current_picked_cards,
        )
        self.dashboard.update_pack_data(
            missing_cards, colors, metrics, tier_data, pi, "missing"
        )

        deck_metrics = get_deck_metrics(taken_cards)
        self.dashboard.update_stats(deck_metrics.distribution_all)
        self.dashboard.update_deck_balance(taken_cards)
        self.dashboard.orchestrator = self.orchestrator
        self.dashboard.update_pool_summary(taken_cards, metrics, draft_id)

        if self.overlay_window:
            self.overlay_window.update_data(
                pack_cards,
                colors,
                metrics,
                tier_data,
                pi,
                recommendations,
                current_picked_cards,
            )

        # Broadcast refresh downwards
        for p in [
            self.panel_taken,
            self.panel_suggest,
            self.panel_custom,
            self.panel_compare,
            self.panel_tiers,
        ]:
            try:
                if hasattr(p, "refresh"):
                    p.refresh()
            except Exception:
                pass

        self.current_pack_data = pack_cards
        self.current_missing_data = missing_cards

    def _update_loop(self):
        """UI Poll Loop: Checks the orchestrator's queue for updates."""
        if not self.root.winfo_exists():
            return

        try:
            is_test = "pytest" in sys.modules
            if not self.orchestrator.is_alive() or is_test:
                self.orchestrator.step_process()

            update_detected = False
            while True:
                try:
                    msg = self.orchestrator.update_queue.get_nowait()
                    if isinstance(msg, dict) and "status" in msg:
                        self.vars["status_text"].set(msg["status"])
                        if hasattr(self, "loading_overlay"):
                            self.loading_overlay.update_status(msg["status"])
                        self.root.update_idletasks()
                    elif msg == "REFRESH":
                        update_detected = True
                except queue.Empty:
                    break

            if update_detected:
                self.top_bar.set_history_dropdown_state("readonly")
                self.top_bar.update_data_sources()
                self.top_bar.update_deck_filter_options()
                self._refresh_ui_data()
                if is_test:
                    self.root.update()

            try:
                ts = os.stat(self.orchestrator.scanner.arena_file).st_mtime
                self.top_bar.update_status_dot(ts, self.previous_timestamp)
                self.previous_timestamp = ts
            except:
                pass
        except Exception as e:
            logger.error(f"Logic Step Error: {e}")
            if hasattr(self, "loading_overlay"):
                self.loading_overlay.hide()

        self._schedule_update()

    def _schedule_update(self):
        self._update_task_id = self.root.after(100, self._update_loop)

    def _on_dataset_update(self):
        latest_file = self.configuration.card_data.latest_dataset
        if latest_file:
            from src.constants import SETS_FOLDER

            full_path = os.path.join(SETS_FOLDER, latest_file)
            if os.path.exists(full_path):
                try:
                    self.orchestrator.scanner.retrieve_set_data(full_path)
                    from src.card_logic import clear_deck_cache

                    clear_deck_cache()
                except Exception:
                    pass

        self.top_bar.update_data_sources()
        self.top_bar.update_deck_filter_options()
        self.orchestrator.request_math_update()
        self._refresh_ui_data()

    def _enable_overlay(self):
        if self.overlay_window:
            return
        self.root.withdraw()
        self.overlay_window = CompactOverlay(
            self.root, self, self.configuration, self._disable_overlay
        )
        self._refresh_ui_data()

    def _disable_overlay(self):
        if self.overlay_window:
            self.overlay_window.destroy()
            self.overlay_window = None
        self.root.deiconify()
        current_scale = constants.UI_SIZE_DICT.get(
            self.configuration.settings.ui_size, 1.0
        )
        Theme.apply(
            self.root,
            palette=self.configuration.settings.theme,
            engine=getattr(self.configuration.settings, "theme_base", "clam"),
            custom_path=self.configuration.settings.theme_custom_path,
            scale=current_scale,
        )
        self._refresh_ui_data()
