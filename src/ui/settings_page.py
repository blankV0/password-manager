"""
Página de Definições do Password Manager.

Configurações da aplicação: tema, auto-lock, clipboard, gerador
de passwords, e informações da app.
"""

from __future__ import annotations

import json
import logging
import tkinter as tk
from tkinter import messagebox
from pathlib import Path
from typing import Callable, Optional

from src import __version__
from src.models.local_auth import LocalAuth

# ── Ficheiro de preferências local ───────────────────────────────────────────
_PREFS_PATH = Path(__file__).resolve().parents[2] / "data" / "preferences.json"

_DEFAULT_PREFS: dict = {
    "theme": "light",                 # "light" | "dark"
    "auto_lock_minutes": 5,           # 0 = desativado
    "clipboard_clear_seconds": 30,    # 0 = desativado
    "pw_default_length": 20,
    "pw_include_symbols": True,
    "pw_include_numbers": True,
    "pw_include_uppercase": True,
    "show_password_strength": True,
}


def _load_prefs() -> dict:
    """Carrega preferências do disco (ou devolve defaults)."""
    try:
        if _PREFS_PATH.exists():
            data = json.loads(_PREFS_PATH.read_text(encoding="utf-8"))
            merged = {**_DEFAULT_PREFS, **data}
            return merged
    except Exception as exc:
        logging.warning("[AVISO] Falha ao ler preferências: %s", exc)
    return dict(_DEFAULT_PREFS)


