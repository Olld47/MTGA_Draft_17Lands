"""
src/ui/windows/practice_dialog.py
Dialog for generating or importing a practice Sealed pool.
"""

import os
import tkinter
from tkinter import messagebox
import ttkbootstrap as ttk

from src.practice_actions import (
    build_set_options,
    dataset_rank,
    generate_random_pool,
    new_session_id,
    parse_pool_text,
)
from src.ui.styles import Theme
from src.utils import read_local_manifest, retrieve_local_set_list
from src.configuration import write_configuration
from src.ui.windows.sealed_studio import SealedStudioWindow


class PracticeDialog(tkinter.Toplevel):
    def __init__(self, parent, app_context, is_import=False):
        super().__init__(parent)
        self.app_context = app_context
        self.is_import = is_import

        title = "Import Sealed Pool" if is_import else "Generate Random Sealed Pool"
        self.title(title)
        self.geometry(f"{Theme.scaled_val(420)}x{Theme.scaled_val(220)}")
        Theme.apply(self, self.app_context.configuration.settings.theme)

        self.transient(parent)
        self.grab_set()

        self._build_ui()

    def _build_ui(self):
        ttk.Label(
            self,
            text="Select a Set to use for this session:",
            font=Theme.scaled_font(10, "bold"),
        ).pack(pady=Theme.scaled_val(15))

        # 1. Gather all available sets from the application metadata
        set_list_data = getattr(
            self.app_context.orchestrator.scanner.set_list, "data", {}
        )
        if not set_list_data:
            messagebox.showwarning(
                "Error",
                "Set list not loaded. Please wait for the app to initialize.",
                parent=self,
            )
            self.destroy()
            return

        active_codes = list(read_local_manifest().get("active_sets", []) or [])
        latest = getattr(
            self.app_context.orchestrator.scanner.set_list, "latest_set", ""
        )

        # 2. Shared dropdown assembly: manifest-active sets first (manifest
        # order), then the rest alphabetically (src.practice_actions).
        options = build_set_options(set_list_data, active_codes, latest)

        active_names = []
        inactive_names = []
        self.code_to_name = {}
        for option in options:
            display_name = f"{option['name']} ({option['code']})"
            self.code_to_name[display_name] = option["code"]
            if option["is_active"]:
                active_names.append(display_name)
            else:
                inactive_names.append(display_name)

        default_val = (
            active_names[0]
            if active_names
            else (inactive_names[0] if inactive_names else "")
        )
        self.var_set = tkinter.StringVar(value=default_val)

        cb_frame = ttk.Frame(self)
        cb_frame.pack(pady=Theme.scaled_val(10))
        om = ttk.OptionMenu(cb_frame, self.var_set, default_val)
        menu = om["menu"]
        menu.delete(0, "end")

        for opt in active_names:
            menu.add_command(label=opt, command=tkinter._setit(self.var_set, opt))

        if active_names and inactive_names:
            menu.add_separator()

        for opt in inactive_names:
            menu.add_command(label=opt, command=tkinter._setit(self.var_set, opt))

        om.pack(fill="x", expand=True, padx=Theme.scaled_val(20))

        btn_text = "Import from Clipboard" if self.is_import else "Generate Pack"
        ttk.Button(
            self, text=btn_text, bootstyle="success", command=self._on_confirm
        ).pack(pady=Theme.scaled_val(20))

    def _on_confirm(self):
        selected = self.var_set.get()
        if not selected:
            return

        target_code = self.code_to_name[selected]
        datasets, _ = retrieve_local_set_list(codes=[target_code])

        if not datasets:
            messagebox.showwarning(
                "Dataset Missing",
                f"No downloaded dataset found for {selected}.\n\nPlease go to the Datasets tab and download it first.",
                parent=self,
            )
            self.destroy()
            return

        # Shared dataset preference: Sealed > Premier > Traditional.
        best_dataset = min(datasets, key=lambda d: dataset_rank(d[1]))
        filepath = best_dataset[6]

        # Switch the main app to this dataset immediately so stats sync up globally
        try:
            self.app_context.orchestrator.scanner.retrieve_set_data(filepath)
            self.app_context.configuration.card_data.latest_dataset = os.path.basename(
                filepath
            )
            write_configuration(self.app_context.configuration)
            self.app_context._update_data_sources()
            self.app_context._update_deck_filter_options()
        except Exception:
            pass

        temp_dataset = self.app_context.orchestrator.scanner.set_data
        temp_metrics = self.app_context.orchestrator.scanner.retrieve_set_metrics()

        if self.is_import:
            try:
                text = self.app_context.root.clipboard_get()
                pool, error = parse_pool_text(temp_dataset, text)
                if error:
                    messagebox.showwarning("Import Failed", error, parent=self)
                    return
            except Exception as e:
                messagebox.showerror(
                    "Error", f"Failed to read clipboard: {e}", parent=self
                )
                return
        else:
            pool, error = generate_random_pool(temp_dataset)
            if error:
                messagebox.showwarning("Error", error, parent=self)
                return

        # Close the dialog and launch Sealed Studio
        self.destroy()
        SealedStudioWindow(
            self.app_context.root,
            self.app_context,
            self.app_context.configuration,
            pool,
            temp_metrics,
            draft_id=new_session_id(),
        )
