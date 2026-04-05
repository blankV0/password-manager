"""
Interface gráfica principal — Login & Registo.

Design split-screen com painel de marca à esquerda e formulário à direita.
Inclui animação do ícone de cadeado, fade-in, focus glow, toggle de
password e estado de loading no botão de submit.
"""

import tkinter as tk
from tkinter import messagebox, ttk
import logging
import math
from datetime import datetime, timedelta
from typing import Callable, Optional

from src.config.settings import (
    WINDOW_TITLE,
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    WINDOW_RESIZABLE,
    APP_LOG_FILE,
    LOGIN_MAX_ATTEMPTS,
    LOGIN_WINDOW_SECONDS,
    LOGIN_COOLDOWN_SECONDS,
)
from src.models.local_auth import LocalAuth, AuthError
from src.services.email_verification import EmailVerification
from src.services.sms_verification import SMSVerification
from src.utils.security_validator import SecurityValidator
from src.utils.logging_config import configure_logging
from src.ui.password_strength import PasswordStrengthBar

# Configurar logging
configure_logging(APP_LOG_FILE)

# ─────────────────────────────────────────────────────────────────────────────
# Design tokens
# ─────────────────────────────────────────────────────────────────────────────
_BRAND_BG = "#1a1d23"          # Painel esquerdo (quase preto)
_BRAND_ACCENT = "#6c63ff"      # Roxo/lilás da marca
_BRAND_ACCENT_HOVER = "#5a52e0"
_BRAND_TEXT = "#ffffff"
_BRAND_MUTED = "#9ca3af"

_FORM_BG = "#ffffff"           # Painel direito (branco)
_FORM_TEXT = "#1f2937"
_FORM_MUTED = "#6b7280"
_FORM_BORDER = "#e5e7eb"
_FORM_FOCUS = _BRAND_ACCENT    # Cor do focus glow
_FORM_SUCCESS = "#22c55e"
_FORM_ERROR = "#ef4444"

_TOPBAR_DARK = _BRAND_BG
_TOPBAR_LIGHT = _FORM_BG

_FONT = "Segoe UI"

# Proporção do painel esquerdo (0.38 = 38% da largura)
_LEFT_RATIO = 0.38


# ─────────────────────────────────────────────────────────────────────────────
# Helpers — animação & widgets reutilizáveis
# ─────────────────────────────────────────────────────────────────────────────

class _AnimatedLock:
    """Desenha um cadeado animado num tk.Canvas.

    A animação é um pulso suave de escala (breathe) que corre
    continuamente enquanto o Canvas existir.
    """

    _SIZE = 80           # Dimensão do canvas (px)
    _PERIOD_MS = 2400    # Duração de um ciclo completo
    _STEP_MS = 30        # Intervalo entre frames (~33 fps)
    _MIN_SCALE = 0.92
    _MAX_SCALE = 1.0

    def __init__(self, parent: tk.Widget, bg: str = _BRAND_BG):
        self.canvas = tk.Canvas(
            parent, width=self._SIZE, height=self._SIZE,
            bg=bg, highlightthickness=0,
        )
        self._bg = bg
        self._phase = 0.0
        self._running = True
        self.canvas.bind("<Destroy>", lambda _: self._stop())
        self._tick()

    def _stop(self):
        self._running = False

    def _tick(self):
        if not self._running:
            return
        self._phase += (self._STEP_MS / self._PERIOD_MS) * 2 * math.pi
        scale = self._MIN_SCALE + (self._MAX_SCALE - self._MIN_SCALE) * (0.5 + 0.5 * math.sin(self._phase))
        self._draw(scale)
        self.canvas.after(self._STEP_MS, self._tick)

    def _draw(self, s: float):
        """Redesenha o cadeado com escala *s* (0.0–1.0)."""
        c = self.canvas
        c.delete("all")
        cx, cy = self._SIZE / 2, self._SIZE / 2

        # Arco (shackle)
        r = 16 * s
        arc_y = cy - 8 * s
        c.create_arc(
            cx - r, arc_y - r, cx + r, arc_y + r,
            start=0, extent=180, style="arc",
            outline=_BRAND_ACCENT, width=max(1, int(3.5 * s)),
        )

        # Corpo
        bw = 26 * s
        bh = 20 * s
        body_y = cy + 2 * s
        c.create_rectangle(
            cx - bw / 2, body_y - bh / 2, cx + bw / 2, body_y + bh / 2,
            fill=_BRAND_ACCENT, outline="",
        )

        # Buraco da fechadura
        kr = 3.5 * s
        c.create_oval(
            cx - kr, body_y - kr - 1, cx + kr, body_y + kr - 1,
            fill=self._bg, outline="",
        )
        kw = 2 * s
        kh = 5 * s
        c.create_rectangle(
            cx - kw / 2, body_y + 1, cx + kw / 2, body_y + kh + 1,
            fill=self._bg, outline="",
        )


class _FocusEntry(tk.Entry):
    """Entry com glow animado no focus e placeholder."""

    def __init__(self, master, placeholder: str = "", show: str = "", **kw):
        kw.setdefault("font", (_FONT, 12))
        kw.setdefault("relief", "flat")
        kw.setdefault("highlightthickness", 2)
        kw.setdefault("highlightbackground", _FORM_BORDER)
        kw.setdefault("highlightcolor", _FORM_FOCUS)
        kw.setdefault("bg", "#f9fafb")
        kw.setdefault("fg", _FORM_TEXT)
        kw.setdefault("insertbackground", _FORM_TEXT)

        self._show_char = show
        self._placeholder = placeholder
        self._has_real_text = False

        super().__init__(master, **kw)

        if placeholder:
            self._show_placeholder()
            self.bind("<FocusIn>", self._on_focus_in)
            self.bind("<FocusOut>", self._on_focus_out)

    # ── placeholder ──
    def _show_placeholder(self):
        self.config(show="", fg=_FORM_MUTED)
        self.delete(0, "end")
        self.insert(0, self._placeholder)
        self._has_real_text = False

    def _on_focus_in(self, _e=None):
        if not self._has_real_text:
            self.delete(0, "end")
            self.config(show=self._show_char, fg=_FORM_TEXT)
            self._has_real_text = True

    def _on_focus_out(self, _e=None):
        if not self.get():
            self._show_placeholder()

    def get_value(self) -> str:
        """Retorna o texto real (ignora placeholder)."""
        if not self._has_real_text:
            return ""
        return self.get()


