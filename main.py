"""Password Manager — ponto de entrada da aplicação desktop.

Fluxo completo: Login → Dashboard (Gerenciador, Gerador, Verificador, etc.)

Lança uma GUI Tkinter que disponibiliza:

* Autenticação (login / registo) via servidor de auth self-hosted
* Dashboard com sidebar integrando gerador, gerenciador, verificador
  e módulos de políticas (pacote ``gerador1``)
* Dark theme com title bar customizada (Windows)

Usage::

    python main.py
"""

from __future__ import annotations

import sys
import logging
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
import ctypes

# Setup do ambiente
def _setup_environment() -> Path:
    project_root = Path(__file__).resolve().parent
    return project_root


app_root = _setup_environment()
sys.path.insert(0, str(app_root))
sys.path.insert(0, str(app_root / "gerador1"))

from src.config.settings import APP_LOG_FILE
from src.utils.logging_config import configure_logging
from src.ui.login_gui import LoginApp

# Importar componentes do colega
from gerador1.inicio import inicio
from gerador1.gerador import gerador
from gerador1.verificador import verificador
from gerador1.utilizador import utilizador
from gerador1.politicas import politicas

from src.ui.settings_page import SettingsPage, get_theme_colors, _load_prefs, apply_theme_recursive
from src.ui.admin_panel import AdminPanel
from src.models.local_auth import LocalAuth
from src.ui.vault_gui import VaultPage


