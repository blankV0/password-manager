import tkinter as tk
import logging
import string


#Classe inicio
class inicio(tk.Frame):
    def __init__(self, master, *, local_auth=None, master_password=""):
        super().__init__(master, bg="white")
        self.master_app = master.master  # pagina principal para andar pelas paginas
        self.local_auth = local_auth
        self._master_password = master_password

        #estilos dos títulos, cartoes e botoes
        self.titulo_style = {"font": ("Segoe UI", 16, "bold"), "bg": "white", "fg": "#2C2F33"}
        self.card_style = {"bg": "#F8F9FA", "padx": 20, "pady": 20, "highlightthickness": 1, "highlightbackground": "#E9ECEF"}
        self.btn_base = {"font": ("Segoe UI", 10, "bold"), "relief": "flat", "cursor": "hand2", "padx": 20}

        # Analisa dados do vault
        total_pass, fracas, repetidas = self._analisar_vault()

        # Mensagem de boas-vindas
        tk.Label(self, text="Bem-vindo de volta,", **self.titulo_style).pack(anchor="w", pady=(20, 0))

        if total_pass == 0:
            sub_msg = "Ainda não tens passwords guardadas."
        elif fracas > 0:
            sub_msg = "Tens passwords inseguras! Atualiza-as o mais rápido possível."
        elif repetidas > 0:
            sub_msg = "Tens passwords repetidas. Considera alterá-las."
        else:
            sub_msg = "O teu vault está protegido e atualizado."

        tk.Label(self, text=sub_msg, font=("Segoe UI", 10), bg="white", fg="#999").pack(anchor="w", pady=(0, 30))

        # Frame dos cartoes
        frame_cards = tk.Frame(self, bg="white")
        frame_cards.pack(fill="x")

        # Cartao 1: total de passwords
        card1 = tk.Frame(frame_cards, **self.card_style)
        card1.pack(side="left", fill="both", expand=True, padx=(0, 10))
        tk.Label(card1, text="PASSWORDS GUARDADAS", font=("Segoe UI", 8, "bold"), bg="#F8F9FA", fg="#999").pack()
        tk.Label(card1, text=str(total_pass), font=("Segoe UI", 24, "bold"), bg="#F8F9FA", fg="#2C2F33").pack()

        # Cartao 2: estado do vault
        card2 = tk.Frame(frame_cards, **self.card_style)
        card2.pack(side="left", fill="both", expand=True, padx=10)
        tk.Label(card2, text="ESTADO DO VAULT", font=("Segoe UI", 8, "bold"), bg="#F8F9FA", fg="#999").pack()

        if total_pass == 0:
            estado_txt, estado_cor = "VAZIO", "#BBB"
            sub_texto, sub_cor = "", "#BBB"
        elif fracas > 0:
            estado_txt, estado_cor = "INSEGURO", "#FF4D4D"
            texto_unidade = "Password Insegura" if fracas == 1 else "Passwords Inseguras"
            sub_texto, sub_cor = f"{fracas} {texto_unidade}", "#FF4D4D"
        elif repetidas > 0:
            estado_txt, estado_cor = "ALERTA", "#FFA500"
            texto_unidade = "Password Repetida" if repetidas == 1 else "Passwords Repetidas"
            sub_texto, sub_cor = f"{repetidas} {texto_unidade}", "#FFA500"
        else:
            estado_txt, estado_cor = "SEGURO", "#2EB872"
            sub_texto, sub_cor = "Tudo Normal", "#2EB872"

        tk.Label(card2, text=estado_txt, font=("Segoe UI", 18, "bold"), bg="#F8F9FA", fg=estado_cor).pack(pady=(5, 0))
        if sub_texto:
            tk.Label(card2, text=sub_texto, font=("Segoe UI", 7, "bold"), bg="#F8F9FA", fg=sub_cor).pack()

        # Acoes rapidas
        tk.Label(self, text="AÇÕES RÁPIDAS", font=("Segoe UI", 8, "bold"), bg="white", fg="#999").pack(anchor="w", pady=(40, 10))

        tk.Button(self, text="GERAR NOVA PASSWORD", **self.btn_base, bg="#2C2F33", fg="white",
                  command=lambda: self.master_app.mudar_tela("Gerador")).pack(fill="x", ipady=15, pady=5)

        tk.Button(self, text="ABRIR O VAULT", **self.btn_base, bg="#E9ECEF", fg="#2C2F33",
                  command=lambda: self.master_app.mudar_tela("Vault")).pack(fill="x", ipady=15, pady=5)

    def _analisar_vault(self):
        """Analisa as entries do vault para calcular estatísticas de segurança."""
        if not self.local_auth or not self._master_password:
            return 0, 0, 0

        try:
            from src.ui.vault_gui import VaultService
            vault = VaultService(self.local_auth, self._master_password)
            ok, msg = vault.initialize()
            if not ok:
                logging.warning("[INICIO] Vault init falhou: %s", msg)
                return 0, 0, 0

            entries = vault.list_entries()
            total = len(entries)
            if total == 0:
                return 0, 0, 0

            fracas = 0
            lista_passwords = []
            for entry in entries:
                p = entry.password
                if p:
                    lista_passwords.append(p)
                    tem_num = any(c.isdigit() for c in p)
                    tem_sym = any(c in string.punctuation for c in p)
                    if len(p) < 8 or not tem_num or not tem_sym:
                        fracas += 1

            repetidas = 0
            for p in set(lista_passwords):
                count = lista_passwords.count(p)
                if count > 1:
                    repetidas += count

            return total, fracas, repetidas
        except Exception as e:
            logging.warning("[INICIO] Falha ao analisar vault: %s", e)
            return 0, 0, 0
