"""
Interface gráfica principal da aplicação.
Ponto de entrada da aplicação de login com nova interface.
"""

import tkinter as tk
from tkinter import messagebox
import logging
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


class LoginApp:
    """Aplicação de Login com interface Tkinter."""

    def __init__(self, root: tk.Misc, on_login_success: Optional[Callable[[str], None]] = None):
        """
        Inicializa a aplicação.

        Args:
            root: Janela principal Tkinter/Toplevel
            on_login_success: callback opcional chamado com access_token após login com sucesso
        """
        self.root = root
        self.on_login_success = on_login_success
        self.root.title(WINDOW_TITLE)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.resizable(WINDOW_RESIZABLE, WINDOW_RESIZABLE)
        self.root.configure(bg="#FFFFFF")

        # A remoção da titlebar nativa e composição DWM são tratadas
        # pelo AppController (main.py).  LoginApp NÃO deve tocar no
        # estilo Win32 da janela para evitar conflitos.
        
        # Design tokens e cores
        self.design_tokens = {
            "color.bg": "#FFFFFF",
            "color.card": "#FFFFFF",
            "color.text": "#1f2937",
            "color.muted": "#6b7280",
            "color.primary": "#2C2F33",
            "color.primary_soft": "#e9efff",
            "color.accent": "#7c3aed",
            "color.warning": "#f59e0b",
            "color.border": "#e6e8ec",
            "color.shadow": "#000000",
            "space.4": 4,
            "space.8": 8,
            "space.12": 12,
            "space.16": 16,
            "space.20": 20,
            "space.24": 24,
            "space.32": 32,
            "radius.12": 12,
            "radius.16": 16,
        }

        self.colors = {
            "bg": self.design_tokens["color.bg"],
            "card": self.design_tokens["color.card"],
            "text": self.design_tokens["color.text"],
            "muted": self.design_tokens["color.muted"],
            "primary": self.design_tokens["color.primary"],
            "primary_light": self.design_tokens["color.primary_soft"],
            "accent": self.design_tokens["color.accent"],
            "warning": self.design_tokens["color.warning"],
            "border": self.design_tokens["color.border"],
            "success": "#22c55e",
        }

        self.local_auth = LocalAuth()
        self.current_view = "login"
        self.login_attempts = {}
        self.current_email = None
        self.session_started_at = None
        
        # Variáveis para dragging
        self.offset_x = 0
        self.offset_y = 0
        
        # Verificar conectividade com API
        if self.local_auth.disabled:
            messagebox.showerror(
                "Erro de Configuração",
                "API_BASE_URL não está configurada.\n\n"
                "Verifique o arquivo .env e certifique-se de que:\n"
                "- API_BASE_URL está preenchido\n"
                "- O servidor de API está ativo\n"
                "- As configurações de TTL no servidor são válidas (mínimo 60 segundos)"
            )
            logging.error("[ERRO] API desabilizada - verificar configuração")
        
        self.show_login_view()
        logging.info("[OK] Aplicação iniciada")

    def start_move(self, event):
        """Inicia movimento da janela."""
        self.offset_x = event.x_root - self.root.winfo_x()
        self.offset_y = event.y_root - self.root.winfo_y()

    def mover_janela(self, event):
        """Move a janela."""
        self.root.geometry(f"+{event.x_root - self.offset_x}+{event.y_root - self.offset_y}")

    def minimizar(self):
        """Minimiza para a taskbar."""
        self.root.iconify()

    def clear_window(self):
        """Limpa todos os widgets da janela."""
        for widget in self.root.winfo_children():
            widget.destroy()

    def _check_rate_limit(self, key: str) -> bool:
        """
        Verifica se o utilizador pode tentar login.
        Retorna False se atingiu limite de tentativas ou está em cooldown.
        """
        now = datetime.now()
        record = self.login_attempts.get(key)

        if not record:
            self.login_attempts[key] = {
                "count": 0,
                "first_attempt": now,
                "cooldown_until": None,
            }
            return True

        # Verificar se está em cooldown
        cooldown_until = record.get("cooldown_until")
        if cooldown_until and now < cooldown_until:
            return False

        # Resetar se a janela de tentativas expirou
        if now - record["first_attempt"] > timedelta(seconds=LOGIN_WINDOW_SECONDS):
            record["count"] = 0
            record["first_attempt"] = now
            record["cooldown_until"] = None
            return True

        # Verificar se já atingiu o máximo de tentativas
        if record["count"] >= LOGIN_MAX_ATTEMPTS:
            return False

        return True

    def _register_failed_attempt(self, key: str) -> None:
        record = self.login_attempts.setdefault(
            key, {"count": 0, "first_attempt": datetime.now(), "cooldown_until": None}
        )
        record["count"] += 1

        if record["count"] >= LOGIN_MAX_ATTEMPTS:
            record["cooldown_until"] = datetime.now() + timedelta(seconds=LOGIN_COOLDOWN_SECONDS)

    def show_login_view(self):
        """Mostra a tela de login."""
        self.clear_window()
        self.current_view = "login"

        # Centralizar janela
        largura = WINDOW_WIDTH
        altura = WINDOW_HEIGHT
        self.root.update_idletasks()
        screen_largura = self.root.winfo_screenwidth()
        screen_altura = self.root.winfo_screenheight()
        x = (screen_largura // 2) - (largura // 2)
        y = (screen_altura // 2) - (altura // 2)
        self.root.geometry(f"{largura}x{altura}+{x}+{y}")

        # Container principal
        main_container = tk.Frame(self.root, bg="#FFFFFF")
        main_container.pack(fill="both", expand=True)

        # Barra de Título Customizada
        barra_topo = tk.Frame(main_container, height=35, bg="white")
        barra_topo.pack(fill="x", side="top")

        barra_esquerda_topo = tk.Frame(barra_topo, bg="#2C2F33", width=210, height=35)
        barra_esquerda_topo.pack(side="left")
        barra_esquerda_topo.pack_propagate(False)

        barra_direita_topo = tk.Frame(barra_topo, bg="white", height=35)
        barra_direita_topo.pack(side="left", fill="both", expand=True)

        # Bind para mover janela
        for frame in (barra_topo, barra_esquerda_topo, barra_direita_topo):
            frame.bind("<Button-1>", self.start_move)
            frame.bind("<B1-Motion>", self.mover_janela)

        # Botões de Controlo
        btn_fechar = tk.Label(barra_direita_topo, text="✕", bg="white", fg="black", font=("Segoe UI", 11), width=4, cursor="hand2")
        btn_fechar.pack(side="right", fill="y")
        btn_fechar.bind("<Enter>", lambda e: btn_fechar.config(bg="#e5e5e5"))
        btn_fechar.bind("<Leave>", lambda e: btn_fechar.config(bg="white"))
        btn_fechar.bind("<Button-1>", lambda e: self.root.destroy())

        btn_min = tk.Label(barra_direita_topo, text="—", bg="white", fg="black", font=("Segoe UI", 11), width=4, cursor="hand2")
        btn_min.pack(side="right", fill="y")
        btn_min.bind("<Enter>", lambda e: btn_min.config(bg="#e5e5e5"))
        btn_min.bind("<Leave>", lambda e: btn_min.config(bg="white"))
        btn_min.bind("<Button-1>", lambda e: self.minimizar())

        # Conteúdo
        content = tk.Frame(main_container, bg="#FFFFFF")
        content.pack(fill="both", expand=True)
        content.place(relx=0.5, rely=0.5, anchor="center")

        card = tk.Frame(content, bg="#FFFFFF")
        card.pack(padx=24, pady=24)

        # Header
        header = tk.Frame(card, bg="#FFFFFF")
        header.pack(fill="x", padx=32, pady=(28, 12))

        tk.Label(
            header,
            text="Password Manager",
            font=("Segoe UI", 12, "bold"),
            bg="#FFFFFF",
            fg=self.colors["muted"],
        ).pack(anchor="w")

        tk.Label(
            header,
            text="Entrar",
            font=("Segoe UI", 28, "bold"),
            bg="#FFFFFF",
            fg=self.colors["text"],
        ).pack(anchor="w", pady=(8, 4))

        tk.Label(
            header,
            text="Aceda ao seu cofre com segurança e continue de onde ficou.",
            font=("Segoe UI", 11),
            bg="#FFFFFF",
            fg=self.colors["muted"],
            wraplength=420,
            justify="left",
        ).pack(anchor="w")

        # Formulário
        form = tk.Frame(card, bg="#FFFFFF")
        form.pack(fill="x", padx=32, pady=(8, 20))

        tk.Label(
            form,
            text="Email ou Telemóvel",
            font=("Segoe UI", 11, "bold"),
            bg="#FFFFFF",
            fg=self.colors["text"],
        ).pack(anchor="w")
        self.login_entry = tk.Entry(
            form,
            width=34,
            font=("Segoe UI", 12),
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.colors["border"],
            highlightcolor=self.colors["primary"],
        )
        self.login_entry.pack(fill="x", pady=(6, 16), ipady=6)
        self.login_entry.bind("<Return>", lambda e: self.login())

        tk.Label(
            form,
            text="Palavra-passe",
            font=("Segoe UI", 11, "bold"),
            bg="#FFFFFF",
            fg=self.colors["text"],
        ).pack(anchor="w")
        self.password_entry = tk.Entry(
            form,
            width=34,
            font=("Segoe UI", 12),
            show="*",
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.colors["border"],
            highlightcolor=self.colors["primary"],
        )
        self.password_entry.pack(fill="x", pady=(6, 20), ipady=6)
        self.password_entry.bind("<Return>", lambda e: self.login())

        login_btn = tk.Button(
            form,
            text="Entrar",
            command=self.login,
            bg=self.colors["primary"],
            fg="white",
            activebackground=self.colors["primary"],
            activeforeground="white",
            relief="flat",
            cursor="hand2",
            padx=18,
            pady=10,
        )
        login_btn.pack(fill="x")

        register_btn = tk.Button(
            form,
            text="Não tem conta? Registar",
            command=self.show_register_view,
            bg="#FFFFFF",
            fg=self.colors["primary"],
            activebackground="#FFFFFF",
            activeforeground=self.colors["primary"],
            relief="flat",
            cursor="hand2",
            pady=6,
        )
        register_btn.pack(pady=(12, 0))

    def show_register_view(self):
        """Mostra a tela de registo."""
        self.clear_window()
        self.current_view = "register"

        # Centralizar janela
        largura = WINDOW_WIDTH
        altura = WINDOW_HEIGHT
        self.root.update_idletasks()
        screen_largura = self.root.winfo_screenwidth()
        screen_altura = self.root.winfo_screenheight()
        x = (screen_largura // 2) - (largura // 2)
        y = (screen_altura // 2) - (altura // 2)
        self.root.geometry(f"{largura}x{altura}+{x}+{y}")

        # Container principal
        main_container = tk.Frame(self.root, bg="#FFFFFF")
        main_container.pack(fill="both", expand=True)

        # Barra de Título
        barra_topo = tk.Frame(main_container, height=35, bg="white")
        barra_topo.pack(fill="x", side="top")

        barra_esquerda_topo = tk.Frame(barra_topo, bg="#2C2F33", width=210, height=35)
        barra_esquerda_topo.pack(side="left")
        barra_esquerda_topo.pack_propagate(False)

        barra_direita_topo = tk.Frame(barra_topo, bg="white", height=35)
        barra_direita_topo.pack(side="left", fill="both", expand=True)

        for frame in (barra_topo, barra_esquerda_topo, barra_direita_topo):
            frame.bind("<Button-1>", self.start_move)
            frame.bind("<B1-Motion>", self.mover_janela)

        btn_fechar = tk.Label(barra_direita_topo, text="✕", bg="white", fg="black", font=("Segoe UI", 11), width=4, cursor="hand2")
        btn_fechar.pack(side="right", fill="y")
        btn_fechar.bind("<Enter>", lambda e: btn_fechar.config(bg="#e5e5e5"))
        btn_fechar.bind("<Leave>", lambda e: btn_fechar.config(bg="white"))
        btn_fechar.bind("<Button-1>", lambda e: self.root.destroy())

        btn_min = tk.Label(barra_direita_topo, text="—", bg="white", fg="black", font=("Segoe UI", 11), width=4, cursor="hand2")
        btn_min.pack(side="right", fill="y")
        btn_min.bind("<Enter>", lambda e: btn_min.config(bg="#e5e5e5"))
        btn_min.bind("<Leave>", lambda e: btn_min.config(bg="white"))
        btn_min.bind("<Button-1>", lambda e: self.minimizar())

        # Conteúdo
        content = tk.Frame(main_container, bg="#FFFFFF")
        content.pack(fill="both", expand=True)
        content.place(relx=0.5, rely=0.5, anchor="center")

        card = tk.Frame(content, bg="#FFFFFF")
        card.pack(padx=24, pady=24)

        header = tk.Frame(card, bg="#FFFFFF")
        header.pack(fill="x", padx=32, pady=(28, 12))

        tk.Label(
            header,
            text="Criar conta",
            font=("Segoe UI", 28, "bold"),
            bg="#FFFFFF",
            fg=self.colors["text"],
        ).pack(anchor="w", pady=(0, 4))

        tk.Label(
            header,
            text="Registe-se para começar a gerir os seus acessos com segurança.",
            font=("Segoe UI", 11),
            bg="#FFFFFF",
            fg=self.colors["muted"],
            wraplength=460,
            justify="left",
        ).pack(anchor="w")

        form = tk.Frame(card, bg="#FFFFFF")
        form.pack(fill="x", padx=32, pady=(8, 20))

        tk.Label(form, text="Username", font=("Segoe UI", 11, "bold"), bg="#FFFFFF", fg=self.colors["text"]).pack(anchor="w")
        self.reg_username_entry = tk.Entry(form, width=34, font=("Segoe UI", 12), relief="flat", highlightthickness=1,
                                          highlightbackground=self.colors["border"], highlightcolor=self.colors["primary"])
        self.reg_username_entry.pack(fill="x", pady=(6, 12), ipady=6)

        tk.Label(form, text="Email", font=("Segoe UI", 11, "bold"), bg="#FFFFFF", fg=self.colors["text"]).pack(anchor="w")
        self.reg_email_entry = tk.Entry(form, width=34, font=("Segoe UI", 12), relief="flat", highlightthickness=1,
                                       highlightbackground=self.colors["border"], highlightcolor=self.colors["primary"])
        self.reg_email_entry.pack(fill="x", pady=(6, 12), ipady=6)

        tk.Label(form, text="Palavra-passe", font=("Segoe UI", 11, "bold"), bg="#FFFFFF", fg=self.colors["text"]).pack(anchor="w")
        self.reg_password_entry = tk.Entry(form, width=34, font=("Segoe UI", 12), show="*", relief="flat", highlightthickness=1,
                                          highlightbackground=self.colors["border"], highlightcolor=self.colors["primary"])
        self.reg_password_entry.pack(fill="x", pady=(6, 4), ipady=6)

        self._strength_bar = PasswordStrengthBar(form, bg="#FFFFFF")
        self._strength_bar.pack(fill="x", pady=(0, 12))
        self._strength_bar.attach(self.reg_password_entry)

        tk.Label(form, text="Confirmar Palavra-passe", font=("Segoe UI", 11, "bold"), bg="#FFFFFF", fg=self.colors["text"]).pack(anchor="w")
        self.reg_confirm_entry = tk.Entry(form, width=34, font=("Segoe UI", 12), show="*", relief="flat", highlightthickness=1,
                                         highlightbackground=self.colors["border"], highlightcolor=self.colors["primary"])
        self.reg_confirm_entry.pack(fill="x", pady=(6, 12), ipady=6)

        tk.Label(form, text="Telemóvel (ex: +351912345678)", font=("Segoe UI", 11, "bold"), bg="#FFFFFF", fg=self.colors["text"]).pack(anchor="w")
        self.reg_phone_entry = tk.Entry(form, width=34, font=("Segoe UI", 12), relief="flat", highlightthickness=1,
                                       highlightbackground=self.colors["border"], highlightcolor=self.colors["primary"])
        self.reg_phone_entry.pack(fill="x", pady=(6, 20), ipady=6)

        register_btn = tk.Button(form, text="Registar", command=self.register, bg=self.colors["success"], fg="white",
                                activebackground=self.colors["success"], activeforeground="white", relief="flat", cursor="hand2", padx=18, pady=10)
        register_btn.pack(fill="x")

        back_btn = tk.Button(form, text="Voltar", command=self.show_login_view, bg="#FFFFFF", fg=self.colors["primary"],
                            activebackground="#FFFFFF", activeforeground=self.colors["primary"], relief="flat", cursor="hand2", pady=6)
        back_btn.pack(pady=(12, 0))

    def login(self):
        """Processa o login."""
        login_input = self.login_entry.get()
        password = self.password_entry.get()

        if not login_input or not password:
            messagebox.showerror("Erro", "Por favor preencha todos os campos!")
            logging.warning("[AVISO] Tentativa de login com campos vazios")
            return

        is_email = "@" in login_input
        rate_key = login_input.lower().strip()

        if not self._check_rate_limit(rate_key):
            messagebox.showerror("Bloqueado", "Demasiadas tentativas. Tente novamente mais tarde.")
            return

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

    def register(self):
        """Processa o registo."""
        try:
            email = self.reg_email_entry.get()
            username = self.reg_username_entry.get().strip()
            password = self.reg_password_entry.get()
            confirm = self.reg_confirm_entry.get()
            phone_number = self.reg_phone_entry.get()

            if not all([username, email, password, confirm, phone_number]):
                messagebox.showerror("Erro", "Por favor preencha todos os campos, incluindo username!")
                logging.warning("[AVISO] Registo com campos vazios")
                return

            if not SMSVerification.is_valid_phone(phone_number):
                messagebox.showerror("Erro", "Número de telemóvel inválido!\nUse: +351912345678 ou 912345678")
                logging.warning("[AVISO] Formato de telemóvel inválido: %s", SecurityValidator.mask_phone(phone_number))
                return

            logging.info("[INFO] Tentativa de registo para: %s", SecurityValidator.mask_email(email))
            all_valid, validation_errors = SecurityValidator.validate_registration(email, password, confirm, username)

            if not all_valid:
                error_msg = "\n".join(validation_errors)
                messagebox.showerror("Erro de Validação", error_msg)
                logging.warning("[AVISO] Registo inválido para %s: %s erro(s)", SecurityValidator.mask_email(email), len(validation_errors))
                return

            success, message, response_data = self.local_auth.register(email, password, phone_number, username)

            if success:
                logging.info("[OK] Utilizador registado: %s", SecurityValidator.mask_email(email))
                user_name = username
                
                # Enviar email com link de verificação se houver token
                if response_data and isinstance(response_data, dict) and 'verificationToken' in response_data:
                    token = response_data['verificationToken']
                    email_success, email_msg = EmailVerification.send_verification_email(email, token, user_name)
                    if email_success:
                        logging.info("[OK] Email de verificação enviado para: %s", SecurityValidator.mask_email(email))
                    else:
                        logging.warning("[AVISO] Falha ao enviar email: %s", email_msg)
                
                sms_code, sms_message = SMSVerification.generate_sms_code(phone_number)

                if sms_code is None:
                    messagebox.showerror("Erro SMS", sms_message)
                    logging.error("[ERRO] Falha ao gerar código SMS para: %s", SecurityValidator.mask_phone(phone_number))
                    return

                self.show_phone_verification_view(email, phone_number, user_name)
            else:
                logging.warning("[AVISO] Registo falhou para: %s - %s", SecurityValidator.mask_email(email), message)
                messagebox.showerror("Erro", message)

        except Exception as e:
            logging.error("[ERRO] Exceção ao registar: %s", e)
            messagebox.showerror("Erro", f"Erro inesperado: {str(e)}")

    def show_phone_verification_view(self, email: str, phone_number: str, user_name: str):
        """Mostra tela de verificação por SMS."""
        self.clear_window()

        # Centralizar
        largura = WINDOW_WIDTH
        altura = WINDOW_HEIGHT
        self.root.update_idletasks()
        screen_largura = self.root.winfo_screenwidth()
        screen_altura = self.root.winfo_screenheight()
        x = (screen_largura // 2) - (largura // 2)
        y = (screen_altura // 2) - (altura // 2)
        self.root.geometry(f"{largura}x{altura}+{x}+{y}")

        main_container = tk.Frame(self.root, bg="#FFFFFF")
        main_container.pack(fill="both", expand=True)

        # Barra de Título
        barra_topo = tk.Frame(main_container, height=35, bg="white")
        barra_topo.pack(fill="x", side="top")

        barra_esquerda_topo = tk.Frame(barra_topo, bg="#2C2F33", width=210, height=35)
        barra_esquerda_topo.pack(side="left")
        barra_esquerda_topo.pack_propagate(False)

        barra_direita_topo = tk.Frame(barra_topo, bg="white", height=35)
        barra_direita_topo.pack(side="left", fill="both", expand=True)

        for frame in (barra_topo, barra_esquerda_topo, barra_direita_topo):
            frame.bind("<Button-1>", self.start_move)
            frame.bind("<B1-Motion>", self.mover_janela)

        btn_fechar = tk.Label(barra_direita_topo, text="✕", bg="white", fg="black", font=("Segoe UI", 11), width=4, cursor="hand2")
        btn_fechar.pack(side="right", fill="y")
        btn_fechar.bind("<Enter>", lambda e: btn_fechar.config(bg="#e5e5e5"))
        btn_fechar.bind("<Leave>", lambda e: btn_fechar.config(bg="white"))
        btn_fechar.bind("<Button-1>", lambda e: self.root.destroy())

        btn_min = tk.Label(barra_direita_topo, text="—", bg="white", fg="black", font=("Segoe UI", 11), width=4, cursor="hand2")
        btn_min.pack(side="right", fill="y")
        btn_min.bind("<Enter>", lambda e: btn_min.config(bg="#e5e5e5"))
        btn_min.bind("<Leave>", lambda e: btn_min.config(bg="white"))
        btn_min.bind("<Button-1>", lambda e: self.minimizar())

        content = tk.Frame(main_container, bg="#FFFFFF")
        content.pack(fill="both", expand=True)
        content.place(relx=0.5, rely=0.5, anchor="center")

        card = tk.Frame(content, bg="#FFFFFF")
        card.pack(padx=24, pady=24)

        header = tk.Frame(card, bg="#FFFFFF")
        header.pack(fill="x", padx=32, pady=(28, 12))

        tk.Label(header, text="Confirmar Telemóvel", font=("Segoe UI", 24, "bold"), 
                bg="#FFFFFF", fg=self.colors["text"]).pack(anchor="w", pady=(0, 4))

        info = tk.Label(header, text=f"Enviámos um código SMS para\n{SMSVerification.format_phone_display(phone_number)}", 
                       font=("Segoe UI", 11), bg="#FFFFFF", fg=self.colors["muted"], justify="left")
        info.pack(anchor="w")

        form = tk.Frame(card, bg="#FFFFFF")
        form.pack(fill="x", padx=32, pady=(8, 20))

        tk.Label(form, text="Código SMS (6 dígitos)", font=("Segoe UI", 11, "bold"), 
                bg="#FFFFFF", fg=self.colors["text"]).pack(anchor="w")
        sms_code_entry = tk.Entry(form, width=20, font=("Segoe UI", 16), justify="center", relief="flat", 
                                 highlightthickness=1, highlightbackground=self.colors["border"], highlightcolor=self.colors["primary"])
        sms_code_entry.pack(fill="x", pady=(6, 16), ipady=6)

        def verify_sms():
            sms_code = sms_code_entry.get()
            if not sms_code or len(sms_code) != 6:
                messagebox.showerror("Erro", "Insira um código com 6 dígitos!")
                return

            success, message = SMSVerification.verify_sms_code(phone_number, sms_code)

            if success:
                verify_success, verify_message = self.local_auth.verify_phone(email)
                email_success, email_message = EmailVerification.send_confirmation_email(email, user_name)
                info_lines = ["Telemóvel confirmado com sucesso!"]
                if verify_success and verify_message:
                    info_lines.append(verify_message)
                if email_success:
                    info_lines.append("Email informativo enviado.")
                else:
                    info_lines.append(f"Email não enviado: {email_message}")
                messagebox.showinfo("Sucesso", "\n".join(info_lines))
                logging.info("[OK] Telemóvel verificado para: %s", email)
                self.show_login_view()
            else:
                messagebox.showerror("Erro", message)
                logging.warning("[AVISO] Verificação SMS falhou para %s", email)

        def resend_sms():
            success, message = SMSVerification.resend_sms_code(phone_number)
            if success:
                messagebox.showinfo("Sucesso", message)
            else:
                messagebox.showerror("Erro", message)

        verify_btn = tk.Button(form, text="Verificar Código", command=verify_sms, bg=self.colors["primary"], 
                              fg="white", activebackground=self.colors["primary"], activeforeground="white", relief="flat", cursor="hand2", padx=18, pady=10)
        verify_btn.pack(fill="x")

        resend_btn = tk.Button(form, text="Reenviar Código", command=resend_sms, bg="#FFFFFF", 
                              fg=self.colors["text"], activebackground="#FFFFFF", activeforeground=self.colors["text"], relief="flat", cursor="hand2", pady=6)
        resend_btn.pack(fill="x", pady=(8, 0))

        back_btn = tk.Button(form, text="Voltar", command=self.show_login_view, bg="#FFFFFF", 
                            fg=self.colors["primary"], activebackground="#FFFFFF", activeforeground=self.colors["primary"], relief="flat", cursor="hand2", pady=6)
        back_btn.pack(pady=(8, 0))