class AppController:
    """Controla o ciclo de vida LoginApp <-> Dashboard."""

    def __init__(self, root: tk.Tk, logger: logging.Logger) -> None:
        self.root = root
        self.logger = logger
        self._titlebar_removed = False
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._drag_hwnd = 0
        
        # Forçar composição DWM (layered window) — impede ecrã preto
        # durante drag porque o Windows mantém um buffer off-screen.
        self.root.wm_attributes('-alpha', 0.99)
        
        # Remover titlebar nativa via Win32 uma única vez após a janela
        # estar totalmente criada.  Usamos after() em vez de <Map> para
        # evitar re-aplicações repetidas de SWP_FRAMECHANGED.
        if sys.platform == "win32":
            self.root.after(150, self._remove_native_titlebar)
            # Safety net: se o Windows restaurar a titlebar (ex: restore
            # de minimize), re-aplicamos — mas SÓ se necessário.
            self.root.bind("<Map>", self._on_map)
        
        # Configurar tamanho e posição
        self._setup_window()
        
        self.login_app: LoginApp | None = None
        self.dashboard: Dashboard | None = None
        
        self._open_login_window()

    def _on_map(self, event=None) -> None:
        """Safety net: re-aplica remoção do titlebar se o Windows a restaurou.

        Só actua se a flag _titlebar_removed já estiver True (ou seja, já
        removemos antes) E o estilo actual ainda tiver WS_CAPTION.
        """
        if sys.platform != "win32" or not self._titlebar_removed:
            return
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if not hwnd:
                hwnd = self.root.winfo_id()
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -16)
            if style & 0x00C00000:  # WS_CAPTION voltou — re-aplicar
                self.root.after_idle(self._remove_native_titlebar)
        except Exception:
            pass

    def _remove_native_titlebar(self) -> None:
        """Remove o titlebar nativo do Windows via Win32 GWL_STYLE.

        A janela fica sem decorações mas continua a ser WS_OVERLAPPEDWINDOW
        — aparece SEMPRE na taskbar, iconify() funciona normalmente,
        sem nenhum hack de overrideredirect.
        """
        if sys.platform != "win32":
            return
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if not hwnd:
                hwnd = self.root.winfo_id()
            GWL_STYLE     = -16
            GWL_EXSTYLE   = -20
            WS_CAPTION    = 0x00C00000  # titlebar
            WS_THICKFRAME = 0x00040000  # borda de resize
            WS_EX_COMPOSITED = 0x02000000  # double-buffer todos os filhos
            
            # Remover titlebar e borda de resize
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
            new_style = style & ~(WS_CAPTION | WS_THICKFRAME)
            if new_style != style:
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, new_style)
            
            # Ativar WS_EX_COMPOSITED — double-buffering nativo do Windows.
            # Todos os widgets filhos são desenhados num buffer off-screen
            # antes de serem mostrados, eliminando o flash preto entre
            # WM_ERASEBKGND e WM_PAINT durante o movimento.
            ex_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            new_ex = ex_style | WS_EX_COMPOSITED
            if new_ex != ex_style:
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_ex)
            
            # Aplicar todas as mudanças de estilo
            # SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED
            ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0027)
            self._titlebar_removed = True
            self.root.update_idletasks()
            self.logger.info("[APP] Titlebar removida + WS_EX_COMPOSITED ativado")
        except Exception as exc:
            self.logger.warning("[AVISO] Não foi possível remover titlebar: %s", exc)

    def _setup_window(self) -> None:
        """Configura o tamanho e posição da janela."""
        largura = 1200
        altura = 800
        self.root.update_idletasks()
        screen_largura = self.root.winfo_screenwidth()
        screen_altura = self.root.winfo_screenheight()
        x = (screen_largura // 2) - (largura // 2)
        y = (screen_altura // 2) - (altura // 2)
        self.root.geometry(f"{largura}x{altura}+{x}+{y}")

    def _shutdown(self) -> None:
        self.logger.info("[APP] Encerrando aplicação.")
        self.root.quit()
        self.root.destroy()

    def _open_login_window(self) -> None:
        """Abre a janela de login."""
        try:
            # Limpa qualquer dashboard anterior
            for widget in self.root.winfo_children():
                widget.destroy()
            
            self.login_app = LoginApp(self.root, on_login_success=self._on_login_success)
            self.logger.info("[APP] LoginApp aberta.")
        except Exception as exc:
            self.logger.error("[ERRO] Não foi possível abrir LoginApp: %s", exc)
            messagebox.showerror(
                "Erro ao iniciar",
                "Não foi possível abrir a janela de login.\n\n"
                f"Detalhe: {exc}",
            )
            self._shutdown()

    def _on_login_success(self, access_token: str) -> None:
        """Chamado após login bem-sucedido. Mostra o Dashboard."""
        try:
            self.logger.info("[APP] Login bem-sucedido. Abrindo Dashboard...")
            
            # Remove o login
            for widget in self.root.winfo_children():
                widget.destroy()
            
            # Guardar referência ao local_auth do LoginApp (tem tokens/role)
            self._local_auth = self.login_app.local_auth if self.login_app else LocalAuth()
            # Guardar master password para vault (KEK derivation)
            self._master_password = getattr(self.login_app, '_vault_master_password', '') or ''
            self.login_app = None
            
            # Cria o dashboard
            self._show_dashboard(access_token)
        except Exception as exc:
            self.logger.error("[ERRO] Falha ao abrir Dashboard: %s", exc)
            messagebox.showerror(
                "Erro ao abrir Dashboard",
                "Não foi possível abrir o painel principal.\n\n"
                f"Detalhe: {exc}",
            )
            self._open_login_window()

    def _show_dashboard(self, access_token: str) -> None:
        """Mostra o dashboard com todas as funcionalidades."""
        # Carregar tema
        prefs = _load_prefs()
        tc = get_theme_colors(prefs.get("theme", "light"))
        
        # Criar barra superior
        barra_topo = tk.Frame(self.root, height=35, bg=tc["topbar"])
        barra_topo.pack(fill="x", side="top")
        barra_topo.pack_propagate(False)
        
        barra_esquerda_topo = tk.Frame(barra_topo, bg=tc["sidebar"], width=210, height=35)
        barra_esquerda_topo.pack(side="left")
        barra_esquerda_topo.pack_propagate(False)
        
        barra_direita_topo = tk.Frame(barra_topo, bg=tc["topbar"], height=35)
        barra_direita_topo.pack(side="left", fill="both", expand=True)
        
        # Drag nativo do Windows — instantâneo, sem qualquer delay.
        # Com WS_EX_COMPOSITED + -alpha 0.99, o DWM mantém um bitmap
        # cached da janela.  ReleaseCapture + WM_NCLBUTTONDOWN(HTCAPTION)
        # diz ao Windows: "arrasta esta janela".  O DWM move o bitmap
        # directamente no GPU — zero repaint do Tkinter necessário.
        def start_move(event):
            if sys.platform == "win32":
                hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
                if not hwnd:
                    hwnd = self.root.winfo_id()
                ctypes.windll.user32.ReleaseCapture()
                # WM_NCLBUTTONDOWN = 0x00A1, HTCAPTION = 2
                ctypes.windll.user32.SendMessageW(hwnd, 0x00A1, 2, 0)
        
        for frame in (barra_topo, barra_esquerda_topo, barra_direita_topo):
            frame.bind("<Button-1>", start_move)
        
        # Botão fechar
        hover_bg = tc["border"]
        btn_fechar = tk.Label(barra_direita_topo, text="✕", bg=tc["topbar"], fg=tc["topbar_text"],
                              font=("Segoe UI", 11), width=4, cursor="hand2")
        btn_fechar.pack(side="right", fill="y")
        btn_fechar.bind("<Enter>", lambda e: btn_fechar.config(bg="#e74c3c", fg="white"))
        btn_fechar.bind("<Leave>", lambda e: btn_fechar.config(bg=tc["topbar"], fg=tc["topbar_text"]))
        btn_fechar.bind("<Button-1>", lambda e: self._shutdown())
        
        # Botão minimizar
        btn_min = tk.Label(barra_direita_topo, text="—", bg=tc["topbar"], fg=tc["topbar_text"],
                           font=("Segoe UI", 11), width=4, cursor="hand2")
        btn_min.pack(side="right", fill="y")
        btn_min.bind("<Enter>", lambda e: btn_min.config(bg=hover_bg))
        btn_min.bind("<Leave>", lambda e: btn_min.config(bg=tc["topbar"], fg=tc["topbar_text"]))
        btn_min.bind("<Button-1>", lambda e: self._minimizar())
        
        # Área do dashboard
        dashboard_area = tk.Frame(self.root, bg=tc["bg"])
        dashboard_area.pack(fill="both", expand=True)
        
        # Criar Dashboard
        self.dashboard = Dashboard(
            dashboard_area, access_token, self._on_logout,
            local_auth=self._local_auth, theme_colors=tc,
            on_rebuild=lambda: self._rebuild_dashboard(access_token),
            master_password=self._master_password,
        )
        self.dashboard.pack(fill="both", expand=True)

    def _rebuild_dashboard(self, access_token: str) -> None:
        """Reconstrói o dashboard inteiro (ex: após trocar tema)."""
        for widget in self.root.winfo_children():
            widget.destroy()
        self._show_dashboard(access_token)

    def _minimizar(self) -> None:
        """Minimiza para a taskbar. O <Map> handler trata do restauro automaticamente."""
        self.root.iconify()

    def _on_logout(self) -> None:
        """Chamado quando o utilizador faz logout."""
        self.logger.info("[APP] Logout realizado. Voltando ao login.")
        # Limpar master password da memória
        self._master_password = ""
        self._open_login_window()


class Dashboard(tk.Frame):
    """Dashboard com navegação entre páginas."""

    def __init__(
        self,
        master,
        access_token: str,
        on_logout_callback,
        *,
        local_auth: LocalAuth | None = None,
        theme_colors: dict | None = None,
        on_rebuild=None,
        master_password: str = "",
    ):
        self.tc = theme_colors or get_theme_colors("light")
        super().__init__(master, bg=self.tc["bg"])
        self.access_token = access_token
        self.on_logout = on_logout_callback
        self.local_auth = local_auth or LocalAuth()
        self.on_rebuild = on_rebuild
        self._master_password = master_password
        self._active_btn: tk.Label | None = None
        
        # Sidebar
        self.sidebar = tk.Frame(self, bg=self.tc["sidebar"], width=210)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        
        # Logo
        self.logo = tk.Label(
            self.sidebar, text="Passwords :D", bg=self.tc["sidebar"], fg="#FFFFFF",
            font=("Segoe UI", 18, "bold"), anchor="w", padx=20, pady=15, cursor="hand2",
        )
        self.logo.pack(fill="x")
        self.logo.bind("<Button-1>", lambda e: self.mudar_tela("Inicio"))
        
        # Navegação principal
        self.criar_botao("\U0001f510  Vault", lambda: self.mudar_tela("Vault"))
        self.criar_botao("\U0001f511  Gerador", lambda: self.mudar_tela("Gerador"))
        self.criar_botao("\U0001f50d  Verificador", lambda: self.mudar_tela("Verificador"))
        
        # Espaçador flexível — empurra os botões abaixo para o fundo
        spacer = tk.Frame(self.sidebar, bg=self.tc["sidebar"])
        spacer.pack(fill="both", expand=True)
        
        # Botões inferiores
        self.criar_botao("👤  Utilizador", lambda: self.mudar_tela("Utilizador"))
        self.criar_botao("📜  Políticas", lambda: self.mudar_tela("Políticas"))
        self.criar_botao("⚙  Definições", lambda: self.mudar_tela("Definições"))
        
        # Botão admin — apenas visível para admins
        if self.local_auth.is_admin():
            self.criar_botao("🛡  Admin", lambda: self.mudar_tela("Admin"), destaque=True)
        
        # Logout
        self.criar_botao("🚪  Logout", self.on_logout, vermelho=True)
        
        # Container principal
        self.main_container = tk.Frame(self, bg=self.tc["bg"])
        self.main_container.pack(side="left", fill="both", expand=True, padx=40, pady=40)
        
        # Página inicial
        self.mudar_tela("Inicio")

    def mudar_tela(self, nome_tela: str) -> None:
        """Muda a tela exibida."""
        for widget in self.main_container.winfo_children():
            widget.destroy()
        
        # Título
        titulo = tk.Label(
            self.main_container, text=nome_tela,
            font=("Segoe UI", 24, "bold"),
            bg=self.tc["bg"], fg=self.tc["text"],
        )
        titulo.pack(anchor="w")
        
        # Separador
        tk.Frame(self.main_container, height=2, bg=self.tc["border"]).pack(fill="x", pady=10)
        
        # Conteúdo
        page = None
        if nome_tela == "Inicio":
            page = inicio(self.main_container)
        elif nome_tela == "Vault":
            page = VaultPage(
                self.main_container,
                local_auth=self.local_auth,
                master_password=self._master_password,
            )
        elif nome_tela == "Gerador":
            page = gerador(
                self.main_container,
                local_auth=self.local_auth,
                master_password=self._master_password,
            )
        elif nome_tela == "Verificador":
            page = verificador(self.main_container)
        elif nome_tela == "Utilizador":
            page = utilizador(self.main_container)
        elif nome_tela == "Políticas":
            page = politicas(self.main_container)
        elif nome_tela == "Definições":
            page = SettingsPage(
                self.main_container,
                on_theme_changed=self._on_theme_changed,
            )
        elif nome_tela == "Admin":
            page = AdminPanel(
                self.main_container,
                local_auth=self.local_auth,
            )

        if page is not None:
            page.pack(fill="both", expand=True)
            # Aplicar tema recursivamente a páginas do colega (gerador1)
            # que usam cores hardcoded — sem efeito no tema claro
            if nome_tela not in ("Definições", "Admin", "Vault"):
                apply_theme_recursive(page, self.tc)

    def _on_theme_changed(self, new_theme: str) -> None:
        """Callback chamado pela SettingsPage quando o tema muda."""
        if self.on_rebuild:
            self.on_rebuild()

    def criar_botao(self, texto: str, comando, vermelho: bool = False, destaque: bool = False) -> tk.Label:
        """Cria um botão no sidebar."""
        sidebar_bg = self.tc["sidebar"]
        if vermelho:
            cor_bg = "#FF4D4D"
            cor_fg = "white"
            cor_hover = "#E63B3B"
        elif destaque:
            cor_bg = sidebar_bg
            cor_fg = self.tc["accent"]
            cor_hover = "#393C43" if sidebar_bg == "#2C2F33" else "#2C2E33"
        else:
            cor_bg = sidebar_bg
            cor_fg = self.tc["sidebar_text"]
            cor_hover = "#393C43" if sidebar_bg == "#2C2F33" else "#2C2E33"
        
        btn = tk.Label(
            self.sidebar, text=texto, bg=cor_bg, fg=cor_fg,
            font=("Segoe UI", 11), anchor="w", padx=20, pady=12, cursor="hand2",
        )
        
        def on_enter(e):
            btn.config(bg=cor_hover, fg="white")
        
        def on_leave(e):
            btn.config(bg=cor_bg, fg=cor_fg)
        
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        btn.bind("<Button-1>", lambda e: comando())
        
        btn.pack(fill="x", side="top")
        return btn


def main() -> None:
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)

    configure_logging(APP_LOG_FILE, level=logging.INFO)
    boot_logger = configure_logging(
        log_dir / "boot.log",
        level=logging.INFO,
        logger_name="boot",
        add_console=True,
        propagate=False,
    )

    boot_logger.info("[BOOT] Iniciando Password Manager Unificado...")

    root = tk.Tk()
    root.title("Password Manager")
    AppController(root, boot_logger)
    root.mainloop()


if __name__ == "__main__":
    main()
