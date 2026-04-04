"""
src/ui/password_strength.py
─────────────────────────────────────────────────────────────────────────────
Widget reutilizável de força de password.

Uso:
    bar = PasswordStrengthBar(parent_frame, bg="#FFFFFF")
    bar.pack(fill="x", pady=(0, 10))
    bar.attach(password_entry)   # liga-se ao Entry existente

Não tem campo de texto próprio — liga-se a um Entry externo.
─────────────────────────────────────────────────────────────────────────────
"""

import string
import tkinter as tk


class PasswordStrengthBar(tk.Frame):
    """
    Barra de força de password + checklist de requisitos.

    Bind automático via attach(entry): reage a cada tecla premida no campo
    de password do formulário, sem duplicar o campo de entrada.
    """

    # Cores por score (0-4 requisitos cumpridos)
    _BAR_COLORS = {
        0: "#E9ECEF",   # vazio
        1: "#FF4D4D",   # muito fraca (vermelho)
        2: "#FF4D4D",   # fraca (vermelho)
        3: "#FFA64D",   # razoável (laranja)
        4: "#2EB872",   # forte (verde)
    }

    _STRENGTH_LABELS = {
        0: ("", "#999"),
        1: ("Muito fraca", "#FF4D4D"),
        2: ("Fraca", "#FF4D4D"),
        3: ("Razoável", "#FFA64D"),
        4: ("Forte", "#2EB872"),
    }

    _REQUIREMENTS = {
        "len": "Mínimo 12 caracteres",
        "upp": "Letra maiúscula",
        "num": "Número",
        "sym": "Caracter especial",
    }

    def __init__(self, master: tk.Widget, bg: str = "white", **kwargs):
        super().__init__(master, bg=bg, **kwargs)

        self._bg = bg

        # ── Barra de progresso ───────────────────────────────────────────────
        self._canvas = tk.Canvas(self, height=6, bg="#E9ECEF", highlightthickness=0)
        self._canvas.pack(fill="x")
        # Rectângulo que cresce da esquerda para a direita
        self._bar_rect = self._canvas.create_rectangle(0, 0, 0, 6, fill="#E9ECEF", outline="")

        # ── Label de texto de força (ex: "Forte", "Fraca") ──────────────────
        self._strength_lbl = tk.Label(
            self,
            text="",
            font=("Segoe UI", 8, "bold"),
            bg=bg,
            fg="#999",
            anchor="e",
        )
        self._strength_lbl.pack(fill="x", pady=(3, 6))

        # ── Checklist de requisitos ──────────────────────────────────────────
        self._req_labels: dict[str, tk.Label] = {}
        for key, text in self._REQUIREMENTS.items():
            lbl = tk.Label(
                self,
                text="• " + text,
                font=("Segoe UI", 9),
                bg=bg,
                fg="#CCCCCC",
                anchor="w",
            )
            lbl.pack(fill="x", pady=1)
            self._req_labels[key] = lbl

    # ── API pública ──────────────────────────────────────────────────────────

    def attach(self, entry: tk.Entry) -> None:
        """
        Liga o widget a um Entry do formulário.
        Chama update_strength() automaticamente a cada tecla.
        """
        entry.bind("<KeyRelease>", lambda _e: self.update_strength(entry.get()))

    def update_strength(self, password: str) -> None:
        """Recalcula e redesenha barra + checklist para a password dada."""
        checks = {
            "len": len(password) >= 12,
            "upp": any(c.isupper() for c in password),
            "num": any(c.isdigit() for c in password),
            "sym": any(c in string.punctuation for c in password),
        }
        score = sum(checks.values())

        # Actualizar checklist
        for key, passed in checks.items():
            symbol = "✓ " if passed else "• "
            color  = "#2EB872" if passed else "#CCCCCC"
            self._req_labels[key].config(
                text=symbol + self._REQUIREMENTS[key],
                fg=color,
            )

        # Actualizar barra
        bar_color = self._BAR_COLORS.get(score, "#E9ECEF")
        self.update_idletasks()
        total_width = self._canvas.winfo_width()
        filled = int((score / 4) * total_width) if total_width > 1 else 0
        self._canvas.coords(self._bar_rect, 0, 0, filled, 6)
        self._canvas.itemconfig(self._bar_rect, fill=bar_color)

        # Actualizar label de texto
        text, text_color = self._STRENGTH_LABELS.get(score, ("", "#999"))
        self._strength_lbl.config(text=text, fg=text_color)