def _save_prefs(prefs: dict) -> None:
    """Persiste preferências em JSON."""
    try:
        _PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _PREFS_PATH.write_text(
            json.dumps(prefs, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception as exc:
        logging.warning("[AVISO] Falha ao gravar preferências: %s", exc)


# ═════════════════════════════════════════════════════════════════════════════
# Cores por tema
# ═════════════════════════════════════════════════════════════════════════════

THEMES: dict[str, dict[str, str]] = {
    "light": {
        "bg": "#FFFFFF",
        "card": "#F9FAFB",
        "text": "#1f2937",
        "muted": "#6b7280",
        "border": "#e5e7eb",
        "accent": "#4f46e5",
        "accent_hover": "#4338ca",
        "success": "#22c55e",
        "danger": "#ef4444",
        "input_bg": "#FFFFFF",
        "sidebar": "#2C2F33",
        "sidebar_text": "#b9bbbe",
        "topbar": "white",
        "topbar_text": "black",
    },
    "dark": {
        "bg": "#1a1b1e",
        "card": "#25262b",
        "text": "#c1c2c5",
        "muted": "#909296",
        "border": "#373A40",
        "accent": "#748ffc",
        "accent_hover": "#5c7cfa",
        "success": "#51cf66",
        "danger": "#ff6b6b",
        "input_bg": "#2C2E33",
        "sidebar": "#141517",
        "sidebar_text": "#909296",
        "topbar": "#25262b",
        "topbar_text": "#c1c2c5",
    },
}


def get_theme_colors(theme_name: str = "light") -> dict[str, str]:
    """Devolve o dicionário de cores para o tema pedido."""
    return THEMES.get(theme_name, THEMES["light"])


# ═════════════════════════════════════════════════════════════════════════════
# Propagação de tema a widgets que não suportam tema nativo
# ═════════════════════════════════════════════════════════════════════════════

# Backgrounds claros que devem ser mapeados para as cores do tema activo
_LIGHT_BG = {"white", "#ffffff", "#FFFFFF", "#fff", "#FFF"}
_LIGHT_CARD_BG = {"#F8F9FA", "#f8f9fa", "#F1F3F5", "#f1f3f5"}
_LIGHT_BORDER = {"#E9ECEF", "#e9ecef"}
_DARK_TEXT = {"#2C2F33", "#2c2f33", "#444", "#444444"}
_MUTED_TEXT = {"#999", "#999999", "#666", "#666666", "#BBB", "#bbb"}


def apply_theme_recursive(widget: tk.Widget, tc: dict) -> None:
    """Percorre recursivamente a árvore de widgets e recolora tudo
    com base no dicionário de tema ``tc``.

    Usado para aplicar dark mode a páginas do colega (gerador1)
    que usam cores hardcoded.
    """
    import tkinter.ttk as ttk

    # ttk.Treeview precisa de configuração via Style
    if isinstance(widget, ttk.Treeview):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background=tc["card"],
            foreground=tc["text"],
            fieldbackground=tc["card"],
            rowheight=40,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Treeview.Heading",
            background=tc["border"],
            foreground=tc["muted"],
            font=("Segoe UI", 8, "bold"),
            relief="flat",
        )
        style.map(
            "Treeview",
            background=[("selected", tc["accent"])],
            foreground=[("selected", "white")],
        )
        # Tags de cor para gerenciador
        try:
            widget.tag_configure("insegura", background="#552222" if tc["bg"] != "#FFFFFF" else "#FFD6D6")
            widget.tag_configure("repetida", background="#553B11" if tc["bg"] != "#FFFFFF" else "#FFE4B3")
        except Exception:
            pass

    # Pular widgets ttk genéricos — não suportam .config(bg=...)
    if isinstance(widget, ttk.Widget):
        for child in widget.winfo_children():
            apply_theme_recursive(child, tc)
        return

    try:
        cfg = widget.config()
    except Exception:
        return

    # ── Recolorir background ──
    if "background" in cfg or "bg" in cfg:
        try:
            cur_bg = str(widget.cget("bg"))
        except Exception:
            cur_bg = ""
        if cur_bg in _LIGHT_BG:
            widget.config(bg=tc["bg"])
        elif cur_bg in _LIGHT_CARD_BG:
            widget.config(bg=tc["card"])
        elif cur_bg in _LIGHT_BORDER:
            widget.config(bg=tc["border"])

    # ── Recolorir foreground ──
    if "foreground" in cfg or "fg" in cfg:
        try:
            cur_fg = str(widget.cget("fg"))
        except Exception:
            cur_fg = ""
        if cur_fg in _DARK_TEXT:
            widget.config(fg=tc["text"])
        elif cur_fg in _MUTED_TEXT:
            widget.config(fg=tc["muted"])

    # ── highlightbackground (bordas) ──
    if "highlightbackground" in cfg:
        try:
            cur_hb = str(widget.cget("highlightbackground"))
        except Exception:
            cur_hb = ""
        if cur_hb in _LIGHT_BORDER:
            widget.config(highlightbackground=tc["border"])

    # ── Entry / Text specifics ──
    if isinstance(widget, tk.Entry):
        try:
            cur_bg = str(widget.cget("bg"))
            if cur_bg in _LIGHT_BG | _LIGHT_CARD_BG:
                widget.config(
                    bg=tc["input_bg"],
                    fg=tc["text"],
                    insertbackground=tc["text"],
                )
            rdbg = str(widget.cget("readonlybackground")) if "readonlybackground" in cfg else ""
            if rdbg in _LIGHT_BG | _LIGHT_CARD_BG:
                widget.config(readonlybackground=tc["input_bg"])
        except Exception:
            pass

    if isinstance(widget, tk.Text):
        try:
            cur_bg = str(widget.cget("bg"))
            if cur_bg in _LIGHT_BG | _LIGHT_CARD_BG:
                widget.config(
                    bg=tc["input_bg"],
                    fg=tc["text"],
                    insertbackground=tc["text"],
                )
        except Exception:
            pass

    if isinstance(widget, tk.Canvas):
        try:
            cur_bg = str(widget.cget("bg"))
            if cur_bg in _LIGHT_BG | _LIGHT_CARD_BG:
                widget.config(bg=tc["bg"])
        except Exception:
            pass

    # ── Checkbutton ──
    if isinstance(widget, tk.Checkbutton):
        try:
            cur_bg = str(widget.cget("bg"))
            if cur_bg in _LIGHT_BG:
                widget.config(
                    bg=tc["bg"],
                    fg=tc["text"],
                    activebackground=tc["bg"],
                    selectcolor=tc["input_bg"],
                )
        except Exception:
            pass

    # ── Botões — manter botões escuros/coloridos, ajustar os claros ──
    if isinstance(widget, tk.Button):
        try:
            cur_bg = str(widget.cget("bg"))
            if cur_bg in _LIGHT_CARD_BG | _LIGHT_BORDER:
                widget.config(bg=tc["card"], fg=tc["text"])
        except Exception:
            pass

    # ── Recursão nos filhos ──
    for child in widget.winfo_children():
        apply_theme_recursive(child, tc)


# ═════════════════════════════════════════════════════════════════════════════
# Widget: SettingsPage
# ═════════════════════════════════════════════════════════════════════════════

class SettingsPage(tk.Frame):
    """Página de definições completa, embebida no main_container do Dashboard."""

    def __init__(
        self,
        master: tk.Widget,
        on_theme_changed: Optional[Callable[[str], None]] = None,
        local_auth: Optional[LocalAuth] = None,
        on_logout: Optional[Callable] = None,
    ):
        self.prefs = _load_prefs()
        self._theme = self.prefs.get("theme", "light")
        self.c = get_theme_colors(self._theme)
        super().__init__(master, bg=self.c["bg"])
        self.on_theme_changed = on_theme_changed
        self.local_auth = local_auth
        self.on_logout = on_logout

        # ── Variáveis Tk ─────────────────────────────────────────────
        self.var_theme = tk.StringVar(value=self._theme)
        self.var_auto_lock = tk.IntVar(value=self.prefs.get("auto_lock_minutes", 5))
        self.var_clip_clear = tk.IntVar(value=self.prefs.get("clipboard_clear_seconds", 30))
        self.var_pw_len = tk.IntVar(value=self.prefs.get("pw_default_length", 20))
        self.var_pw_symbols = tk.BooleanVar(value=self.prefs.get("pw_include_symbols", True))
        self.var_pw_numbers = tk.BooleanVar(value=self.prefs.get("pw_include_numbers", True))
        self.var_pw_upper = tk.BooleanVar(value=self.prefs.get("pw_include_uppercase", True))
        self.var_show_strength = tk.BooleanVar(value=self.prefs.get("show_password_strength", True))

        self._build_ui()

    # ── Layout ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Scrollable canvas
        canvas = tk.Canvas(self, bg=self.c["bg"], highlightthickness=0)
        scrollbar = tk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self._inner = tk.Frame(canvas, bg=self.c["bg"])
        self._inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=self._inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mousewheel
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        parent = self._inner

        # ── Secção: Aparência ────────────────────────────────────────
        self._section(parent, "Aparência")
        theme_row = self._card(parent)
        self._label(theme_row, "Tema da aplicação")
        self._sublabel(theme_row, "Altera as cores de toda a interface.")
        btn_frame = tk.Frame(theme_row, bg=self.c["card"])
        btn_frame.pack(anchor="w", pady=(4, 0))
        for value, label in [("light", "☀  Claro"), ("dark", "🌙  Escuro")]:
            selected = self.var_theme.get() == value
            btn = tk.Label(
                btn_frame,
                text=label,
                font=("Segoe UI", 10, "bold" if selected else ""),
                bg=self.c["accent"] if selected else self.c["bg"],
                fg="white" if selected else self.c["text"],
                padx=16, pady=6,
                cursor="hand2",
            )
            btn.pack(side="left", padx=(0, 8))
            btn.bind("<Button-1>", lambda e, v=value: self._set_theme(v))

        # ── Secção: Segurança ────────────────────────────────────────
        self._section(parent, "Segurança")

        lock_card = self._card(parent)
        self._label(lock_card, "Auto-lock (minutos)")
        self._sublabel(lock_card, "Bloqueia a app após inatividade. 0 = desativado.")
        self._spinner(lock_card, self.var_auto_lock, 0, 60)

        clip_card = self._card(parent)
        self._label(clip_card, "Limpar clipboard (segundos)")
        self._sublabel(clip_card, "Remove passwords copiadas do clipboard. 0 = desativado.")
        self._spinner(clip_card, self.var_clip_clear, 0, 120)

        strength_card = self._card(parent)
        self._label(strength_card, "Indicador de força de password")
        self._sublabel(strength_card, "Mostrar barra de força ao registar / alterar password.")
        tk.Checkbutton(
            strength_card, variable=self.var_show_strength,
            bg=self.c["card"], activebackground=self.c["card"],
            fg=self.c["text"], selectcolor=self.c["input_bg"],
            text="Ativado", font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(4, 0))

        # ── Secção: Gerador de Passwords ─────────────────────────────
        self._section(parent, "Gerador de Passwords")

        len_card = self._card(parent)
        self._label(len_card, "Comprimento por defeito")
        self._sublabel(len_card, "Número de caracteres ao gerar uma password.")
        self._spinner(len_card, self.var_pw_len, 12, 128)

        chars_card = self._card(parent)
        self._label(chars_card, "Tipos de caracteres incluídos")
        for var, text in [
            (self.var_pw_upper, "Letras maiúsculas (A-Z)"),
            (self.var_pw_numbers, "Números (0-9)"),
            (self.var_pw_symbols, "Símbolos (!@#$%...)"),
        ]:
            tk.Checkbutton(
                chars_card, variable=var,
                bg=self.c["card"], activebackground=self.c["card"],
                fg=self.c["text"], selectcolor=self.c["input_bg"],
                text=text, font=("Segoe UI", 10),
            ).pack(anchor="w", pady=2)

        # ── Secção: Sobre ────────────────────────────────────────────
        self._section(parent, "Sobre")
        about_card = self._card(parent)
        for key, val in [
            ("Aplicação", "Password Manager"),
            ("Versão", __version__),
            ("Python", self._python_version()),
            ("Encriptação", "AES-256-GCM · Argon2id KDF"),
            ("Autor", "Projecto académico"),
        ]:
            row = tk.Frame(about_card, bg=self.c["card"])
            row.pack(fill="x", pady=2)
            tk.Label(row, text=key, font=("Segoe UI", 10, "bold"),
                     bg=self.c["card"], fg=self.c["text"], width=14, anchor="w").pack(side="left")
            tk.Label(row, text=val, font=("Segoe UI", 10),
                     bg=self.c["card"], fg=self.c["muted"], anchor="w").pack(side="left")

        # ── Secção: Zona de Perigo ──────────────────────────────────
        if self.local_auth and not self.local_auth.is_admin():
            self._section(parent, "⚠ Zona de Perigo")
            danger_card = tk.Frame(
                parent, bg=self.c["card"],
                highlightthickness=2,
                highlightbackground=self.c["danger"],
                padx=16, pady=12,
            )
            danger_card.pack(fill="x", pady=(0, 8))
            self._label(danger_card, "Apagar a minha conta")
            tk.Label(
                danger_card,
                text="Esta ação é IRREVERSÍVEL. A tua conta, todas as passwords\n"
                     "do vault e todos os dados associados serão eliminados permanentemente.",
                font=("Segoe UI", 9),
                bg=self.c["card"], fg=self.c["danger"],
                justify="left",
            ).pack(anchor="w")
            del_btn = tk.Label(
                danger_card, text="X  Eliminar a minha conta",
                font=("Segoe UI", 10, "bold"),
                bg=self.c["danger"], fg="white",
                padx=16, pady=8, cursor="hand2",
            )
            del_btn.pack(anchor="w", pady=(10, 0))
            del_btn.bind("<Button-1>", lambda e: self._delete_own_account())

        # ── Botão guardar ────────────────────────────────────────────
        save_frame = tk.Frame(parent, bg=self.c["bg"])
        save_frame.pack(fill="x", pady=(20, 10))
        save_btn = tk.Label(
            save_frame, text="💾  Guardar definições",
            font=("Segoe UI", 11, "bold"),
            bg=self.c["accent"], fg="white",
            padx=24, pady=10, cursor="hand2",
        )
        save_btn.pack(anchor="w")
        save_btn.bind("<Enter>", lambda e: save_btn.config(bg=self.c["accent_hover"]))
        save_btn.bind("<Leave>", lambda e: save_btn.config(bg=self.c["accent"]))
        save_btn.bind("<Button-1>", lambda e: self._save())

    # ── Helpers de UI ─────────────────────────────────────────────────

    def _section(self, parent: tk.Widget, title: str) -> None:
        tk.Label(
            parent, text=title,
            font=("Segoe UI", 13, "bold"),
            bg=self.c["bg"], fg=self.c["text"],
        ).pack(anchor="w", pady=(18, 6))

    def _card(self, parent: tk.Widget) -> tk.Frame:
        card = tk.Frame(
            parent, bg=self.c["card"],
            highlightthickness=1,
            highlightbackground=self.c["border"],
            padx=16, pady=12,
        )
        card.pack(fill="x", pady=(0, 8))
        return card

    def _label(self, parent: tk.Widget, text: str) -> None:
        tk.Label(
            parent, text=text,
            font=("Segoe UI", 11, "bold"),
            bg=self.c["card"], fg=self.c["text"],
        ).pack(anchor="w")

    def _sublabel(self, parent: tk.Widget, text: str) -> None:
        tk.Label(
            parent, text=text,
            font=("Segoe UI", 9),
            bg=self.c["card"], fg=self.c["muted"],
        ).pack(anchor="w")

    def _spinner(self, parent: tk.Widget, var: tk.IntVar, lo: int, hi: int) -> None:
        frame = tk.Frame(parent, bg=self.c["card"])
        frame.pack(anchor="w", pady=(6, 0))

        def _dec():
            v = var.get()
            if v > lo:
                var.set(v - 1)
                lbl.config(text=str(var.get()))

        def _inc():
            v = var.get()
            if v < hi:
                var.set(v + 1)
                lbl.config(text=str(var.get()))

        btn_m = tk.Label(frame, text="−", font=("Segoe UI", 12, "bold"),
                         bg=self.c["border"], fg=self.c["text"],
                         width=3, cursor="hand2")
        btn_m.pack(side="left")
        btn_m.bind("<Button-1>", lambda e: _dec())

        lbl = tk.Label(frame, text=str(var.get()), font=("Segoe UI", 12),
                       bg=self.c["input_bg"], fg=self.c["text"], width=5)
        lbl.pack(side="left", padx=2)

        btn_p = tk.Label(frame, text="+", font=("Segoe UI", 12, "bold"),
                         bg=self.c["border"], fg=self.c["text"],
                         width=3, cursor="hand2")
        btn_p.pack(side="left")
        btn_p.bind("<Button-1>", lambda e: _inc())

    @staticmethod
    def _python_version() -> str:
        import sys
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    # ── Acções ────────────────────────────────────────────────────────

    def _set_theme(self, theme: str) -> None:
        self.var_theme.set(theme)
        self._save()

    def _delete_own_account(self) -> None:
        """Permite ao utilizador eliminar a sua própria conta."""
        if not self.local_auth:
            return

        confirm = messagebox.askyesno(
            "⚠ Eliminar Conta",
            "ATENÇÃO: Esta ação é IRREVERSÍVEL!\n\n"
            "Todos os teus dados serão eliminados:\n"
            "  • A tua conta e credenciais\n"
            "  • Todas as passwords do vault\n"
            "  • Tokens e verificações\n\n"
            "Tens a certeza que queres eliminar a tua conta?",
        )
        if not confirm:
            return

        confirm2 = messagebox.askyesno(
            "Última Confirmação",
            "Esta é a última confirmação.\n\nEliminar a tua conta permanentemente?",
        )
        if not confirm2:
            return

        success, message = self.local_auth.delete_own_account()
        if success:
            messagebox.showinfo("Conta Eliminada", "A tua conta foi eliminada permanentemente.")
            logging.info("[SETTINGS] Conta própria eliminada.")
            if self.on_logout:
                self.on_logout()
        else:
            messagebox.showerror("Erro", message)

    def _save(self) -> None:
        self.prefs.update({
            "theme": self.var_theme.get(),
            "auto_lock_minutes": self.var_auto_lock.get(),
            "clipboard_clear_seconds": self.var_clip_clear.get(),
            "pw_default_length": self.var_pw_len.get(),
            "pw_include_symbols": self.var_pw_symbols.get(),
            "pw_include_numbers": self.var_pw_numbers.get(),
            "pw_include_uppercase": self.var_pw_upper.get(),
            "show_password_strength": self.var_show_strength.get(),
        })
        _save_prefs(self.prefs)
        logging.info("[OK] Preferências guardadas: tema=%s", self.prefs["theme"])
        messagebox.showinfo("Definições", "Preferências guardadas com sucesso!")

        if self.on_theme_changed:
            self.on_theme_changed(self.var_theme.get())
