"""
Vault UI — encrypted password vault embedded in the Dashboard.

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
from typing import Optional

from src.storage.vault_crypto import VaultCrypto, VaultCryptoError
from src.models.local_auth import LocalAuth, AuthError

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class VaultEntry:
    id: str
    site: str
    username: str
    password: str
    notes: str
    created_at: int = 0
    updated_at: int = 0


# ─────────────────────────────────────────────────────────────────────────────
# Vault service — crypto + sync
# ─────────────────────────────────────────────────────────────────────────────

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
        """Initialize the vault: setup or unlock, then sync entries."""
        try:
            key_data = self.local_auth.vault_get_key()

            if key_data.get("exists"):
                self._crypto.unlock(
                    self._master_password,
                    key_data["kek_salt_b64"],
                    key_data["wrapped_dek_b64"],
                    key_data["dek_nonce_b64"],
                    key_data["dek_tag_b64"],
                )
                logger.info("[VAULT] Existing vault unlocked")
            else:
                setup_data = self._crypto.setup_new_vault(self._master_password)
                self.local_auth.vault_setup_key(setup_data)
                logger.info("[VAULT] New vault created and key stored on server")

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
            entry_data = {"site": site, "username": username, "password": password, "notes": notes}
            ct_b64, nonce_b64, tag_b64 = self._crypto.encrypt_entry(entry_data)

            result = self.local_auth.vault_create_entry({
                "encrypted_data_b64": ct_b64, "nonce_b64": nonce_b64, "tag_b64": tag_b64,
            })

            ei = result.get("entry", {})
            entry = VaultEntry(
                id=ei.get("id", ""), site=site, username=username,
                password=password, notes=notes,
                created_at=ei.get("created_at", 0), updated_at=ei.get("updated_at", 0),
            )
            self._entries.append(entry)
            logger.info("[VAULT] Entry added: %s", site)
            return entry

        except (VaultCryptoError, AuthError) as exc:
            logger.error("[VAULT] Failed to add entry: %s", exc)
            return None

    def update_entry(self, entry_id: str, site: str, username: str, password: str, notes: str) -> bool:
        """Encrypt and push an updated entry to the server."""
        try:
            entry_data = {"site": site, "username": username, "password": password, "notes": notes}
            ct_b64, nonce_b64, tag_b64 = self._crypto.encrypt_entry(entry_data)

            self.local_auth.vault_update_entry(entry_id, {
                "encrypted_data_b64": ct_b64, "nonce_b64": nonce_b64, "tag_b64": tag_b64,
            })

            for i, e in enumerate(self._entries):
                if e.id == entry_id:
                    self._entries[i] = VaultEntry(
                        entry_id, site, username, password, notes, e.created_at, e.updated_at,
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


# ─────────────────────────────────────────────────────────────────────────────
# VaultPage — inline page for the Dashboard
# ─────────────────────────────────────────────────────────────────────────────

class VaultPage(tk.Frame):
    """
    Embedded vault page that fits inside the Dashboard main_container.

    Same functionality as the old VaultWindow, but as a tk.Frame:
    - Treeview with Site, Username, Password(hidden), Notes, Actions
    - Toolbar: Add / Edit / Delete / Copy Password / Refresh
    - Real-time search filtering
    - Per-row reveal/hide toggle via Actions column click
    - Clipboard auto-clear after 30s
    """

    HIDDEN_PASSWORD = "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022"

    def __init__(
        self,
        master: tk.Misc,
        local_auth: LocalAuth,
        master_password: str,
    ) -> None:
        super().__init__(master, bg="white")

        self._local_auth = local_auth
        self._master_password = master_password
        self._revealed_ids: set[str] = set()
        self._entries_by_id: dict[str, VaultEntry] = {}
        self._service: VaultService | None = None

        self._build_ui()

        # Init in background so the frame renders first
        self.after(50, self._init_vault)

    # ── Build ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Badge
        badge = tk.Label(
            self, text="AES-256-GCM  \u2022  Zero-Knowledge  \u2022  Encriptado ponto-a-ponto",
            font=("Segoe UI", 9), bg="white", fg="#6c63ff",
        )
        badge.pack(anchor="w", pady=(0, 12))

        # Toolbar
        toolbar = tk.Frame(self, bg="white")
        toolbar.pack(fill="x", pady=(0, 10))

        btn_dark = {"bg": "#2C2F33", "fg": "white", "font": ("Segoe UI", 9, "bold"),
                    "relief": "flat", "cursor": "hand2", "padx": 14}
        btn_light = {"bg": "#E9ECEF", "fg": "#2C2F33", "font": ("Segoe UI", 9, "bold"),
                     "relief": "flat", "cursor": "hand2", "padx": 14}

        tk.Button(toolbar, text="ADICIONAR", command=self._on_add, **btn_dark).pack(side="left", ipady=8)
        tk.Button(toolbar, text="EDITAR", command=self._on_edit, **btn_dark).pack(side="left", padx=8, ipady=8)
        tk.Button(toolbar, text="COPIAR PASS", command=self._on_copy_password, **btn_light).pack(side="left", ipady=8)
        tk.Button(toolbar, text="APAGAR", command=self._on_delete, **btn_light).pack(side="left", padx=8, ipady=8)
        tk.Button(toolbar, text="ATUALIZAR", command=self._on_refresh, **btn_light).pack(side="left", ipady=8)

        # Search
        search_row = tk.Frame(self, bg="white")
        search_row.pack(fill="x", pady=(0, 10))

        tk.Label(search_row, text="Pesquisar:", font=("Segoe UI", 10),
                 bg="white", fg="#666").pack(side="left", padx=(0, 8))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._apply_filter())

        search_entry = tk.Entry(
            search_row, textvariable=self.search_var,
            font=("Segoe UI", 10), bg="#F8F9FA", fg="#444",
            insertbackground="#444", relief="flat",
            highlightthickness=1, highlightbackground="#E9ECEF",
            highlightcolor="#6c63ff",
        )
        search_entry.pack(side="left", fill="x", expand=True, ipady=6)

        # Table
        table_frame = tk.Frame(self, bg="white", highlightthickness=1, highlightbackground="#E9ECEF")
        table_frame.pack(fill="both", expand=True)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Vault.Treeview",
                        background="#FFFFFF", foreground="#444",
                        fieldbackground="#FFFFFF", rowheight=38,
                        font=("Segoe UI", 10))
        style.configure("Vault.Treeview.Heading",
                        font=("Segoe UI", 8, "bold"), background="#F8F9FA",
                        foreground="#999", relief="flat")
        style.map("Vault.Treeview",
                  background=[("selected", "#6c63ff")],
                  foreground=[("selected", "#ffffff")])

        columns = ("site", "username", "password", "notes", "actions")
        self.tree = ttk.Treeview(
            table_frame, columns=columns, show="headings",
            style="Vault.Treeview", selectmode="browse",
        )

        self.tree.heading("site", text="  SERVI\u00c7O")
        self.tree.heading("username", text="  UTILIZADOR / EMAIL")
        self.tree.heading("password", text="  PASSWORD")
        self.tree.heading("notes", text="  NOTAS")
        self.tree.heading("actions", text="  A\u00c7\u00c3O")

        self.tree.column("site", width=160, anchor="w")
        self.tree.column("username", width=200, anchor="w")
        self.tree.column("password", width=120, anchor="center")
        self.tree.column("notes", width=220, anchor="w")
        self.tree.column("actions", width=80, anchor="center")

        scroll = tk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.tree.bind("<Button-1>", self._tree_on_click)
        self.tree.bind("<Double-1>", lambda _: self._on_edit())

        # Status bar
        self._status = tk.Label(
            self, text="A inicializar o vault\u2026", font=("Segoe UI", 9),
            bg="white", fg="#999", anchor="w",
        )
        self._status.pack(fill="x", pady=(8, 0))

    # ── Init ─────────────────────────────────────────────────────────────────

    def _init_vault(self) -> None:
        """Initialize vault — unlock/setup and sync entries."""
        self._service = VaultService(self._local_auth, self._master_password)
        success, message = self._service.initialize()
        if not success:
            self._status.config(text=f"Erro: {message}", fg="#e74c3c")
            messagebox.showerror("Vault", message)
            return
        self._load_entries()
        count = len(self._entries_by_id)
        self._status.config(
            text=f"{count} {'entrada' if count == 1 else 'entradas'} \u2022 Encriptado \u2022 Sincronizado",
            fg="#22c55e",
        )

    # ── Data ─────────────────────────────────────────────────────────────────

    def _load_entries(self) -> None:
        if not self._service:
            return
        entries = self._service.list_entries()
        self._entries_by_id = {e.id: e for e in entries}
        self._apply_filter()

    def _apply_filter(self) -> None:
        query = self.search_var.get().strip().lower() if hasattr(self, "search_var") else ""

        for item in self.tree.get_children():
            self.tree.delete(item)

        for entry in self._entries_by_id.values():
            haystack = f"{entry.site} {entry.username} {entry.notes}".lower()
            if query and query not in haystack:
                continue

            show_pw = entry.id in self._revealed_ids
            pw_text = entry.password if show_pw else self.HIDDEN_PASSWORD
            action_text = "Ocultar" if show_pw else "Mostrar"

            self.tree.insert("", "end", iid=entry.id, values=(
                entry.site, entry.username, pw_text, entry.notes, action_text,
            ))

    def _get_selected_id(self) -> str | None:
        sel = self.tree.selection()
        return sel[0] if sel else None

    # ── Tree events ──────────────────────────────────────────────────────────

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

    # ── Entry dialog (Toplevel) ──────────────────────────────────────────────

    def _show_entry_dialog(
        self, title: str, initial: VaultEntry | None = None,
    ) -> tuple[str, str, str, str] | None:
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.geometry("420x440")
        dialog.configure(bg="white")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.resizable(False, False)

        # Centre on screen
        dialog.update_idletasks()
        sx = dialog.winfo_screenwidth()
        sy = dialog.winfo_screenheight()
        dialog.geometry(f"+{(sx - 420) // 2}+{(sy - 440) // 2}")

        pad = {"padx": 24}
        lbl_style = {"font": ("Segoe UI", 8, "bold"), "bg": "white", "fg": "#999"}
        ent_style = {"font": ("Segoe UI", 10), "bg": "#F8F9FA", "relief": "flat"}

        tk.Label(dialog, text=title, font=("Segoe UI", 14, "bold"),
                 bg="white", fg="#2C2F33").pack(anchor="w", **pad, pady=(20, 16))

        fields: dict[str, tk.Entry] = {}
        for label_text, key, show in [
            ("SERVI\u00c7O", "site", ""),
            ("UTILIZADOR / EMAIL", "username", ""),
            ("PASSWORD", "password", "\u25cf"),
            ("NOTAS", "notes", ""),
        ]:
            tk.Label(dialog, text=label_text, **lbl_style).pack(anchor="w", **pad)
            ent = tk.Entry(dialog, show=show, **ent_style)
            ent.pack(fill="x", **pad, pady=(4, 10), ipady=8)
            if initial:
                ent.insert(0, getattr(initial, key, ""))
            fields[key] = ent

        result: dict[str, tuple[str, str, str, str] | None] = {"value": None}

        def save() -> None:
            site = fields["site"].get().strip()
            username = fields["username"].get().strip()
            password = fields["password"].get().strip()
            notes = fields["notes"].get().strip()
            if not site or not username or not password:
                messagebox.showwarning("Aviso",
                    "Servi\u00e7o, utilizador e password s\u00e3o obrigat\u00f3rios.", parent=dialog)
                return
            result["value"] = (site, username, password, notes)
            dialog.destroy()

        btn_frame = tk.Frame(dialog, bg="white")
        btn_frame.pack(fill="x", padx=24, pady=(4, 20))

        tk.Button(btn_frame, text="GUARDAR", command=save,
                  bg="#2C2F33", fg="white", font=("Segoe UI", 9, "bold"),
                  relief="flat", cursor="hand2", padx=20).pack(side="right", ipady=6)
        tk.Button(btn_frame, text="CANCELAR", command=dialog.destroy,
                  bg="#E9ECEF", fg="#2C2F33", font=("Segoe UI", 9, "bold"),
                  relief="flat", cursor="hand2", padx=16).pack(side="right", padx=(0, 8), ipady=6)

        self.wait_window(dialog)
        return result["value"]

    # ── Actions ──────────────────────────────────────────────────────────────

    def _on_add(self) -> None:
        payload = self._show_entry_dialog("Nova Credencial")
        if not payload or not self._service:
            return
        site, username, password, notes = payload
        entry = self._service.add_entry(site, username, password, notes)
        if entry:
            self._entries_by_id[entry.id] = entry
            self._apply_filter()
            self._update_status()
        else:
            messagebox.showerror("Erro", "Falha ao guardar a entrada.")

    def _on_edit(self) -> None:
        entry_id = self._get_selected_id()
        if not entry_id:
            messagebox.showinfo("Editar", "Selecione uma entrada primeiro.")
            return
        current = self._entries_by_id.get(entry_id)
        if not current or not self._service:
            return
        payload = self._show_entry_dialog("Editar Credencial", initial=current)
        if not payload:
            return
        site, username, password, notes = payload
        ok = self._service.update_entry(entry_id, site, username, password, notes)
        if ok:
            self._entries_by_id[entry_id] = VaultEntry(
                entry_id, site, username, password, notes,
                current.created_at, current.updated_at,
            )
            self._apply_filter()
        else:
            messagebox.showerror("Erro", "Falha ao atualizar a entrada.")

    def _on_delete(self) -> None:
        entry_id = self._get_selected_id()
        if not entry_id:
            messagebox.showinfo("Apagar", "Selecione uma entrada primeiro.")
            return
        if not messagebox.askyesno("Apagar", "Deseja apagar esta entrada permanentemente?"):
            return
        if self._service and self._service.delete_entry(entry_id):
            self._entries_by_id.pop(entry_id, None)
            self._revealed_ids.discard(entry_id)
            self._apply_filter()
            self._update_status()
        else:
            messagebox.showerror("Erro", "Falha ao apagar a entrada.")

    def _on_copy_password(self) -> None:
        entry_id = self._get_selected_id()
        if not entry_id:
            messagebox.showinfo("Copiar", "Selecione uma entrada primeiro.")
            return
        pw = self._service.get_password(entry_id) if self._service else None
        if not pw:
            return
        self.clipboard_clear()
        self.clipboard_append(pw)
        self.update_idletasks()
        self.after(30_000, self._clear_clipboard)
        self._status.config(text="Password copiada! Clipboard limpo em 30s.", fg="#6c63ff")

    def _clear_clipboard(self) -> None:
        try:
            self.clipboard_clear()
            self.clipboard_append("")
        except tk.TclError:
            pass

    def _on_refresh(self) -> None:
        if not self._service:
            return
        try:
            self._service._sync_from_server()
            self._load_entries()
            self._update_status()
            self._status.config(text="Vault sincronizado com sucesso.", fg="#22c55e")
        except Exception as exc:
            messagebox.showerror("Refresh", f"Erro ao sincronizar: {exc}")

    def _update_status(self) -> None:
        count = len(self._entries_by_id)
        self._status.config(
            text=f"{count} {'entrada' if count == 1 else 'entradas'} \u2022 Encriptado \u2022 Sincronizado",
            fg="#22c55e",
        )

    # ── Cleanup ──────────────────────────────────────────────────────────────

    def destroy(self) -> None:
        """Override destroy to wipe crypto keys from memory."""
        if self._service:
            self._service.lock()
            self._service = None
        super().destroy()
