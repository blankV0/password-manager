import tkinter as tk
from tkinter import filedialog  # para abrir a seleção de ficheiro
from tkinter import messagebox
import json
import logging
import string


class utilizador(tk.Frame):
    def __init__(self, master, *, local_auth=None, master_password=""):
        super().__init__(master, bg="white")
        self.local_auth = local_auth
        self._master_password = master_password
        self._vault = None

        # estilos dos botoes
        self.btn_preto = {"bg": "#2C2F33", "fg": "white", "font": ("Segoe UI", 9, "bold"), "relief": "flat", "cursor": "hand2"}
        self.btn_cinza = {"bg": "#E9ECEF", "fg": "#2C2F33", "font": ("Segoe UI", 9, "bold"), "relief": "flat", "cursor": "hand2"}
        self.btn_vermelho = {"bg": "#FF4D4D", "fg": "white", "font": ("Segoe UI", 9, "bold"), "relief": "flat", "cursor": "hand2"}

        # Inicializar vault e obter estatísticas
        total, fracas, repetidas, forte = self._analisar_vault()

        # Estatísticas / cartões
        tk.Label(self, text="ESTATÍSTICAS", font=("Segoe UI", 8, "bold"), bg="white", fg="#999").pack(anchor="w", pady=(10, 8))

        frame_stats = tk.Frame(self, bg="white")
        frame_stats.pack(fill="x", pady=(0, 20))

        self._criar_card(frame_stats, "CONTAS", str(total), "#2C2F33", 0)
        self._criar_card(frame_stats, "SEGURAS", str(forte), "#2EB872", 1)
        self._criar_card(frame_stats, "INSEGURAS", str(fracas), "#FF4D4D", 2)
        self._criar_card(frame_stats, "REPETIDAS", str(repetidas), "#FFA64D", 3)

        for i in range(4):
            frame_stats.columnconfigure(i, weight=1)

        # Gestão de dados
        tk.Label(self, text="GESTÃO DE DADOS", font=("Segoe UI", 8, "bold"), bg="white", fg="#999").pack(anchor="w", pady=(0, 8))

        frame_gestao = tk.Frame(
            self, bg="white", highlightthickness=1, highlightbackground="#E9ECEF")
        frame_gestao.pack(fill="x", pady=(0, 20))

        self._criar_linha_acao(frame_gestao, "Exportar Gerenciador", "Exporta todas as passwords do gerenciador para um ficheiro JSON local.", "EXPORTAR", self.btn_preto, self.exportar)

        tk.Frame(frame_gestao, bg="#E9ECEF", height=1).pack(fill="x", padx=15)

        self._criar_linha_acao(frame_gestao, "Importar Gerenciador", "Importa passwords de um ficheiro JSON para o gerenciador.", "IMPORTAR", self.btn_cinza, self.importar)

        tk.Frame(frame_gestao, bg="#E9ECEF", height=1).pack(fill="x", padx=15)

        self._criar_linha_acao(frame_gestao, "Apagar Todos os Dados do Gerenciador", "Remove permanentemente todas as passwords guardadas no gerenciador.", "APAGAR TUDO", self.btn_vermelho, self.apagar_tudo)

    def _analisar_vault(self):
        """Analisa as entries do vault para calcular estatísticas."""
        if not self.local_auth or not self._master_password:
            return 0, 0, 0, 0

        try:
            from src.ui.vault_gui import VaultService
            self._vault = VaultService(self.local_auth, self._master_password)
            ok, msg = self._vault.initialize()
            if not ok:
                logging.warning("[UTILIZADOR] Vault init falhou: %s", msg)
                return 0, 0, 0, 0

            entries = self._vault.list_entries()
            total = len(entries)
            if total == 0:
                return 0, 0, 0, 0

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

            forte = total - fracas
            return total, fracas, repetidas, forte
        except Exception as e:
            logging.warning("[UTILIZADOR] Falha ao analisar vault: %s", e)
            return 0, 0, 0, 0

    # cartões
    def _criar_card(self, parent, titulo, valor, cor, coluna):
        card = tk.Frame(parent, bg="#F8F9FA", highlightthickness=1, highlightbackground="#E9ECEF")
        card.grid(row=0, column=coluna, padx=(0, 10) if coluna < 3 else 0, sticky="ew", ipady=10)

        tk.Label(card, text=titulo, font=("Segoe UI", 7, "bold"), bg="#F8F9FA", fg="#999").pack(pady=(10, 2))
        tk.Label(card, text=valor, font=("Segoe UI", 20, "bold"), bg="#F8F9FA", fg=cor).pack()
        tk.Label(card, text="", bg="#F8F9FA").pack(pady=(2, 8))

    # dados
    def _criar_linha_acao(self, parent, titulo, descricao, btn_texto, btn_style, comando):
        frame = tk.Frame(parent, bg="white")
        frame.pack(fill="x", padx=15, pady=12)

        tk.Label(frame, text=titulo, font=("Segoe UI", 10, "bold"), bg="white", fg="#2C2F33").pack(anchor="w")
        tk.Label(frame, text=descricao, font=("Segoe UI", 9), bg="white", fg="#999").pack(anchor="w", pady=(2, 8))
        tk.Button(frame, text=btn_texto, command=comando, **btn_style, padx=15, pady=6).pack(anchor="w")

    def exportar(self):
        """Exporta os dados do vault para um ficheiro JSON local."""
        if not self._vault:
            messagebox.showwarning("Aviso", "Gerenciador não inicializado.")
            return

        entries = self._vault.list_entries()
        if not entries:
            messagebox.showinfo("Aviso", "Não existem passwords para exportar.")
            return

        destino = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("Ficheiro JSON", "*.json")],
            title="Guardar cópia do gerenciador"
        )
        if destino:
            try:
                export_data = []
                for entry in entries:
                    export_data.append({
                        "site": entry.site,
                        "username": entry.username,
                        "password": entry.password,
                        "notes": entry.notes,
                    })
                with open(destino, "w", encoding="utf-8") as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
                messagebox.showinfo("Sucesso", "Gerenciador exportado com sucesso!")
            except Exception as e:
                messagebox.showerror("Erro", f"Não foi possível exportar: {e}")

    def importar(self):
        """Importa passwords de um ficheiro JSON para o vault."""
        if not self._vault:
            messagebox.showwarning("Aviso", "Gerenciador n\u00e3o inicializado.")
            return

        ficheiro = filedialog.askopenfilename(
            filetypes=[("Ficheiro JSON", "*.json")],
            title="Selecionar ficheiro para importar",
        )
        if not ficheiro:
            return

        try:
            with open(ficheiro, "r", encoding="utf-8") as f:
                dados = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            messagebox.showerror("Erro", "Ficheiro inv\u00e1lido. Deve ser um JSON v\u00e1lido.")
            return
        except Exception as e:
            messagebox.showerror("Erro", f"N\u00e3o foi poss\u00edvel ler o ficheiro: {e}")
            return

        if not isinstance(dados, list):
            messagebox.showerror("Erro", "Formato inv\u00e1lido. O ficheiro deve conter uma lista de entradas.")
            return

        if not dados:
            messagebox.showinfo("Aviso", "O ficheiro n\u00e3o cont\u00e9m entradas.")
            return

        # Validar estrutura
        campos_obrigatorios = {"site", "username", "password"}
        for i, item in enumerate(dados):
            if not isinstance(item, dict):
                messagebox.showerror("Erro", f"Entrada {i+1} inv\u00e1lida (n\u00e3o \u00e9 um objeto).")
                return
            faltam = campos_obrigatorios - set(item.keys())
            if faltam:
                messagebox.showerror("Erro", f"Entrada {i+1} sem campos: {', '.join(faltam)}")
                return

        confirm = messagebox.askyesno(
            "Importar",
            f"Importar {len(dados)} entrada(s) para o gerenciador?\n\n"
            "Entradas existentes N\u00c3O ser\u00e3o alteradas.",
        )
        if not confirm:
            return

        sucesso = 0
        erros = 0
        for item in dados:
            site = str(item.get("site", "")).strip()
            username = str(item.get("username", "")).strip()
            password = str(item.get("password", "")).strip()
            notes = str(item.get("notes", "")).strip()
            if not site or not username or not password:
                erros += 1
                continue
            result = self._vault.add_entry(site, username, password, notes)
            if result:
                sucesso += 1
            else:
                erros += 1

        msg = f"{sucesso} entrada(s) importada(s) com sucesso."
        if erros:
            msg += f"\n{erros} entrada(s) falharam."
        messagebox.showinfo("Import conclu\u00eddo", msg)
        logging.info("[UTILIZADOR] Import: %d sucesso, %d erros", sucesso, erros)

        # Refresh
        for w in self.winfo_children():
            w.destroy()
        self.__init__(self.master, local_auth=self.local_auth, master_password=self._master_password)

    def apagar_tudo(self):
        """Apaga TODAS as passwords do vault do utilizador atual (via API)."""
        if not self.local_auth:
            messagebox.showwarning("Aviso", "Não autenticado.")
            return

        confirm = messagebox.askyesno(
            "⚠ Apagar Tudo",
            "ATENÇÃO: Esta ação é IRREVERSÍVEL!\n\n"
            "Todas as passwords do gerenciador serão eliminadas permanentemente.\n\n"
            "Tens a certeza?",
        )
        if not confirm:
            return

        confirm2 = messagebox.askyesno(
            "Última Confirmação",
            "Esta é a última confirmação.\n\nApagar todas as passwords do gerenciador?",
        )
        if not confirm2:
            return

        try:
            result = self.local_auth.vault_delete_all_entries()
            msg = result.get("message", "Dados apagados.")
            messagebox.showinfo("Sucesso", msg)
            logging.info("[UTILIZADOR] Vault limpo: %s", msg)
            # Refresh stats - rebuild the page
            for w in self.winfo_children():
                w.destroy()
            self.__init__(self.master, local_auth=self.local_auth, master_password=self._master_password)
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao apagar: {e}")