class _PasswordField(tk.Frame):
    """Campo de password com toggle show/hide."""

    def __init__(self, master, placeholder: str = "", **kw):
        super().__init__(master, bg=kw.get("bg", _FORM_BG))

        container = tk.Frame(self, bg="#f9fafb", highlightthickness=2,
                             highlightbackground=_FORM_BORDER, highlightcolor=_FORM_FOCUS)
        container.pack(fill="x")

        self.entry = _FocusEntry(
            container, placeholder=placeholder, show="●",
            highlightthickness=0, bg="#f9fafb", bd=0,
        )
        self.entry.pack(side="left", fill="both", expand=True, ipady=8, padx=(10, 0))

        self._visible = False
        self.toggle_btn = tk.Label(
            container, text="👁", bg="#f9fafb", fg=_FORM_MUTED,
            font=(_FONT, 12), cursor="hand2", padx=10,
        )
        self.toggle_btn.pack(side="right", fill="y")
        self.toggle_btn.bind("<Button-1>", self._toggle)

    def _toggle(self, _e=None):
        self._visible = not self._visible
        if self.entry._has_real_text:
            self.entry.config(show="" if self._visible else "●")
        self.toggle_btn.config(
            text="🙈" if self._visible else "👁",
            fg=_BRAND_ACCENT if self._visible else _FORM_MUTED,
        )

    def get_value(self) -> str:
        return self.entry.get_value()

    def bind_enter(self, callback):
        self.entry.bind("<Return>", callback)


class _ActionButton(tk.Canvas):
    """Botão flat com hover suave, cantos arredondados e estado loading."""

    _HEIGHT = 46
    _RADIUS = 10

    def __init__(self, master, text: str, command: Callable,
                 bg_color: str = _BRAND_ACCENT, fg_color: str = "#ffffff",
                 hover_color: str = _BRAND_ACCENT_HOVER, width: int = 340):
        super().__init__(master, height=self._HEIGHT, bg=_FORM_BG,
                         highlightthickness=0, bd=0)
        self._text = text
        self._command = command
        self._bg = bg_color
        self._fg = fg_color
        self._hover = hover_color
        self._current_bg = bg_color
        self._loading = False
        self._dots = 0
        self._width = width

        self.bind("<Configure>", self._on_resize)
        self.bind("<Enter>", lambda _: self._set_bg(self._hover))
        self.bind("<Leave>", lambda _: self._set_bg(self._bg))
        self.bind("<Button-1>", lambda _: self._on_click())
        self.config(cursor="hand2")

    def _set_bg(self, color: str):
        if self._loading:
            return
        self._current_bg = color
        self._redraw()

    def _on_resize(self, _e=None):
        self._redraw()

    def _redraw(self):
        self.delete("all")
        w = self.winfo_width() or self._width
        h = self._HEIGHT
        r = self._RADIUS
        # Rounded rect
        self.create_arc(0, 0, 2 * r, 2 * r, start=90, extent=90, fill=self._current_bg, outline="")
        self.create_arc(w - 2 * r, 0, w, 2 * r, start=0, extent=90, fill=self._current_bg, outline="")
        self.create_arc(0, h - 2 * r, 2 * r, h, start=180, extent=90, fill=self._current_bg, outline="")
        self.create_arc(w - 2 * r, h - 2 * r, w, h, start=270, extent=90, fill=self._current_bg, outline="")
        self.create_rectangle(r, 0, w - r, h, fill=self._current_bg, outline="")
        self.create_rectangle(0, r, w, h - r, fill=self._current_bg, outline="")
        # Text
        display = self._text if not self._loading else "A verificar" + "." * (self._dots % 4)
        self.create_text(w / 2, h / 2, text=display, fill=self._fg, font=(_FONT, 12, "bold"))

    def _on_click(self):
        if self._loading:
            return
        self._command()

    def set_loading(self, loading: bool):
        self._loading = loading
        if loading:
            self._current_bg = _FORM_MUTED
            self.config(cursor="wait")
            self._animate_dots()
        else:
            self._current_bg = self._bg
            self.config(cursor="hand2")
            self._dots = 0
        self._redraw()

    def _animate_dots(self):
        if not self._loading:
            return
        self._dots += 1
        self._redraw()
        self.after(400, self._animate_dots)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers — layout partilhado (titlebar, split-screen)
# ─────────────────────────────────────────────────────────────────────────────

def _build_titlebar(parent, login_app: "LoginApp"):
    """Constrói a barra de título custom split dark/light."""
    bar = tk.Frame(parent, height=35, bg=_TOPBAR_LIGHT)
    bar.pack(fill="x", side="top")
    bar.pack_propagate(False)

    left = tk.Frame(bar, bg=_TOPBAR_DARK, height=35)
    left.pack(side="left", fill="y")
    # A largura é dinâmica — será ajustada pelo <Configure> do parent

    right = tk.Frame(bar, bg=_TOPBAR_LIGHT, height=35)
    right.pack(side="left", fill="both", expand=True)

    for f in (bar, left, right):
        f.bind("<Button-1>", login_app.start_move)
        f.bind("<B1-Motion>", login_app.mover_janela)

    # Botão fechar
    btn_close = tk.Label(right, text="✕", bg=_TOPBAR_LIGHT, fg=_FORM_TEXT,
                         font=(_FONT, 11), width=4, cursor="hand2")
    btn_close.pack(side="right", fill="y")
    btn_close.bind("<Enter>", lambda e: btn_close.config(bg="#e74c3c", fg="white"))
    btn_close.bind("<Leave>", lambda e: btn_close.config(bg=_TOPBAR_LIGHT, fg=_FORM_TEXT))
    btn_close.bind("<Button-1>", lambda e: login_app.root.destroy())

    # Botão minimizar
    btn_min = tk.Label(right, text="—", bg=_TOPBAR_LIGHT, fg=_FORM_TEXT,
                       font=(_FONT, 11), width=4, cursor="hand2")
    btn_min.pack(side="right", fill="y")
    btn_min.bind("<Enter>", lambda e: btn_min.config(bg="#e5e5e5"))
    btn_min.bind("<Leave>", lambda e: btn_min.config(bg=_TOPBAR_LIGHT, fg=_FORM_TEXT))
    btn_min.bind("<Button-1>", lambda e: login_app.minimizar())

    return bar, left


