"""Dialog window for creating/editing vault entries."""

from __future__ import annotations

import secrets
import string
import tkinter as tk
from tkinter import messagebox
from typing import Callable, Any


class VaultEntryDialog(tk.Toplevel):
    """
    Toplevel dialog for vault entry input.

    Features:
    - Fields: Site/URL, Username, Password, Notes
    - Show/hide password toggle
    - Strong password generator (16 chars)
    - Password strength indicator (weak/medium/strong)
    - Save callback with entry data
    - Required validation for Site and Password
    - Dark theme
    """

    BG = "#1a1a2e"
    CARD = "#22243b"
    FG = "#f5f5f5"
    MUTED = "#aab0d6"
    ACCENT = "#e94560"

    def __init__(
        self,
        master: tk.Misc,
        on_save: Callable[[dict[str, Any]], None],
        initial_data: dict[str, Any] | None = None,
        title: str = "Vault Entry",
    ) -> None:
        super().__init__(master)
        self.on_save = on_save
        self.initial_data = initial_data or {}
        self._password_visible = False

        self.title(title)
        self.geometry("500x430")
        self.minsize(500, 430)
        self.configure(bg=self.BG)
        self.transient()
        self.grab_set()

        self.site_var = tk.StringVar(value=str(self.initial_data.get("site", "")))
        self.username_var = tk.StringVar(value=str(self.initial_data.get("username", "")))
        self.password_var = tk.StringVar(value=str(self.initial_data.get("password", "")))
        self.notes_var = tk.StringVar(value=str(self.initial_data.get("notes", "")))
        self.strength_var = tk.StringVar(value="Strength: weak")

        self._build_ui()
        self._bind_events()
        self._update_strength()

        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _build_ui(self) -> None:
        container = tk.Frame(self, bg=self.BG)
        container.pack(fill="both", expand=True, padx=18, pady=18)

        tk.Label(
            container,
            text="Vault Entry",
            bg=self.BG,
            fg=self.FG,
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w", pady=(0, 12))

        form = tk.Frame(container, bg=self.BG)
        form.pack(fill="both", expand=True)

        # Site / URL
        tk.Label(form, text="Site / URL", bg=self.BG, fg=self.MUTED, font=("Segoe UI", 10)).grid(
            row=0, column=0, sticky="w", pady=(0, 5)
        )
        tk.Entry(
            form,
            textvariable=self.site_var,
            bg=self.CARD,
            fg=self.FG,
            insertbackground=self.FG,
            relief="flat",
            font=("Segoe UI", 10),
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        # Username
        tk.Label(form, text="Username", bg=self.BG, fg=self.MUTED, font=("Segoe UI", 10)).grid(
            row=2, column=0, sticky="w", pady=(0, 5)
        )
        tk.Entry(
            form,
            textvariable=self.username_var,
            bg=self.CARD,
            fg=self.FG,
            insertbackground=self.FG,
            relief="flat",
            font=("Segoe UI", 10),
        ).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        # Password
        tk.Label(form, text="Password", bg=self.BG, fg=self.MUTED, font=("Segoe UI", 10)).grid(
            row=4, column=0, sticky="w", pady=(0, 5)
        )

        pwd_row = tk.Frame(form, bg=self.BG)
        pwd_row.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(0, 6))

        self.password_entry = tk.Entry(
            pwd_row,
            textvariable=self.password_var,
            show="*",
            bg=self.CARD,
            fg=self.FG,
            insertbackground=self.FG,
            relief="flat",
            font=("Segoe UI", 10),
        )
        self.password_entry.pack(side="left", fill="x", expand=True)

        self.toggle_btn = tk.Button(
            pwd_row,
            text="Show",
            command=self._toggle_password_visibility,
            bg="#2d314f",
            fg=self.FG,
            activebackground="#3a4066",
            activeforeground=self.FG,
            relief="flat",
            padx=10,
        )
        self.toggle_btn.pack(side="left", padx=(8, 0))

        self.generate_btn = tk.Button(
            pwd_row,
            text="Generate Password",
            command=self._generate_password,
            bg=self.ACCENT,
            fg="#ffffff",
            activebackground="#ff5d78",
            activeforeground="#ffffff",
            relief="flat",
            padx=10,
        )
        self.generate_btn.pack(side="left", padx=(8, 0))

        self.strength_label = tk.Label(
            form,
            textvariable=self.strength_var,
            bg=self.BG,
            fg="#f39c12",
            font=("Segoe UI", 9, "bold"),
        )
        self.strength_label.grid(row=6, column=0, sticky="w", pady=(0, 12))

        # Notes
        tk.Label(form, text="Notes", bg=self.BG, fg=self.MUTED, font=("Segoe UI", 10)).grid(
            row=7, column=0, sticky="w", pady=(0, 5)
        )
        tk.Entry(
            form,
            textvariable=self.notes_var,
            bg=self.CARD,
            fg=self.FG,
            insertbackground=self.FG,
            relief="flat",
            font=("Segoe UI", 10),
        ).grid(row=8, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        form.grid_columnconfigure(0, weight=1)

        # Footer buttons
        footer = tk.Frame(container, bg=self.BG)
        footer.pack(fill="x", pady=(12, 0))

        tk.Button(
            footer,
            text="Cancel",
            command=self._on_cancel,
            bg="#2d314f",
            fg=self.FG,
            activebackground="#3a4066",
            activeforeground=self.FG,
            relief="flat",
            padx=16,
            pady=8,
        ).pack(side="right", padx=(8, 0))

        tk.Button(
            footer,
            text="Save",
            command=self._on_save,
            bg=self.ACCENT,
            fg="#ffffff",
            activebackground="#ff5d78",
            activeforeground="#ffffff",
            relief="flat",
            padx=16,
            pady=8,
        ).pack(side="right")

    def _bind_events(self) -> None:
        self.password_var.trace_add("write", lambda *_: self._update_strength())
        self.bind("<Return>", lambda _e: self._on_save())
        self.bind("<Escape>", lambda _e: self._on_cancel())

    def _toggle_password_visibility(self) -> None:
        self._password_visible = not self._password_visible
        self.password_entry.configure(show="" if self._password_visible else "*")
        self.toggle_btn.configure(text="Hide" if self._password_visible else "Show")

    def _generate_password(self) -> None:
        upper = string.ascii_uppercase
        lower = string.ascii_lowercase
        digits = string.digits
        symbols = "!@#$%^&*()-_=+[]{};:,.?/"

        # Guarantee all groups are present
        chars = [
            secrets.choice(upper),
            secrets.choice(lower),
            secrets.choice(digits),
            secrets.choice(symbols),
        ]

        pool = upper + lower + digits + symbols
        while len(chars) < 16:
            chars.append(secrets.choice(pool))

        # Shuffle securely
        for i in range(len(chars) - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            chars[i], chars[j] = chars[j], chars[i]

        generated = "".join(chars)
        self.password_var.set(generated)

    def _password_score(self, password: str) -> int:
        score = 0
        if len(password) >= 12:
            score += 1
        if any(c.islower() for c in password) and any(c.isupper() for c in password):
            score += 1
        if any(c.isdigit() for c in password):
            score += 1
        if any(c in "!@#$%^&*()-_=+[]{};:,.?/" for c in password):
            score += 1
        if len(password) >= 14:
            score += 1
        return score

    def _update_strength(self) -> None:
        pwd = self.password_var.get()
        score = self._password_score(pwd)

        if score <= 2:
            self.strength_var.set("Strength: weak")
            self.strength_label.configure(fg="#ff7675")
        elif score == 3 or score == 4:
            self.strength_var.set("Strength: medium")
            self.strength_label.configure(fg="#f39c12")
        else:
            self.strength_var.set("Strength: strong")
            self.strength_label.configure(fg="#2ecc71")

    def _on_save(self) -> None:
        site = self.site_var.get().strip()
        username = self.username_var.get().strip()
        password = self.password_var.get().strip()
        notes = self.notes_var.get().strip()

        if not site:
            messagebox.showwarning("Validation", "Site/URL cannot be empty.", parent=self)
            return

        if not password:
            messagebox.showwarning("Validation", "Password cannot be empty.", parent=self)
            return

        payload = {
            "site": site,
            "username": username,
            "password": password,
            "notes": notes,
        }

        try:
            self.on_save(payload)
        except Exception as exc:
            messagebox.showerror("Save Error", f"Could not save entry: {exc}", parent=self)
            return

        self.destroy()

    def _on_cancel(self) -> None:
        self.destroy()
