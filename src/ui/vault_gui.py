"""
Vault UI window for password management.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from dataclasses import dataclass
from typing import Callable


@dataclass
class VaultEntry:
    id: int
    site: str
    username: str
    password: str
    notes: str


class VaultService:
    """Local stub service (fake data). Replace with real API/service later."""

    def __init__(self, access_token: str) -> None:
        self.access_token = access_token
        # Stub vazio — será substituído pelo vault encriptado (Phase 3)
        self._entries: list[VaultEntry] = []
        self._next_id = 1

    def list_entries(self) -> list[VaultEntry]:
        return list(self._entries)

    def add_entry(self, site: str, username: str, password: str, notes: str) -> VaultEntry:
        entry = VaultEntry(self._next_id, site, username, password, notes)
        self._next_id += 1
        self._entries.append(entry)
        return entry

    def update_entry(self, entry_id: int, site: str, username: str, password: str, notes: str) -> bool:
        for i, entry in enumerate(self._entries):
            if entry.id == entry_id:
                self._entries[i] = VaultEntry(entry_id, site, username, password, notes)
                return True
        return False

    def delete_entry(self, entry_id: int) -> bool:
        original = len(self._entries)
        self._entries = [e for e in self._entries if e.id != entry_id]
        return len(self._entries) < original

    def get_password(self, entry_id: int) -> str | None:
        for entry in self._entries:
            if entry.id == entry_id:
                return entry.password
        return None


class VaultWindow(tk.Toplevel):
    """
    Dark-themed vault window.

    Requirements covered:
    - Receives JWT `access_token`
    - Treeview columns: Site, Username, Password(hidden), Notes, Actions
    - Toolbar: Add/Edit/Delete/Copy Password/Lock
    - Real-time search filtering
    - Per-row reveal/hide toggle via Actions column click
    - Auto-lock after 5 minutes inactivity
    """

    LOCK_TIMEOUT_MS = 5 * 60 * 1000
    HIDDEN_PASSWORD = "••••••••"

    def __init__(
        self,
        master: tk.Misc,
        access_token: str,
        on_lock: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(master)
        self.access_token = access_token
        self.on_lock = on_lock

        self.service = VaultService(access_token)
        self._entries_by_id: dict[int, VaultEntry] = {}
        self._revealed_ids: set[int] = set()
        self._lock_after_id: str | None = None

        self.title("Vault")
        self.geometry("1000x620")
        self.configure(bg="#1a1a2e")
        self.minsize(860, 520)

        self._setup_style()
        self._build_ui()
        self._load_entries()
        self._bind_inactivity_events()
        self._reset_lock_timer()

        self.protocol("WM_DELETE_WINDOW", self._handle_lock)

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("Vault.Treeview",
                        background="#22243b",
                        foreground="#f5f5f5",
                        fieldbackground="#22243b",
                        rowheight=32,
                        bordercolor="#1a1a2e",
                        borderwidth=0)
        style.map("Vault.Treeview",
                  background=[("selected", "#e94560")],
                  foreground=[("selected", "#ffffff")])

        style.configure("Vault.Treeview.Heading",
                        background="#2d314f",
                        foreground="#f5f5f5",
                        relief="flat",
                        font=("Segoe UI", 10, "bold"))
        style.map("Vault.Treeview.Heading",
                  background=[("active", "#3a4066")])

        style.configure("Vault.TButton",
                        background="#e94560",
                        foreground="#ffffff",
                        borderwidth=0,
                        focusthickness=0,
                        focuscolor="#e94560",
                        padding=(10, 6))
        style.map("Vault.TButton",
                  background=[("active", "#ff5d78")])

    def _build_ui(self) -> None:
        self.container = tk.Frame(self, bg="#1a1a2e")
        self.container.pack(fill="both", expand=True, padx=16, pady=16)

        title = tk.Label(self.container,
                         text="Password Vault",
                         bg="#1a1a2e",
                         fg="#ffffff",
                         font=("Segoe UI", 18, "bold"))
        title.pack(anchor="w", pady=(0, 12))

        self._build_toolbar()
        self._build_search()
        self._build_table()

    def _build_toolbar(self) -> None:
        toolbar = tk.Frame(self.container, bg="#1a1a2e")
        toolbar.pack(fill="x", pady=(0, 10))

        ttk.Button(toolbar, text="Add Entry", style="Vault.TButton", command=self._on_add).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="Edit Entry", style="Vault.TButton", command=self._on_edit).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="Delete Entry", style="Vault.TButton", command=self._on_delete).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="Copy Password", style="Vault.TButton", command=self._on_copy_password).pack(side="left", padx=(0, 8))

        lock_btn = ttk.Button(toolbar, text="Lock (logout)", style="Vault.TButton", command=self._handle_lock)
        lock_btn.pack(side="right")

    def _build_search(self) -> None:
        row = tk.Frame(self.container, bg="#1a1a2e")
        row.pack(fill="x", pady=(0, 10))

        tk.Label(row,
                 text="Search:",
                 bg="#1a1a2e",
                 fg="#c7c9d9",
                 font=("Segoe UI", 10)).pack(side="left", padx=(0, 8))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._apply_filter())

        entry = tk.Entry(row,
                         textvariable=self.search_var,
                         bg="#22243b",
                         fg="#f5f5f5",
                         insertbackground="#f5f5f5",
                         relief="flat",
                         font=("Segoe UI", 10))
        entry.pack(side="left", fill="x", expand=True)

    def _build_table(self) -> None:
        table_frame = tk.Frame(self.container, bg="#1a1a2e")
        table_frame.pack(fill="both", expand=True)

        columns = ("site", "username", "password", "notes", "actions")
        self.tree = ttk.Treeview(table_frame,
                                 columns=columns,
                                 show="headings",
                                 style="Vault.Treeview",
                                 selectmode="browse")

        self.tree.heading("site", text="Site")
        self.tree.heading("username", text="Username")
        self.tree.heading("password", text="Password")
        self.tree.heading("notes", text="Notes")
        self.tree.heading("actions", text="Actions")

        self.tree.column("site", width=180, anchor="w")
        self.tree.column("username", width=180, anchor="w")
        self.tree.column("password", width=140, anchor="center")
        self.tree.column("notes", width=320, anchor="w")
        self.tree.column("actions", width=120, anchor="center")

        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)

        self.tree.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", self._tree_on_double_click)
        self.tree.bind("<Button-1>", self._tree_on_click)

    def _load_entries(self) -> None:
        entries = self.service.list_entries()
        self._entries_by_id = {entry.id: entry for entry in entries}
        self._apply_filter()

    def _apply_filter(self) -> None:
        query = self.search_var.get().strip().lower() if hasattr(self, "search_var") else ""

        for item in self.tree.get_children():
            self.tree.delete(item)

        for entry in self._entries_by_id.values():
            haystack = f"{entry.site} {entry.username} {entry.notes}".lower()
            if query and query not in haystack:
                continue

            show_password = entry.id in self._revealed_ids
            password_text = entry.password if show_password else self.HIDDEN_PASSWORD
            action_text = "Hide" if show_password else "Reveal"

            self.tree.insert("", "end", iid=str(entry.id), values=(
                entry.site,
                entry.username,
                password_text,
                entry.notes,
                action_text,
            ))

    def _get_selected_id(self) -> int | None:
        selected = self.tree.selection()
        if not selected:
            return None
        try:
            return int(selected[0])
        except ValueError:
            return None

    def _tree_on_click(self, event: tk.Event) -> None:
        region = self.tree.identify("region", event.x, event.y)
        column = self.tree.identify_column(event.x)
        row = self.tree.identify_row(event.y)

        if region == "cell" and column == "#5" and row:
            entry_id = int(row)
            if entry_id in self._revealed_ids:
                self._revealed_ids.remove(entry_id)
            else:
                self._revealed_ids.add(entry_id)
            self._apply_filter()

    def _tree_on_double_click(self, _event: tk.Event) -> None:
        self._on_edit()

    def _show_entry_dialog(self, title: str, initial: VaultEntry | None = None) -> tuple[str, str, str, str] | None:
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.geometry("420x320")
        dialog.configure(bg="#1a1a2e")
        dialog.transient(self)
        dialog.grab_set()

        fields = {
            "Site": tk.StringVar(value=initial.site if initial else ""),
            "Username": tk.StringVar(value=initial.username if initial else ""),
            "Password": tk.StringVar(value=initial.password if initial else ""),
            "Notes": tk.StringVar(value=initial.notes if initial else ""),
        }

        row = 0
        for label, var in fields.items():
            tk.Label(dialog, text=label, bg="#1a1a2e", fg="#ffffff", font=("Segoe UI", 10)).grid(
                row=row, column=0, sticky="w", padx=16, pady=(14 if row == 0 else 8, 2)
            )
            show = "*" if label == "Password" else ""
            tk.Entry(dialog,
                     textvariable=var,
                     show=show,
                     bg="#22243b",
                     fg="#f5f5f5",
                     insertbackground="#f5f5f5",
                     relief="flat").grid(
                row=row + 1, column=0, sticky="ew", padx=16, pady=(0, 4)
            )
            row += 2

        dialog.grid_columnconfigure(0, weight=1)

        result: dict[str, tuple[str, str, str, str] | None] = {"value": None}

        def save() -> None:
            site = fields["Site"].get().strip()
            username = fields["Username"].get().strip()
            password = fields["Password"].get().strip()
            notes = fields["Notes"].get().strip()

            if not site or not username or not password:
                messagebox.showwarning("Validation", "Site, Username and Password are required.", parent=dialog)
                return
            result["value"] = (site, username, password, notes)
            dialog.destroy()

        btns = tk.Frame(dialog, bg="#1a1a2e")
        btns.grid(row=row + 1, column=0, sticky="e", padx=16, pady=14)

        tk.Button(btns, text="Cancel", command=dialog.destroy, bg="#2d314f", fg="#ffffff", relief="flat").pack(side="right", padx=(8, 0))
        tk.Button(btns, text="Save", command=save, bg="#e94560", fg="#ffffff", relief="flat").pack(side="right")

        self.wait_window(dialog)
        return result["value"]

    def _on_add(self) -> None:
        payload = self._show_entry_dialog("Add Entry")
        if not payload:
            return

        site, username, password, notes = payload
        entry = self.service.add_entry(site, username, password, notes)
        self._entries_by_id[entry.id] = entry
        self._apply_filter()

    def _on_edit(self) -> None:
        entry_id = self._get_selected_id()
        if entry_id is None:
            messagebox.showinfo("Edit Entry", "Select an entry first.")
            return

        current = self._entries_by_id.get(entry_id)
        if not current:
            return

        payload = self._show_entry_dialog("Edit Entry", initial=current)
        if not payload:
            return

        site, username, password, notes = payload
        ok = self.service.update_entry(entry_id, site, username, password, notes)
        if ok:
            self._entries_by_id[entry_id] = VaultEntry(entry_id, site, username, password, notes)
            self._apply_filter()

    def _on_delete(self) -> None:
        entry_id = self._get_selected_id()
        if entry_id is None:
            messagebox.showinfo("Delete Entry", "Select an entry first.")
            return

        if not messagebox.askyesno("Delete Entry", "Delete selected entry?"):
            return

        ok = self.service.delete_entry(entry_id)
        if ok:
            self._entries_by_id.pop(entry_id, None)
            self._revealed_ids.discard(entry_id)
            self._apply_filter()

    def _on_copy_password(self) -> None:
        entry_id = self._get_selected_id()
        if entry_id is None:
            messagebox.showinfo("Copy Password", "Select an entry first.")
            return

        password = self.service.get_password(entry_id)
        if not password:
            messagebox.showwarning("Copy Password", "Could not get password.")
            return

        self.clipboard_clear()
        self.clipboard_append(password)
        self.update_idletasks()
        messagebox.showinfo("Copy Password", "Password copied to clipboard.")

    def _bind_inactivity_events(self) -> None:
        for sequence in ("<Any-KeyPress>", "<Any-Button>", "<Motion>"):
            self.bind_all(sequence, self._on_activity, add="+")

    def _on_activity(self, _event: tk.Event | None = None) -> None:
        self._reset_lock_timer()

    def _reset_lock_timer(self) -> None:
        if self._lock_after_id is not None:
            self.after_cancel(self._lock_after_id)
        self._lock_after_id = self.after(self.LOCK_TIMEOUT_MS, self._handle_lock)

    def _handle_lock(self) -> None:
        if self._lock_after_id is not None:
            try:
                self.after_cancel(self._lock_after_id)
            except Exception:
                pass
            self._lock_after_id = None

        # Unbind inactivity listeners set by this window.
        for sequence in ("<Any-KeyPress>", "<Any-Button>", "<Motion>"):
            self.unbind_all(sequence)

        if callable(self.on_lock):
            try:
                self.on_lock()
            except Exception:
                pass

        self.destroy()