def _build_brand_panel(parent):
    """Constrói o painel de marca (esquerdo) com lock animado + features."""
    panel = tk.Frame(parent, bg=_BRAND_BG)

    # Spacer topo
    tk.Frame(panel, bg=_BRAND_BG, height=40).pack()

    # Lock animado
    lock = _AnimatedLock(panel, bg=_BRAND_BG)
    lock.canvas.pack(pady=(0, 24))

    # Título da marca
    tk.Label(
        panel, text="Password\nManager",
        font=(_FONT, 26, "bold"), bg=_BRAND_BG, fg=_BRAND_TEXT,
        justify="center",
    ).pack(pady=(0, 8))

    tk.Label(
        panel, text="O seu cofre digital seguro.",
        font=(_FONT, 11), bg=_BRAND_BG, fg=_BRAND_MUTED,
    ).pack(pady=(0, 32))

    # Separador
    sep = tk.Frame(panel, bg="#2d3139", height=1)
    sep.pack(fill="x", padx=32, pady=(0, 28))

    # Features
    features = [
        ("🔐", "AES-256-GCM", "Encriptação de nível militar"),
        ("🛡", "Argon2id", "Hash de passwords OWASP"),
        ("☁", "Sync seguro", "Servidor dedicado via VPN"),
    ]
    for emoji, title, desc in features:
        row = tk.Frame(panel, bg=_BRAND_BG)
        row.pack(fill="x", padx=32, pady=6)

        tk.Label(
            row, text=emoji, font=(_FONT, 16), bg=_BRAND_BG,
        ).pack(side="left", padx=(0, 12))

        text_col = tk.Frame(row, bg=_BRAND_BG)
        text_col.pack(side="left")

        tk.Label(
            text_col, text=title,
            font=(_FONT, 11, "bold"), bg=_BRAND_BG, fg=_BRAND_TEXT,
            anchor="w",
        ).pack(anchor="w")

        tk.Label(
            text_col, text=desc,
            font=(_FONT, 9), bg=_BRAND_BG, fg=_BRAND_MUTED,
            anchor="w",
        ).pack(anchor="w")

    return panel


def _fade_in(widget: tk.Widget, duration_ms: int = 400, steps: int = 12, _step: int = 0, *, rely: float = 0.5):
    """Fade-in suave de um widget usando lift/place alpha trick.

    Tkinter não suporta opacidade por widget, então simulamos com
    uma série rápida de place() com offsets decrescentes que dão
    a ilusão de um slide-up + fade.

    *rely* deve corresponder ao rely base do widget (0.5 para cards
    centrados, 0.0 para painéis ancorados ao topo).
    """
    if _step > steps:
        return
    # slide-up: começa 15px abaixo e sobe até 0
    offset = int(15 * (1 - _step / steps))
    widget.place_configure(rely=rely, y=offset)
    widget.after(
        duration_ms // steps,
        lambda: _fade_in(widget, duration_ms, steps, _step + 1, rely=rely),
    )


# ─────────────────────────────────────────────────────────────────────────────
# LoginApp
# ─────────────────────────────────────────────────────────────────────────────

