"""
Vault UI window — encrypted password vault with server sync.

Phase 3 implementation: every entry is encrypted client-side with
AES-256-GCM before being sent to the server.  The server stores only
opaque ciphertext (zero-knowledge architecture).

Architecture:
    Master Password → Argon2id → KEK
    DEK (random) ← wrapped with KEK → stored on server
    Each entry: plaintext → AES-256-GCM(DEK) → ciphertext → server
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk, messagebox
from dataclasses import dataclass
from typing import Callable, Optional, Any

from src.storage.vault_crypto import VaultCrypto, VaultCryptoError
from src.models.local_auth import LocalAuth, AuthError

logger = logging.getLogger(__name__)


@dataclass
class VaultEntry:
    id: str
    site: str
    username: str
    password: str
    notes: str
    created_at: int = 0
    updated_at: int = 0


class VaultService:
    """
    Encrypted vault service — real implementation.

    All entries are encrypted with AES-256-GCM before being stored
    on the server.  The server never sees plaintext.
    """

    def __init__(self, local_auth: LocalAuth, master_password: str) -> None:
        self.local_auth = local_auth
        self._crypto = VaultCrypto()
        self._entries: list[VaultEntry] = []
        self._master_password = master_password
        self._is_ready = False

    def initialize(self) -> tuple[bool, str]:
        """
        Initialize the vault: setup or unlock, then sync entries.

        Returns:
            (success, message)
        """
        try:
            # Step 1: Check if vault key exists on server
            key_data = self.local_auth.vault_get_key()

            if key_data.get("exists"):
                # Returning user — unlock with master password
                self._crypto.unlock(
                    self._master_password,
                    key_data["kek_salt_b64"],
                    key_data["wrapped_dek_b64"],
                    key_data["dek_nonce_b64"],
                    key_data["dek_tag_b64"],
                )
                logger.info("[VAULT] Existing vault unlocked")
            else:
                # First-time setup — create new vault
                setup_data = self._crypto.setup_new_vault(self._master_password)
                self.local_auth.vault_setup_key(setup_data)
                logger.info("[VAULT] New vault created and key stored on server")

            # Step 2: Sync entries from server
            self._sync_from_server()
            self._is_ready = True
            return True, "Vault desbloqueado com sucesso."

        except VaultCryptoError as exc:
            logger.warning("[VAULT] Crypto error: %s", exc)
            return False, str(exc)
        except AuthError as exc:
            logger.warning("[VAULT] API error: %s", exc)
            return False, f"Erro de ligação ao servidor: {exc}"
        except Exception as exc:
            logger.error("[VAULT] Unexpected error: %s", exc, exc_info=True)
            return False, f"Erro inesperado: {exc}"

    def _sync_from_server(self) -> None:
        """Pull all encrypted entries from server and decrypt them."""
        data = self.local_auth.vault_list_entries()
        entries_raw = data.get("entries", [])

        self._entries.clear()
        for raw in entries_raw:
            try:
                decrypted = self._crypto.decrypt_entry(
                    raw["encrypted_data_b64"],
                    raw["nonce_b64"],
                    raw["tag_b64"],
                )
                self._entries.append(VaultEntry(
                    id=raw["id"],
                    site=decrypted.get("site", ""),
                    username=decrypted.get("username", ""),
                    password=decrypted.get("password", ""),
                    notes=decrypted.get("notes", ""),
                    created_at=raw.get("created_at", 0),
                    updated_at=raw.get("updated_at", 0),
                ))
            except VaultCryptoError:
                logger.warning("[VAULT] Failed to decrypt entry %s — skipping", raw.get("id"))

        logger.info("[VAULT] Synced %d entries from server", len(self._entries))

    def list_entries(self) -> list[VaultEntry]:
        return list(self._entries)

    def add_entry(self, site: str, username: str, password: str, notes: str) -> Optional[VaultEntry]:
        """Encrypt and push a new entry to the server."""
        try:
            entry_data = {
                "site": site,
                "username": username,
                "password": password,
                "notes": notes,
            }
            ct_b64, nonce_b64, tag_b64 = self._crypto.encrypt_entry(entry_data)

            result = self.local_auth.vault_create_entry({
                "encrypted_data_b64": ct_b64,
                "nonce_b64": nonce_b64,
                "tag_b64": tag_b64,
            })

            entry_item = result.get("entry", {})
            entry = VaultEntry(
                id=entry_item.get("id", ""),
                site=site,
                username=username,
                password=password,
                notes=notes,
                created_at=entry_item.get("created_at", 0),
                updated_at=entry_item.get("updated_at", 0),
            )
            self._entries.append(entry)
            logger.info("[VAULT] Entry added: %s", site)
            return entry

        except (VaultCryptoError, AuthError) as exc:
            logger.error("[VAULT] Failed to add entry: %s", exc)
            return None

    def update_entry(
        self, entry_id: str, site: str, username: str, password: str, notes: str,
    ) -> bool:
        """Encrypt and push an updated entry to the server."""
        try:
            entry_data = {
                "site": site,
                "username": username,
                "password": password,
                "notes": notes,
            }
            ct_b64, nonce_b64, tag_b64 = self._crypto.encrypt_entry(entry_data)

            self.local_auth.vault_update_entry(entry_id, {
                "encrypted_data_b64": ct_b64,
                "nonce_b64": nonce_b64,
                "tag_b64": tag_b64,
            })

            for i, e in enumerate(self._entries):
                if e.id == entry_id:
                    self._entries[i] = VaultEntry(
                        entry_id, site, username, password, notes,
                        e.created_at, e.updated_at,
                    )
                    break

            logger.info("[VAULT] Entry updated: %s", site)
            return True

        except (VaultCryptoError, AuthError) as exc:
            logger.error("[VAULT] Failed to update entry: %s", exc)
            return False

    def delete_entry(self, entry_id: str) -> bool:
        """Delete an entry from the server."""
        try:
            self.local_auth.vault_delete_entry(entry_id)
            self._entries = [e for e in self._entries if e.id != entry_id]
            logger.info("[VAULT] Entry deleted: %s", entry_id)
            return True
        except AuthError as exc:
            logger.error("[VAULT] Failed to delete entry: %s", exc)
            return False

    def get_password(self, entry_id: str) -> Optional[str]:
        for entry in self._entries:
            if entry.id == entry_id:
                return entry.password
        return None

    def lock(self) -> None:
        """Wipe keys and entries from memory."""
        self._crypto.lock()
        self._entries.clear()
        self._master_password = ""
        self._is_ready = False
        logger.info("[VAULT] Vault locked — keys wiped from memory")


class VaultWindow(tk.Toplevel):
    """
    Dark-themed vault window with encrypted storage.

    Requirements covered:
    - Receives LocalAuth + master_password for encryption
    - Treeview columns: Site, Username, Password(hidden), Notes, Actions
    - Toolbar: Add/Edit/Delete/Copy Password/Refresh/Lock
    - Real-time search filtering
    - Per-row reveal/hide toggle via Actions column click
    - Auto-lock after 5 minutes inactivity
    - All data encrypted client-side (AES-256-GCM)
    """

    LOCK_TIMEOUT_MS = 5 * 60 * 1000
    HIDDEN_PASSWORD = "••••••••"

    def __init__(
        self,
        master: tk.Misc,
        local_auth: LocalAuth,
        master_password: str,
        on_lock: Callable[[], None] | None = None,
        *,
        access_token: str = "",
    ) -> None:
        super().__init__(master)
        self.on_lock = on_lock
        self._revealed_ids: set[str] = set()
        self._lock_after_id: str | None = None
        self._entries_by_id: dict[str, VaultEntry] = {}

        self.title("Vault")
        self.geometry("1000x620")
        self.configure(bg="#1a1a2e")
        self.minsize(860, 520)

        self._setup_style()
        self._build_ui()

        # Initialize encrypted vault service
        self.service = VaultService(local_auth, master_password)
        self._init_vault()

        self._bind_inactivity_events()
        self._reset_lock_timer()
        self.protocol("WM_DELETE_WINDOW", self._handle_lock)

    def _init_vault(self) -> None:
        """Initialize vault — unlock/setup and sync entries."""
        success, message = self.service.initialize()
        if not success:
            messagebox.showerror("Vault Error", message, parent=self)
            self.after(100, self.destroy)
            return
        self._load_entries()

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

        title_row = tk.Frame(self.container, bg="#1a1a2e")
        title_row.pack(fill="x", pady=(0, 12))

        tk.Label(title_row, text="🔐 Password Vault",
                 bg="#1a1a2e", fg="#ffffff",
                 font=("Segoe UI", 18, "bold")).pack(side="left")

        tk.Label(title_row, text="AES-256-GCM • Zero-Knowledge",
                 bg="#1a1a2e", fg="#6c63ff",
                 font=("Segoe UI", 9)).pack(side="left", padx=(12, 0), pady=(6, 0))

        self._build_toolbar()
        self._build_search()
        self._build_table()

    def _build_toolbar(self) -> None:
        toolbar = tk.Frame(self.container, bg="#1a1a2e")
        toolbar.pack(fill="x", pady=(0, 10))

        ttk.Button(toolbar, text="Add Entry", style="Vault.TButton",
                   command=self._on_add).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="Edit Entry", style="Vault.TButton",
                   command=self._on_edit).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="Delete Entry", style="Vault.TButton",
                   command=self._on_delete).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="Copy Password", style="Vault.TButton",
                   command=self._on_copy_password).pack(side="left", padx=(0, 8))
        ttk.Button(toolbar, text="🔄 Refresh", style="Vault.TButton",
                   command=self._on_refresh).pack(side="left", padx=(0, 8))

        ttk.Button(toolbar, text="Lock (logout)", style="Vault.TButton",
                   command=self._handle_lock).pack(side="right")

    def _build_search(self) -> None:
        row = tk.Frame(self.container, bg="#1a1a2e")
        row.pack(fill="x", pady=(0, 10))

        tk.Label(row, text="Search:", bg="#1a1a2e", fg="#c7c9d9",
                 font=("Segoe UI", 10)).pack(side="left", padx=(0, 8))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._apply_filter())

        tk.Entry(row, textvariable=self.search_var,
                 bg="#22243b", fg="#f5f5f5",
                 insertbackground="#f5f5f5", relief="flat",
                 font=("Segoe UI", 10)).pack(side="left", fill="x", expand=True)

    def _build_table(self) -> None:
        table_frame = tk.Frame(self.container, bg="#1a1a2e")
        table_frame.pack(fill="both", expand=True)

        columns = ("site", "username", "password", "notes", "actions")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings",
                                 style="Vault.Treeview", selectmode="browse")

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

            self.tree.insert("", "end", iid=entry.id, values=(
                entry.site, entry.username, password_text, entry.notes, action_text,
            ))

    def _get_selected_id(self) -> str | None:
        selected = self.tree.selection()
        return selected[0] if selected else None

    def _tree_on_click(self, event: tk.Event) -> None:
        region = self.tree.identify("region", event.x, event.y)
        column = self.tree.identify_column(event.x)
        row = self.tree.identify_row(event.y)

        if region == "cell" and column == "#5" and row:
            if row in self._revealed_ids:
                self._revealed_ids.remove(row)
            else:
                self._revealed_ids.add(row)
            self._apply_filter()

    def _tree_on_double_click(self, _event: tk.Event) -> None:
        self._on_edit()

    def _show_entry_dialog(
        self, title: str, initial: VaultEntry | None = None,
    ) -> tuple[str, str, str, str] | None:
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
            tk.Label(dialog, text=label, bg="#1a1a2e", fg="#ffffff",
                     font=("Segoe UI", 10)).grid(
                row=row, column=0, sticky="w", padx=16,
                pady=(14 if row == 0 else 8, 2),
            )
            show = "*" if label == "Password" else ""
            tk.Entry(dialog, textvariable=var, show=show,
                     bg="#22243b", fg="#f5f5f5",
                     insertbackground="#f5f5f5", relief="flat").grid(
                row=row + 1, column=0, sticky="ew", padx=16, pady=(0, 4),
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
                messagebox.showwarning(
                    "Validation",
                    "Site, Username and Password are required.",
                    parent=dialog,
                )
                return
            result["value"] = (site, username, password, notes)
            dialog.destroy()

        btns = tk.Frame(dialog, bg="#1a1a2e")
        btns.grid(row=row + 1, column=0, sticky="e", padx=16, pady=14)

        tk.Button(btns, text="Cancel", command=dialog.destroy,
                  bg="#2d314f", fg="#ffffff", relief="flat").pack(side="right", padx=(8, 0))
        tk.Button(btns, text="Save", command=save,
                  bg="#e94560", fg="#ffffff", relief="flat").pack(side="right")

        self.wait_window(dialog)
        return result["value"]

    def _on_add(self) -> None:
        payload = self._show_entry_dialog("Add Entry")
        if not payload:
            return
        site, username, password, notes = payload
        entry = self.service.add_entry(site, username, password, notes)
        if entry:
            self._entries_by_id[entry.id] = entry
            self._apply_filter()
        else:
            messagebox.showerror("Error", "Failed to save entry.", parent=self)

    def _on_edit(self) -> None:
        entry_id = self._get_selected_id()
        if entry_id is None:
            messagebox.showinfo("Edit Entry", "Select an entry first.", parent=self)
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
            self._entries_by_id[entry_id] = VaultEntry(
                entry_id, site, username, password, notes,
                current.created_at, current.updated_at,
            )
            self._apply_filter()
        else:
            messagebox.showerror("Error", "Failed to update entry.", parent=self)

    def _on_delete(self) -> None:
        entry_id = self._get_selected_id()
        if entry_id is None:
            messagebox.showinfo("Delete Entry", "Select an entry first.", parent=self)
            return
        if not messagebox.askyesno("Delete Entry", "Delete selected entry?", parent=self):
            return
        ok = self.service.delete_entry(entry_id)
        if ok:
            self._entries_by_id.pop(entry_id, None)
            self._revealed_ids.discard(entry_id)
            self._apply_filter()
        else:
            messagebox.showerror("Error", "Failed to delete entry.", parent=self)

    def _on_copy_password(self) -> None:
        entry_id = self._get_selected_id()
        if entry_id is None:
            messagebox.showinfo("Copy Password", "Select an entry first.", parent=self)
            return
        password = self.service.get_password(entry_id)
        if not password:
            messagebox.showwarning("Copy Password", "Could not get password.", parent=self)
            return
        self.clipboard_clear()
        self.clipboard_append(password)
        self.update_idletasks()
        self.after(30_000, self._clear_clipboard)
        messagebox.showinfo(
            "Copy Password",
            "Password copiada!\nClipboard será limpo em 30s.",
            parent=self,
        )

    def _clear_clipboard(self) -> None:
        """Security: clear clipboard after timeout."""
        try:
            self.clipboard_clear()
            self.clipboard_append("")
        except tk.TclError:
            pass

    def _on_refresh(self) -> None:
        """Re-sync entries from server."""
        try:
            self.service._sync_from_server()
            self._load_entries()
            messagebox.showinfo("Refresh", "Vault sincronizado com sucesso.", parent=self)
        except Exception as exc:
            messagebox.showerror("Refresh", f"Erro ao sincronizar: {exc}", parent=self)

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

        for sequence in ("<Any-KeyPress>", "<Any-Button>", "<Motion>"):
            self.unbind_all(sequence)

        # Wipe encryption keys from memory
        if hasattr(self, "service"):
            self.service.lock()

        if callable(self.on_lock):
            try:
                self.on_lock()
            except Exception:
                pass

        self.destroy()
