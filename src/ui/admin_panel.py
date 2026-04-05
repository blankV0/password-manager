"""
Painel de Administração — apenas acessível a utilizadores com role=admin.

Funcionalidades:
  • Listar utilizadores (email, role, active)
  • Ativar / desativar contas
  • Reset de password
  • Consultar logs de autenticação
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import messagebox

from src.models.local_auth import LocalAuth
from src.ui.settings_page import get_theme_colors, _load_prefs


class AdminPanel(tk.Frame):
    """Painel de administração embebido no main_container do Dashboard."""

    def __init__(
        self,
        master: tk.Widget,
        local_auth: LocalAuth,
    ):
        self.local_auth = local_auth
        prefs = _load_prefs()
        self.c = get_theme_colors(prefs.get("theme", "light"))
        super().__init__(master, bg=self.c["bg"])

        if not self.local_auth.is_admin():
            self._show_access_denied()
            return

        self._build_ui()

    # ── Acesso negado ─────────────────────────────────────────────────

    def _show_access_denied(self) -> None:
        frame = tk.Frame(self, bg=self.c["bg"])
        frame.pack(expand=True)
        tk.Label(
            frame, text="🔒", font=("Segoe UI", 48),
            bg=self.c["bg"], fg=self.c["muted"],
        ).pack(pady=(0, 8))
        tk.Label(
            frame, text="Acesso Restrito",
            font=("Segoe UI", 18, "bold"),
            bg=self.c["bg"], fg=self.c["text"],
        ).pack()
        tk.Label(
            frame, text="Esta página é exclusiva para administradores.",
            font=("Segoe UI", 11),
            bg=self.c["bg"], fg=self.c["muted"],
        ).pack(pady=(4, 0))

    # ── UI principal ──────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self._selected_row = None  # (row_frame, original_bg)

        # ── Barra de acções ──────────────────────────────────────────
        actions = tk.Frame(self, bg=self.c["bg"])
        actions.pack(fill="x", pady=(0, 12))

        # Linha 1: campos
        fields = tk.Frame(actions, bg=self.c["bg"])
        fields.pack(fill="x")

        # Email alvo
        email_frame = tk.Frame(fields, bg=self.c["bg"])
        email_frame.pack(side="left", padx=(0, 12))
        tk.Label(
            email_frame, text="Email do utilizador",
            font=("Segoe UI", 10, "bold"),
            bg=self.c["bg"], fg=self.c["text"],
        ).pack(anchor="w")
        self.target_email = tk.Entry(
            email_frame, width=32, font=("Segoe UI", 11),
            relief="flat", highlightthickness=1,
            highlightbackground=self.c["border"],
            highlightcolor=self.c["accent"],
            bg=self.c["input_bg"], fg=self.c["text"],
            insertbackground=self.c["text"],
        )
        self.target_email.pack(pady=(4, 0), ipady=4)

        # Nova password
        pw_frame = tk.Frame(fields, bg=self.c["bg"])
        pw_frame.pack(side="left", padx=(0, 12))
        tk.Label(
            pw_frame, text="Nova password (reset)",
            font=("Segoe UI", 10, "bold"),
            bg=self.c["bg"], fg=self.c["text"],
        ).pack(anchor="w")
        self.new_password = tk.Entry(
            pw_frame, width=24, font=("Segoe UI", 11), show="•",
            relief="flat", highlightthickness=1,
            highlightbackground=self.c["border"],
            highlightcolor=self.c["accent"],
            bg=self.c["input_bg"], fg=self.c["text"],
            insertbackground=self.c["text"],
        )
        self.new_password.pack(pady=(4, 0), ipady=4)

        # Linha 2: botões
        btn_bar = tk.Frame(actions, bg=self.c["bg"])
        btn_bar.pack(fill="x", pady=(10, 0))

        buttons = [
            ("🔄  Atualizar lista", self.c["accent"], self._refresh_users),
            ("✅  Ativar", self.c["success"], lambda: self._set_active(True)),
            ("🚫  Desativar", self.c["danger"], lambda: self._set_active(False)),
            ("X  Eliminar", "#dc2626", self._delete_user),
            ("*  Reset password", "#f59e0b", self._reset_password),
            ("📋  Ver logs", self.c["border"], self._show_logs),
        ]
        for text, bg_color, cmd in buttons:
            fg = "white" if bg_color not in (self.c["border"],) else self.c["text"]
            btn = tk.Label(
                btn_bar, text=text,
                font=("Segoe UI", 10, "bold"),
                bg=bg_color, fg=fg,
                padx=14, pady=6, cursor="hand2",
            )
            btn.pack(side="left", padx=(0, 6))
            _bg = bg_color  # capture
            btn.bind("<Button-1>", lambda e, c=cmd: c())

        # ── Tabela de utilizadores ───────────────────────────────────
        table_header = tk.Frame(self, bg=self.c["bg"])
        table_header.pack(fill="x", pady=(8, 0))
        tk.Label(
            table_header, text="Utilizadores registados",
            font=("Segoe UI", 12, "bold"),
            bg=self.c["bg"], fg=self.c["text"],
        ).pack(side="left")
        self.count_label = tk.Label(
            table_header, text="",
            font=("Segoe UI", 10),
            bg=self.c["bg"], fg=self.c["muted"],
        )
        self.count_label.pack(side="left", padx=(8, 0))

        # Card com texto
        users_card = tk.Frame(
            self, bg=self.c["card"],
            highlightthickness=1,
            highlightbackground=self.c["border"],
        )
        users_card.pack(fill="both", expand=True, pady=(6, 0))

        # Headers
        header_frame = tk.Frame(users_card, bg=self.c["border"])
        header_frame.pack(fill="x")
        for col, w in [("Email", 30), ("Username", 16), ("Role", 10), ("Ativo", 8), ("Criado", 20)]:
            tk.Label(
                header_frame, text=col,
                font=("Segoe UI", 9, "bold"),
                bg=self.c["border"], fg=self.c["text"],
                width=w, anchor="w", padx=8, pady=4,
            ).pack(side="left")

        # Scrollable user rows
        canvas = tk.Canvas(users_card, bg=self.c["card"], highlightthickness=0)
        sb = tk.Scrollbar(users_card, orient="vertical", command=canvas.yview)
        self._users_inner = tk.Frame(canvas, bg=self.c["card"])
        self._users_inner.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self._users_inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Carregar utilizadores
        self._refresh_users()

    # ── Acções ────────────────────────────────────────────────────────

    def _refresh_users(self) -> None:
        success, message, users = self.local_auth.admin_list_users()
        if not success:
            messagebox.showerror("Erro", message)
            return

        # Limpar linhas anteriores
        for w in self._users_inner.winfo_children():
            w.destroy()

        users = users or []
        self.count_label.config(text=f"({len(users)} utilizadores)")

        for i, user in enumerate(users):
            bg = self.c["card"] if i % 2 == 0 else self.c["bg"]
            row = tk.Frame(self._users_inner, bg=bg)
            row.pack(fill="x")

            email = user.get("email", "—")
            username = user.get("username", "—")
            role = user.get("role", "user")
            active = user.get("active", True)
            created = user.get("created_at", "—")
            if isinstance(created, str) and "T" in created:
                created = created.split("T")[0]

            # Cores de destaque
            role_fg = self.c["accent"] if role == "admin" else self.c["muted"]
            active_text = "✓ Sim" if active else "✗ Não"
            active_fg = self.c["success"] if active else self.c["danger"]

            for text, w, fg in [
                (email, 30, self.c["text"]),
                (username, 16, self.c["text"]),
                (role, 10, role_fg),
                (active_text, 8, active_fg),
                (created, 20, self.c["muted"]),
            ]:
                tk.Label(
                    row, text=text,
                    font=("Segoe UI", 10),
                    bg=bg, fg=fg,
                    width=w, anchor="w", padx=8, pady=6,
                ).pack(side="left")

            # Clique na linha preenche o email
            row.bind("<Button-1>", lambda e, em=email, r=row, ob=bg: self._select_user(em, r, ob))
            for child in row.winfo_children():
                child.bind("<Button-1>", lambda e, em=email, r=row, ob=bg: self._select_user(em, r, ob))

    def _select_user(self, email: str, row: tk.Frame | None = None, orig_bg: str | None = None) -> None:
        """Preenche o campo de email e destaca a linha selecionada."""
        # Restaurar linha anterior
        if self._selected_row:
            prev_row, prev_bg = self._selected_row
            try:
                prev_row.config(bg=prev_bg)
                for child in prev_row.winfo_children():
                    child.config(bg=prev_bg)
            except tk.TclError:
                pass

        # Destacar nova linha
        if row:
            sel_bg = self.c["accent"]
            row.config(bg=sel_bg)
            for child in row.winfo_children():
                child.config(bg=sel_bg, fg="white")
            self._selected_row = (row, orig_bg)

        self.target_email.delete(0, tk.END)
        self.target_email.insert(0, email)

    def _set_active(self, active: bool) -> None:
        email = self.target_email.get().strip()
        if not email:
            messagebox.showerror("Erro", "Insira o email do utilizador.")
            return

        action = "ativar" if active else "desativar"
        if not messagebox.askyesno("Confirmar", f"Tem a certeza que quer {action} a conta\n{email}?"):
            return

        success, message = self.local_auth.admin_set_active(email, active)
        if success:
            messagebox.showinfo("Sucesso", f"Conta {'ativada' if active else 'desativada'}.")
            logging.info("[ADMIN] Conta %s: %s", action, email)
            self._refresh_users()
        else:
            messagebox.showerror("Erro", message)

    def _reset_password(self) -> None:
        email = self.target_email.get().strip()
        pwd = self.new_password.get().strip()
        if not email or not pwd:
            messagebox.showerror("Erro", "Email e nova password são obrigatórios.")
            return

        if len(pwd) < 12:
            messagebox.showerror("Erro", "A password deve ter no mínimo 12 caracteres.")
            return

        if not messagebox.askyesno("Confirmar", f"Reset da password de\n{email}?"):
            return

        success, message = self.local_auth.admin_reset_password(email, pwd)
        if success:
            messagebox.showinfo("Sucesso", "Password alterada com sucesso.")
            logging.info("[ADMIN] Password reset para: %s", email)
            self.new_password.delete(0, tk.END)
        else:
            messagebox.showerror("Erro", message)

    def _delete_user(self) -> None:
        """Elimina permanentemente a conta de um utilizador."""
        email = self.target_email.get().strip()
        if not email:
            messagebox.showerror("Erro", "Insira o email do utilizador.")
            return

        confirm = messagebox.askyesno(
            "⚠ Eliminar Conta",
            f"ATENÇÃO: Esta ação é IRREVERSÍVEL!\n\n"
            f"Todos os dados do utilizador serão eliminados:\n"
            f"  • Conta e credenciais\n"
            f"  • Todas as passwords do gerenciador\n"
            f"  • Tokens e verificações\n\n"
            f"Eliminar permanentemente:\n{email}?",
        )
        if not confirm:
            return

        # Segunda confirmação
        confirm2 = messagebox.askyesno(
            "Confirmar Eliminação",
            f"Última confirmação.\nEliminar {email} permanentemente?",
        )
        if not confirm2:
            return

        success, message = self.local_auth.admin_delete_user(email)
        if success:
            messagebox.showinfo("Sucesso", f"Conta {email} eliminada permanentemente.")
            logging.info("[ADMIN] Conta eliminada: %s", email)
            self.target_email.delete(0, tk.END)
            self._refresh_users()
        else:
            messagebox.showerror("Erro", message)

    def _show_logs(self) -> None:
        success, message, logs = self.local_auth.admin_get_logs()
        if not success:
            messagebox.showerror("Erro", message)
            return

        log_win = tk.Toplevel(self)
        log_win.title("Logs de Autenticação")
        log_win.geometry("900x500")
        log_win.configure(bg=self.c["bg"])

        # Header
        tk.Label(
            log_win, text="📋 Logs de Autenticação",
            font=("Segoe UI", 14, "bold"),
            bg=self.c["bg"], fg=self.c["text"],
        ).pack(anchor="w", padx=16, pady=(12, 6))

        # Text widget
        text_frame = tk.Frame(log_win, bg=self.c["card"])
        text_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        text = tk.Text(
            text_frame, wrap="none",
            font=("Consolas", 10),
            bg=self.c["card"], fg=self.c["text"],
            insertbackground=self.c["text"],
            selectbackground=self.c["accent"],
            selectforeground="white",
            relief="flat",
        )
        vsb = tk.Scrollbar(text_frame, orient="vertical", command=text.yview)
        hsb = tk.Scrollbar(text_frame, orient="horizontal", command=text.xview)
        text.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        text.pack(side="left", fill="both", expand=True)

        for line in logs or []:
            if isinstance(line, dict):
                formatted = (
                    f"{line.get('timestamp', '?')}  "
                    f"[{line.get('event_type', '?')}]  "
                    f"{line.get('email', '?')}  "
                    f"{line.get('details', '')}\n"
                )
            else:
                formatted = f"{line}\n"
            text.insert(tk.END, formatted)

        text.configure(state="disabled")