class LoginApp:
    """Aplicação de Login com interface Tkinter."""

    def __init__(self, root: tk.Misc, on_login_success: Optional[Callable[[str], None]] = None):
        self.root = root
        self.on_login_success = on_login_success
        self.root.title(WINDOW_TITLE)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.resizable(WINDOW_RESIZABLE, WINDOW_RESIZABLE)
        self.root.configure(bg=_FORM_BG)

        self.local_auth = LocalAuth()
        self.current_view = "login"
        self.login_attempts = {}
        self.current_email = None
        self.session_started_at = None
        self._vault_master_password: str = ""

        # Variáveis para dragging
        self.offset_x = 0
        self.offset_y = 0

        # Referências a widgets de formulário
        self._login_btn: Optional[_ActionButton] = None

        # Verificar conectividade com API
        if self.local_auth.disabled:
            messagebox.showerror(
                "Erro de Configuração",
                "API_BASE_URL não está configurada.\n\n"
                "Verifique o arquivo .env e certifique-se de que:\n"
                "- API_BASE_URL está preenchido\n"
                "- O servidor de API está ativo\n"
                "- As configurações de TTL no servidor são válidas (mínimo 60 segundos)",
            )
            logging.error("[ERRO] API desabilizada - verificar configuração")

        self.show_login_view()
        logging.info("[OK] Aplicação iniciada")

    # ── window helpers ──

    def start_move(self, event):
        self.offset_x = event.x_root - self.root.winfo_x()
        self.offset_y = event.y_root - self.root.winfo_y()

    def mover_janela(self, event):
        self.root.geometry(f"+{event.x_root - self.offset_x}+{event.y_root - self.offset_y}")

    def minimizar(self):
        self.root.iconify()

    def clear_window(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def _center_window(self, width: int = WINDOW_WIDTH, height: int = WINDOW_HEIGHT):
        self.root.update_idletasks()
        sx = self.root.winfo_screenwidth()
        sy = self.root.winfo_screenheight()
        self.root.geometry(f"{width}x{height}+{(sx - width) // 2}+{(sy - height) // 2}")

    # ── rate-limiting ──

    def _check_rate_limit(self, key: str) -> bool:
        now = datetime.now()
        record = self.login_attempts.get(key)
        if not record:
            self.login_attempts[key] = {"count": 0, "first_attempt": now, "cooldown_until": None}
            return True
        if record.get("cooldown_until") and now < record["cooldown_until"]:
            return False
        if now - record["first_attempt"] > timedelta(seconds=LOGIN_WINDOW_SECONDS):
            record["count"] = 0
            record["first_attempt"] = now
            record["cooldown_until"] = None
            return True
        if record["count"] >= LOGIN_MAX_ATTEMPTS:
            return False
        return True

    def _register_failed_attempt(self, key: str) -> None:
        record = self.login_attempts.setdefault(
            key, {"count": 0, "first_attempt": datetime.now(), "cooldown_until": None},
        )
        record["count"] += 1
        if record["count"] >= LOGIN_MAX_ATTEMPTS:
            record["cooldown_until"] = datetime.now() + timedelta(seconds=LOGIN_COOLDOWN_SECONDS)

    # ══════════════════════════════════════════════════════════════════════════
    # LOGIN VIEW
    # ══════════════════════════════════════════════════════════════════════════

    def show_login_view(self):
        self.clear_window()
        self.current_view = "login"
        self._center_window()

        outer = tk.Frame(self.root, bg=_FORM_BG)
        outer.pack(fill="both", expand=True)

        # Titlebar
        _bar, _bar_left = _build_titlebar(outer, self)

        # Body (split-screen)
        body = tk.Frame(outer, bg=_FORM_BG)
        body.pack(fill="both", expand=True)

        # Painel esquerdo — marca
        left_panel = _build_brand_panel(body)
        left_panel.place(relx=0, rely=0, relwidth=_LEFT_RATIO, relheight=1)

        # Ajustar largura do titlebar dark
        def _sync_left(_e=None):
            _bar_left.config(width=int(body.winfo_width() * _LEFT_RATIO))
        body.bind("<Configure>", _sync_left)

        # Painel direito — formulário
        right_panel = tk.Frame(body, bg=_FORM_BG)
        right_panel.place(relx=_LEFT_RATIO, rely=0, relwidth=1 - _LEFT_RATIO, relheight=1)

        # Card de formulário centrado
        card = tk.Frame(right_panel, bg=_FORM_BG)
        card.place(relx=0.5, rely=0.5, anchor="center")

        # ── Header ──
        tk.Label(
            card, text="Password Manager",
            font=(_FONT, 12), bg=_FORM_BG, fg=_BRAND_ACCENT,
        ).pack(anchor="w")

        tk.Label(
            card, text="Entrar",
            font=(_FONT, 28, "bold"), bg=_FORM_BG, fg=_FORM_TEXT,
        ).pack(anchor="w", pady=(6, 4))

        tk.Label(
            card, text="Aceda ao seu cofre com segurança e continue\nde onde ficou.",
            font=(_FONT, 10), bg=_FORM_BG, fg=_FORM_MUTED,
            justify="left",
        ).pack(anchor="w", pady=(0, 24))

        # ── Email ──
        tk.Label(
            card, text="Email ou Telemóvel",
            font=(_FONT, 10, "bold"), bg=_FORM_BG, fg=_FORM_TEXT,
        ).pack(anchor="w")

        self.login_entry = _FocusEntry(card, placeholder="nome@exemplo.pt")
        self.login_entry.pack(fill="x", pady=(6, 16), ipady=8)
        self.login_entry.bind("<Return>", lambda _: self.login())

        # ── Password ──
        tk.Label(
            card, text="Palavra-passe",
            font=(_FONT, 10, "bold"), bg=_FORM_BG, fg=_FORM_TEXT,
        ).pack(anchor="w")

        self._pw_field = _PasswordField(card, placeholder="••••••••••••")
        self._pw_field.pack(fill="x", pady=(6, 24))
        self._pw_field.bind_enter(lambda _: self.login())

        # ── Botão Entrar ──
        self._login_btn = _ActionButton(
            card, text="Entrar", command=self.login,
        )
        self._login_btn.pack(fill="x", ipady=0)

        # ── Link Registar ──
        reg_link = tk.Label(
            card, text="Não tem conta? Registar",
            font=(_FONT, 10), bg=_FORM_BG, fg=_BRAND_ACCENT,
            cursor="hand2",
        )
        reg_link.pack(pady=(16, 0))
        reg_link.bind("<Enter>", lambda e: reg_link.config(font=(_FONT, 10, "underline")))
        reg_link.bind("<Leave>", lambda e: reg_link.config(font=(_FONT, 10)))
        reg_link.bind("<Button-1>", lambda e: self.show_register_view())

        # Fade-in
        _fade_in(card)

    # ══════════════════════════════════════════════════════════════════════════
    # REGISTER VIEW
    # ══════════════════════════════════════════════════════════════════════════

    def show_register_view(self):
        self.clear_window()
        self.current_view = "register"
        self._center_window(height=900)

        outer = tk.Frame(self.root, bg=_FORM_BG)
        outer.pack(fill="both", expand=True)

        _bar, _bar_left = _build_titlebar(outer, self)

        body = tk.Frame(outer, bg=_FORM_BG)
        body.pack(fill="both", expand=True)

        left_panel = _build_brand_panel(body)
        left_panel.place(relx=0, rely=0, relwidth=_LEFT_RATIO, relheight=1)

        def _sync_left(_e=None):
            _bar_left.config(width=int(body.winfo_width() * _LEFT_RATIO))
        body.bind("<Configure>", _sync_left)

        right_panel = tk.Frame(body, bg=_FORM_BG)
        right_panel.place(relx=_LEFT_RATIO, rely=0, relwidth=1 - _LEFT_RATIO, relheight=1)

        # Card — sem scroll, cabe tudo na janela
        card = tk.Frame(right_panel, bg=_FORM_BG)
        card.pack(padx=48, pady=(18, 12))

        # ── Header ──
        tk.Label(card, text="Password Manager", font=(_FONT, 11), bg=_FORM_BG, fg=_BRAND_ACCENT).pack(anchor="w")
        tk.Label(card, text="Criar conta", font=(_FONT, 24, "bold"), bg=_FORM_BG, fg=_FORM_TEXT).pack(anchor="w", pady=(2, 2))
        tk.Label(
            card, text="Registe-se para começar a gerir os seus acessos com segurança.",
            font=(_FONT, 9), bg=_FORM_BG, fg=_FORM_MUTED, justify="left",
        ).pack(anchor="w", pady=(0, 14))

        # ── Username ──
        tk.Label(card, text="Username", font=(_FONT, 9, "bold"), bg=_FORM_BG, fg=_FORM_TEXT).pack(anchor="w")
        self.reg_username_entry = _FocusEntry(card, placeholder="johndoe")
        self.reg_username_entry.pack(fill="x", pady=(4, 8), ipady=6)

        # ── Email ──
        tk.Label(card, text="Email", font=(_FONT, 9, "bold"), bg=_FORM_BG, fg=_FORM_TEXT).pack(anchor="w")
        self.reg_email_entry = _FocusEntry(card, placeholder="nome@exemplo.pt")
        self.reg_email_entry.pack(fill="x", pady=(4, 8), ipady=6)

        # ── Password ──
        tk.Label(card, text="Palavra-passe", font=(_FONT, 9, "bold"), bg=_FORM_BG, fg=_FORM_TEXT).pack(anchor="w")

        pw_row = tk.Frame(card, bg=_FORM_BG)
        pw_row.pack(fill="x", pady=(4, 0))

        self._reg_pw_field = _PasswordField(pw_row, placeholder="Mínimo 12 caracteres")
        self._reg_pw_field.pack(side="left", fill="x", expand=True)

        gen_btn = tk.Label(
            pw_row, text="🎲", font=(_FONT, 16), bg=_FORM_BG, fg=_BRAND_ACCENT,
            cursor="hand2", padx=8,
        )
        gen_btn.pack(side="right")
        gen_btn.bind("<Button-1>", lambda _: self._generate_register_password())
        gen_btn.bind("<Enter>", lambda e: gen_btn.config(fg=_BRAND_ACCENT_HOVER))
        gen_btn.bind("<Leave>", lambda e: gen_btn.config(fg=_BRAND_ACCENT))

        self._strength_bar = PasswordStrengthBar(card, bg=_FORM_BG)
        self._strength_bar.pack(fill="x", pady=(2, 8))
        self._strength_bar.attach(self._reg_pw_field.entry)

        # ── Confirmar Password ──
        tk.Label(card, text="Confirmar Palavra-passe", font=(_FONT, 9, "bold"), bg=_FORM_BG, fg=_FORM_TEXT).pack(anchor="w")
        self._reg_confirm_field = _PasswordField(card, placeholder="Repetir palavra-passe")
        self._reg_confirm_field.pack(fill="x", pady=(4, 8))

        # ── Telemóvel com selector de país ──
        tk.Label(card, text="Telemóvel", font=(_FONT, 9, "bold"), bg=_FORM_BG, fg=_FORM_TEXT).pack(anchor="w")

        phone_row = tk.Frame(card, bg=_FORM_BG)
        phone_row.pack(fill="x", pady=(4, 14))

        # Country code dropdown
        self._country_codes = [
            ("🇵🇹 +351", "+351"),
            ("🇧🇷 +55", "+55"),
            ("🇪🇸 +34", "+34"),
            ("🇫🇷 +33", "+33"),
            ("🇬🇧 +44", "+44"),
            ("🇩🇪 +49", "+49"),
            ("🇮🇹 +39", "+39"),
            ("🇳🇱 +31", "+31"),
            ("🇧🇪 +32", "+32"),
            ("🇨🇭 +41", "+41"),
            ("🇦🇹 +43", "+43"),
            ("🇮🇪 +353", "+353"),
            ("🇱🇺 +352", "+352"),
            ("🇺🇸 +1", "+1"),
            ("🇨🇦 +1", "+1"),
            ("🇲🇽 +52", "+52"),
            ("🇦🇷 +54", "+54"),
            ("🇨🇴 +57", "+57"),
            ("🇨🇱 +56", "+56"),
            ("🇵🇪 +51", "+51"),
            ("🇻🇪 +58", "+58"),
            ("🇺🇾 +598", "+598"),
            ("🇦🇴 +244", "+244"),
            ("🇲🇿 +258", "+258"),
            ("🇨🇻 +238", "+238"),
            ("🇬🇼 +245", "+245"),
            ("🇸🇹 +239", "+239"),
            ("🇹🇱 +670", "+670"),
            ("🇮🇳 +91", "+91"),
            ("🇨🇳 +86", "+86"),
            ("🇯🇵 +81", "+81"),
            ("🇰🇷 +82", "+82"),
            ("🇦🇺 +61", "+61"),
            ("🇿🇦 +27", "+27"),
            ("🇳🇬 +234", "+234"),
            ("🇪🇬 +20", "+20"),
            ("🇲🇦 +212", "+212"),
            ("🇹🇷 +90", "+90"),
            ("🇷🇺 +7", "+7"),
            ("🇺🇦 +380", "+380"),
            ("🇵🇱 +48", "+48"),
            ("🇷🇴 +40", "+40"),
            ("🇸🇪 +46", "+46"),
            ("🇳🇴 +47", "+47"),
            ("🇩🇰 +45", "+45"),
            ("🇫🇮 +358", "+358"),
            ("🇬🇷 +30", "+30"),
            ("🇭🇷 +385", "+385"),
            ("🇨🇿 +420", "+420"),
            ("🇭🇺 +36", "+36"),
        ]

        self._cc_var = tk.StringVar(value="🇵🇹 +351")
        cc_combo = ttk.Combobox(
            phone_row, textvariable=self._cc_var,
            values=[c[0] for c in self._country_codes],
            state="readonly", width=10, font=(_FONT, 10),
        )
        cc_combo.pack(side="left", ipady=6, padx=(0, 6))

        # Style for combobox
        style = ttk.Style()
        style.configure("TCombobox", fieldbackground="#f9fafb", background="#f9fafb")

        self.reg_phone_entry = _FocusEntry(phone_row, placeholder="912 345 678")
        self.reg_phone_entry.pack(side="left", fill="x", expand=True, ipady=6)

        # ── Botão Registar ──
        self._reg_btn = _ActionButton(
            card, text="Registar", command=self.register,
            bg_color=_FORM_SUCCESS, hover_color="#16a34a",
        )
        self._reg_btn.pack(fill="x")

        # ── Link Voltar ──
        back_link = tk.Label(card, text="← Voltar ao login", font=(_FONT, 10), bg=_FORM_BG, fg=_BRAND_ACCENT, cursor="hand2")
        back_link.pack(pady=(10, 0))
        back_link.bind("<Enter>", lambda e: back_link.config(font=(_FONT, 10, "underline")))
        back_link.bind("<Leave>", lambda e: back_link.config(font=(_FONT, 10)))
        back_link.bind("<Button-1>", lambda e: self.show_login_view())

        # Animar o painel direito
        _fade_in(right_panel, rely=0)

    # ══════════════════════════════════════════════════════════════════════════
    # PHONE VERIFICATION VIEW
    # ══════════════════════════════════════════════════════════════════════════

    def show_phone_verification_view(self, email: str, phone_number: str, user_name: str):
        self.clear_window()
        self._center_window()

        outer = tk.Frame(self.root, bg=_FORM_BG)
        outer.pack(fill="both", expand=True)

        _bar, _bar_left = _build_titlebar(outer, self)

        body = tk.Frame(outer, bg=_FORM_BG)
        body.pack(fill="both", expand=True)

        left_panel = _build_brand_panel(body)
        left_panel.place(relx=0, rely=0, relwidth=_LEFT_RATIO, relheight=1)

        def _sync_left(_e=None):
            _bar_left.config(width=int(body.winfo_width() * _LEFT_RATIO))
        body.bind("<Configure>", _sync_left)

        right_panel = tk.Frame(body, bg=_FORM_BG)
        right_panel.place(relx=_LEFT_RATIO, rely=0, relwidth=1 - _LEFT_RATIO, relheight=1)

        card = tk.Frame(right_panel, bg=_FORM_BG)
        card.place(relx=0.5, rely=0.5, anchor="center")

        # ── Header ──
        tk.Label(card, text="📱", font=(_FONT, 36), bg=_FORM_BG).pack(pady=(0, 8))
        tk.Label(card, text="Confirmar Telemóvel", font=(_FONT, 24, "bold"), bg=_FORM_BG, fg=_FORM_TEXT).pack(pady=(0, 6))
        tk.Label(
            card,
            text=f"Enviámos um código SMS para\n{SMSVerification.format_phone_display(phone_number)}",
            font=(_FONT, 10), bg=_FORM_BG, fg=_FORM_MUTED, justify="center",
        ).pack(pady=(0, 24))

        # ── Código SMS ──
        tk.Label(card, text="Código SMS (6 dígitos)", font=(_FONT, 10, "bold"), bg=_FORM_BG, fg=_FORM_TEXT).pack(anchor="w")
        sms_entry = _FocusEntry(card, placeholder="000000")
        sms_entry.config(font=(_FONT, 18), justify="center")
        sms_entry.pack(fill="x", pady=(6, 24), ipady=8)

        def verify_sms():
            code = sms_entry.get_value()
            if not code or len(code) != 6:
                messagebox.showerror("Erro", "Insira um código com 6 dígitos!")
                return
            success, message = SMSVerification.verify_sms_code(phone_number, code)
            if success:
                verify_success, verify_message = self.local_auth.verify_phone(email)
                logging.info("[OK] Telemóvel verificado para: %s", email)
                # Seguir para verificação de email
                self.show_email_verification_view(email, user_name)
            else:
                messagebox.showerror("Erro", message)
                logging.warning("[AVISO] Verificação SMS falhou para %s", email)

        def resend_sms():
            success, message = SMSVerification.resend_sms_code(phone_number)
            if success:
                messagebox.showinfo("Sucesso", message)
            else:
                messagebox.showerror("Erro", message)

        _ActionButton(card, text="Verificar Código", command=verify_sms).pack(fill="x")

        resend_link = tk.Label(card, text="Reenviar código", font=(_FONT, 10), bg=_FORM_BG, fg=_BRAND_ACCENT, cursor="hand2")
        resend_link.pack(pady=(12, 0))
        resend_link.bind("<Enter>", lambda e: resend_link.config(font=(_FONT, 10, "underline")))
        resend_link.bind("<Leave>", lambda e: resend_link.config(font=(_FONT, 10)))
        resend_link.bind("<Button-1>", lambda e: resend_sms())

        back_link = tk.Label(card, text="← Voltar ao login", font=(_FONT, 10), bg=_FORM_BG, fg=_FORM_MUTED, cursor="hand2")
        back_link.pack(pady=(8, 0))
        back_link.bind("<Button-1>", lambda e: self.show_login_view())

        _fade_in(card)

    # ══════════════════════════════════════════════════════════════════════════
    # VIEW — Email Verification (shown after SMS verification)
    # ══════════════════════════════════════════════════════════════════════════

    def show_email_verification_view(self, email: str, user_name: str):
        """Ecrã de verificação de email — polls o servidor até o utilizador clicar no link."""
        self.clear_window()
        self._center_window()

        self._email_poll_active = True  # flag to stop polling

        outer = tk.Frame(self.root, bg=_FORM_BG)
        outer.pack(fill="both", expand=True)

        _bar, _bar_left = _build_titlebar(outer, self)

        body = tk.Frame(outer, bg=_FORM_BG)
        body.pack(fill="both", expand=True)

        left_panel = _build_brand_panel(body)
        left_panel.place(relx=0, rely=0, relwidth=_LEFT_RATIO, relheight=1)

        def _sync_left(_e=None):
            _bar_left.config(width=int(body.winfo_width() * _LEFT_RATIO))
        body.bind("<Configure>", _sync_left)

        right_panel = tk.Frame(body, bg=_FORM_BG)
        right_panel.place(relx=_LEFT_RATIO, rely=0, relwidth=1 - _LEFT_RATIO, relheight=1)

        card = tk.Frame(right_panel, bg=_FORM_BG)
        card.place(relx=0.5, rely=0.5, anchor="center")

        # ── Header ──
        tk.Label(card, text="✉️", font=(_FONT, 36), bg=_FORM_BG).pack(pady=(0, 8))
        tk.Label(
            card, text="Verifique o seu Email",
            font=(_FONT, 24, "bold"), bg=_FORM_BG, fg=_FORM_TEXT,
        ).pack(pady=(0, 6))

        # Mask email for display  (ex: t***e@pmanager.pt)
        masked = SecurityValidator.mask_email(email) if hasattr(SecurityValidator, "mask_email") else email
        tk.Label(
            card,
            text=f"Enviámos um email de verificação para\n{masked}\nClique no link no email para confirmar a sua conta.",
            font=(_FONT, 10), bg=_FORM_BG, fg=_FORM_MUTED, justify="center",
            wraplength=340,
        ).pack(pady=(0, 24))

        # ── Status label (updates during polling) ──
        status_var = tk.StringVar(value="A aguardar confirmação…")
        status_lbl = tk.Label(
            card, textvariable=status_var,
            font=(_FONT, 10), bg=_FORM_BG, fg=_BRAND_ACCENT,
        )
        status_lbl.pack(pady=(0, 18))

        # ── Spinner dots animation ──
        dots_var = tk.StringVar(value="●○○")
        dots_lbl = tk.Label(
            card, textvariable=dots_var,
            font=(_FONT, 16), bg=_FORM_BG, fg=_BRAND_ACCENT,
        )
        dots_lbl.pack(pady=(0, 18))
        _dot_frames = ["●○○", "○●○", "○○●", "○●○"]
        _dot_idx = [0]

        def _animate_dots():
            if not self._email_poll_active:
                return
            _dot_idx[0] = (_dot_idx[0] + 1) % len(_dot_frames)
            try:
                dots_var.set(_dot_frames[_dot_idx[0]])
                self.root.after(400, _animate_dots)
            except tk.TclError:
                pass
        self.root.after(400, _animate_dots)

        # ── "Já verifiquei" manual check button ──
        def _manual_check():
            verified = self.local_auth.check_email_verified(email)
            if verified:
                self._email_poll_active = False
                status_var.set("✅ Email verificado com sucesso!")
                dots_var.set("")
                messagebox.showinfo(
                    "Sucesso",
                    "O seu email foi verificado!\nJá pode fazer login.",
                )
                logging.info("[OK] Email verificado para: %s", email)
                self.show_login_view()
            else:
                status_var.set("Ainda não confirmado. Verifique o seu email.")

        check_btn = _ActionButton(card, text="Já verifiquei ✓", command=_manual_check)
        check_btn.pack(fill="x", pady=(0, 8))

        # ── Resend link ──
        def _resend_email():
            success, msg = self.local_auth.resend_verification_email(email)
            if success:
                status_var.set("📨 Email reenviado!")
                messagebox.showinfo("Sucesso", "Email de verificação reenviado com sucesso!")
            else:
                messagebox.showerror("Erro", msg)

        resend_link = tk.Label(
            card, text="Reenviar email de verificação",
            font=(_FONT, 10), bg=_FORM_BG, fg=_BRAND_ACCENT, cursor="hand2",
        )
        resend_link.pack(pady=(4, 0))
        resend_link.bind("<Enter>", lambda e: resend_link.config(font=(_FONT, 10, "underline")))
        resend_link.bind("<Leave>", lambda e: resend_link.config(font=(_FONT, 10)))
        resend_link.bind("<Button-1>", lambda e: _resend_email())

        # ── Back to login ──
        back_link = tk.Label(
            card, text="← Voltar ao login",
            font=(_FONT, 10), bg=_FORM_BG, fg=_FORM_MUTED, cursor="hand2",
        )
        back_link.pack(pady=(8, 0))
        back_link.bind("<Button-1>", lambda e: _go_login())

        def _go_login():
            self._email_poll_active = False
            self.show_login_view()

        # ── Auto-poll every 5 seconds ──
        def _poll():
            if not self._email_poll_active:
                return
            try:
                verified = self.local_auth.check_email_verified(email)
                if verified:
                    self._email_poll_active = False
                    status_var.set("✅ Email verificado com sucesso!")
                    dots_var.set("")
                    messagebox.showinfo(
                        "Sucesso",
                        "O seu email foi verificado!\nJá pode fazer login.",
                    )
                    logging.info("[OK] Email verificado (auto-poll) para: %s", email)
                    self.show_login_view()
                    return
            except Exception:
                pass
            if self._email_poll_active:
                self.root.after(5000, _poll)

        # Start polling after 3s to give user time to read
        self.root.after(3000, _poll)

        _fade_in(card)

    # ══════════════════════════════════════════════════════════════════════════
    # LOGIC — Login
    # ══════════════════════════════════════════════════════════════════════════

    def login(self):
        login_input = self.login_entry.get_value()
        password = self._pw_field.get_value()

        if not login_input or not password:
            messagebox.showerror("Erro", "Por favor preencha todos os campos!")
            logging.warning("[AVISO] Tentativa de login com campos vazios")
            return

        is_email = "@" in login_input
        rate_key = login_input.lower().strip()

        if not self._check_rate_limit(rate_key):
            messagebox.showerror("Bloqueado", "Demasiadas tentativas. Tente novamente mais tarde.")
            return

        # Loading state
        if self._login_btn:
            self._login_btn.set_loading(True)

        def _do_login():
            try:
                if is_email:
                    email_valid, email_msg = SecurityValidator.validate_email(login_input)
                    if not email_valid:
                        messagebox.showerror("Erro", email_msg)
                        return

                    logging.info("[INFO] Tentativa de login com email: %s", SecurityValidator.mask_email(login_input))
                    try:
                        tokens = self.local_auth.login(login_input, password)
                        self.session_started_at = datetime.now()
                        logging.info("[OK] Login bem-sucedido para: %s", SecurityValidator.mask_email(login_input))
                        access_token = tokens.get("access_token")
                        self.current_email = login_input

                        # ── Verificar se email está confirmado ──
                        if not self.local_auth.check_email_verified(login_input):
                            logging.info("[INFO] Email não verificado, a mostrar ecrã de verificação")
                            self.root.after(0, lambda: self.show_email_verification_view(login_input, ""))
                            return

                        # Guardar password temporariamente para derivação KEK do vault
                        self._vault_master_password = password
                        if self.on_login_success and access_token:
                            self.on_login_success(access_token)
                        else:
                            messagebox.showinfo("Sucesso", "Login bem-sucedido!")
                    except AuthError as auth_exc:
                        self._register_failed_attempt(rate_key)
                        logging.warning("[AVISO] Login falhou para: %s", SecurityValidator.mask_email(login_input))
                        messagebox.showerror("Erro", str(auth_exc))
                else:
                    logging.info("[INFO] Tentativa de login com telemóvel: %s", SecurityValidator.mask_phone(login_input))
                    success, result = self.local_auth.login_by_phone(login_input, password)

                    if success:
                        email = result
                        self.session_started_at = datetime.now()
                        logging.info("[OK] Login bem-sucedido por telemóvel: %s", SecurityValidator.mask_phone(login_input))
                        self.current_email = email

                        # ── Verificar se email está confirmado ──
                        if not self.local_auth.check_email_verified(email):
                            logging.info("[INFO] Email não verificado (login por telemóvel)")
                            self.root.after(0, lambda e=email: self.show_email_verification_view(e, ""))
                            return

                        self._vault_master_password = password
                        if self.on_login_success and self.local_auth.auth_token:
                            self.on_login_success(self.local_auth.auth_token)
                        else:
                            messagebox.showinfo("Sucesso", "Login bem-sucedido!")
                    else:
                        self._register_failed_attempt(rate_key)
                        logging.warning("[AVISO] Login por telemóvel falhou: %s", SecurityValidator.mask_phone(login_input))
                        messagebox.showerror("Erro", result)
            except Exception as e:
                logging.error("[ERRO] Exceção ao fazer login: %s", e)
                messagebox.showerror("Erro", f"Erro inesperado: {str(e)}")
            finally:
                if self._login_btn:
                    try:
                        self._login_btn.set_loading(False)
                    except tk.TclError:
                        pass  # Widget já destruído (login success)

        # Dar tempo ao UI de mostrar o loading
        self.root.after(100, _do_login)

    # ══════════════════════════════════════════════════════════════════════════
    # LOGIC — Generate password for register
    # ══════════════════════════════════════════════════════════════════════════

    def _generate_register_password(self):
        """Gera uma password forte e insere no campo de registo."""
        import random, string as _string
        chars = _string.ascii_letters + _string.digits + "!@#$%^&*()_+-=[]{}:;<>?"
        # Garantir que cumpre todos os requisitos
        pw = [
            random.choice(_string.ascii_uppercase),
            random.choice(_string.ascii_lowercase),
            random.choice(_string.digits),
            random.choice("!@#$%^&*()_+-=[]{}:;<>?"),
        ]
        pw += [random.choice(chars) for _ in range(12)]
        random.shuffle(pw)
        generated = "".join(pw)

        # Inserir no campo de password
        entry = self._reg_pw_field.entry
        entry._has_real_text = True
        entry.config(show="●", fg=_FORM_TEXT)
        entry.delete(0, "end")
        entry.insert(0, generated)

        # Inserir no campo de confirmação
        confirm_entry = self._reg_confirm_field.entry
        confirm_entry._has_real_text = True
        confirm_entry.config(show="●", fg=_FORM_TEXT)
        confirm_entry.delete(0, "end")
        confirm_entry.insert(0, generated)

        # Atualizar barra de força
        self._strength_bar.update_strength(generated)

        # Mostrar password temporariamente e copiar
        self._reg_pw_field.entry.config(show="")
        self._reg_pw_field.toggle_btn.config(text="🙈", fg=_BRAND_ACCENT)
        self._reg_pw_field._visible = True

        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(generated)
        except tk.TclError:
            pass

        messagebox.showinfo(
            "Password Gerada",
            "Password forte gerada e copiada para o clipboard!\n\n"
            "⚠️ Guarde-a num local seguro antes de continuar.",
        )

    # ══════════════════════════════════════════════════════════════════════════
    # LOGIC — Register
    # ══════════════════════════════════════════════════════════════════════════

    def register(self):
        try:
            email = self.reg_email_entry.get_value()
            username = self.reg_username_entry.get_value()
            password = self._reg_pw_field.get_value()
            confirm = self._reg_confirm_field.get_value()
            phone_number = self.reg_phone_entry.get_value()

            # Adicionar código do país ao número
            if phone_number and not phone_number.startswith("+"):
                selected = self._cc_var.get()
                cc = next((c[1] for c in self._country_codes if c[0] == selected), "+351")
                phone_number = cc + phone_number.lstrip("0")

            if not all([username, email, password, confirm, phone_number]):
                messagebox.showerror("Erro", "Por favor preencha todos os campos, incluindo username!")
                logging.warning("[AVISO] Registo com campos vazios")
                return

            if not SMSVerification.is_valid_phone(phone_number):
                messagebox.showerror("Erro", "Número de telemóvel inválido!\nSelecione o país e insira o número.")
                logging.warning("[AVISO] Formato de telemóvel inválido: %s", SecurityValidator.mask_phone(phone_number))
                return

            # Loading
            if hasattr(self, "_reg_btn"):
                self._reg_btn.set_loading(True)

            logging.info("[INFO] Tentativa de registo para: %s", SecurityValidator.mask_email(email))
            all_valid, validation_errors = SecurityValidator.validate_registration(email, password, confirm, username)

            if not all_valid:
                error_msg = "\n".join(validation_errors)
                messagebox.showerror("Erro de Validação", error_msg)
                logging.warning("[AVISO] Registo inválido para %s: %s erro(s)", SecurityValidator.mask_email(email), len(validation_errors))
                if hasattr(self, "_reg_btn"):
                    self._reg_btn.set_loading(False)
                return

            success, message, response_data = self.local_auth.register(email, password, phone_number, username)

            if success:
                logging.info("[OK] Utilizador registado: %s", SecurityValidator.mask_email(email))
                user_name = username

                # O servidor já envia o email de verificação automaticamente no registo.
                # Apenas prosseguir para verificação SMS.

                sms_code, sms_message = SMSVerification.generate_sms_code(phone_number)

                if sms_code is None:
                    messagebox.showerror("Erro SMS", sms_message)
                    logging.error("[ERRO] Falha ao gerar código SMS para: %s", SecurityValidator.mask_phone(phone_number))
                    return

                self.show_phone_verification_view(email, phone_number, user_name)
            else:
                logging.warning("[AVISO] Registo falhou para: %s - %s", SecurityValidator.mask_email(email), message)
                # Traduzir mensagem genérica do servidor
                if "could not be completed" in (message or "").lower():
                    message = (
                        "Não foi possível completar o registo.\n\n"
                        "O email ou username já podem estar em uso.\n"
                        "Tente com dados diferentes."
                    )
                messagebox.showerror("Erro", message)

        except Exception as e:
            logging.error("[ERRO] Exceção ao registar: %s", e)
            messagebox.showerror("Erro", f"Erro inesperado: {str(e)}")
        finally:
            if hasattr(self, "_reg_btn"):
                try:
                    self._reg_btn.set_loading(False)
                except tk.TclError:
                    pass
