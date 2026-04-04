import tkinter as tk
from tkinter import filedialog #para abir a seleçao de ficheiro
import json
import shutil #para copiar ficheiros
import os #para ver se tem ficheiros
import string


class utilizador(tk.Frame):
    def __init__(self, master, caminho_ficheiro="passwords.json"):
        super().__init__(master, bg="white")
        self.caminho_ficheiro = caminho_ficheiro #guarda o caminho do ficheiro

        #estilos dos botoes
        self.btn_preto = {"bg": "#2C2F33", "fg": "white", "font": ("Segoe UI", 9, "bold"), "relief": "flat", "cursor": "hand2"}
        self.btn_cinza = {"bg": "#E9ECEF", "fg": "#2C2F33", "font": ("Segoe UI", 9, "bold"), "relief": "flat", "cursor": "hand2"}
        self.btn_vermelho = {"bg": "#FF4D4D", "fg": "white", "font": ("Segoe UI", 9, "bold"), "relief": "flat", "cursor": "hand2"}

        total, fracas, repetidas, forte = self.analisar_passwords() #faz como no inico mesma coisa

        #Estatiscas / cartoes 
        tk.Label(self, text="ESTATÍSTICAS", font=("Segoe UI", 8, "bold"), bg="white", fg="#999").pack(anchor="w", pady=(10, 8))

        frame_stats = tk.Frame(self, bg="white")
        frame_stats.pack(fill="x", pady=(0, 20))

        self._criar_card(frame_stats, "CONTAS", str(total), "#2C2F33", 0) #cartao total de contas
        self._criar_card(frame_stats, "SEGURAS", str(forte), "#2EB872", 1) #cartao de senhas seguras
        self._criar_card(frame_stats, "INSEGURAS", str(fracas), "#FF4D4D", 2) #cartao de senhas inseguras
        self._criar_card(frame_stats, "REPETIDAS", str(repetidas), "#FFA64D", 3) #cartoa de senhas iguais

        for i in range(4):
            frame_stats.columnconfigure(i, weight=1) # para os cortoes terem as medidas iguais

        #Gestao de dados
        tk.Label(self, text="GESTÃO DE DADOS", font=("Segoe UI", 8, "bold"), bg="white", fg="#999").pack(anchor="w", pady=(0, 8))

        frame_gestao = tk.Frame(
            self, bg="white", highlightthickness=1, highlightbackground="#E9ECEF")
        frame_gestao.pack(fill="x", pady=(0, 20))

        self._criar_linha_acao(frame_gestao, "Exportar Base de Dados", "Guarda uma cópia da base de dados no teu computador.", "EXPORTAR", self.btn_preto, self.exportar)

        tk.Frame(frame_gestao, bg="#E9ECEF", height=1).pack(fill="x", padx=15) # a linha para separar

        self._criar_linha_acao(frame_gestao, "Importar Base de Dados", "Substitui a base de dados atual por um ficheiro externo.", "IMPORTAR", self.btn_cinza, self.importar)

        tk.Frame(frame_gestao, bg="#E9ECEF", height=1).pack(fill="x", padx=15) # a linha para separar

        self._criar_linha_acao(frame_gestao, "Apagar Todos os Dados", "Remove permanentemente todas as passwords guardadas.", "APAGAR", self.btn_vermelho, self.apagar_tudo)

    #cartoes
    def _criar_card(self, parent, titulo, valor, cor, coluna):
        card = tk.Frame(parent, bg="#F8F9FA", highlightthickness=1, highlightbackground="#E9ECEF")
        card.grid(row=0, column=coluna, padx=(0, 10) if coluna < 3 else 0, sticky="ew", ipady=10) #para posicionar o cartao na grelha

        tk.Label(card, text=titulo, font=("Segoe UI", 7, "bold"), bg="#F8F9FA", fg="#999").pack(pady=(10, 2)) #titulo do cartao
        tk.Label(card, text=valor, font=("Segoe UI", 20, "bold"), bg="#F8F9FA", fg=cor).pack() # valor do cartao
        tk.Label(card, text="", bg="#F8F9FA").pack(pady=(2, 8)) 
    #dados
    def _criar_linha_acao(self, parent, titulo, descricao, btn_texto, btn_style, comando):
        frame = tk.Frame(parent, bg="white")
        frame.pack(fill="x", padx=15, pady=12)

        tk.Label(frame, text=titulo, font=("Segoe UI", 10, "bold"), bg="white", fg="#2C2F33").pack(anchor="w") # titulo
        tk.Label(frame, text=descricao, font=("Segoe UI", 9), bg="white", fg="#999").pack(anchor="w", pady=(2, 8)) #descriçao
        tk.Button(frame, text=btn_texto, command=comando, **btn_style, padx=15, pady=6).pack(anchor="w")#botoes

    #Avisos(Cuidado deu so problemas mais valia ter feito a parte)
    def setup_move(self, window, widget):
        def start_move(event):
            window.offset_x = event.x_root - window.winfo_x() #calcula quando mexe horizontals
            window.offset_y = event.y_root - window.winfo_y() #calcula a quando mexe vertical

        def do_move(event):
            window.geometry(f"+{event.x_root - window.offset_x}+{event.y_root - window.offset_y}") #mover a janela com rato
        widget.bind("<Button-1>", start_move) #quando clica ele ja se pode mexer
        widget.bind("<B1-Motion>", do_move) #ao mexer o rato a janela mexe 

    def aviso(self, titulo, mensagem):
        janela = tk.Toplevel(self)#cria uma janela
        janela.overrideredirect(True) #remove as bordas padrao da janela
        w, h = 320, 160 #dimençoes da janela 
        sw, sh = janela.winfo_screenwidth(), janela.winfo_screenheight() #ve as dimensoes do ecra
        janela.geometry(f"{w}x{h}+{(sw//2)-(w//2)}+{(sh//2)-(h//2)}") #centra conforme o ecra
        janela.config(bg="white", highlightthickness=1, highlightbackground="#E9ECEF")
        janela.grab_set()
        container = tk.Frame(janela, bg="white", padx=25, pady=25)
        container.pack(fill="both", expand=True)
        self.setup_move(janela, container) #premite mexer a janela
        tk.Label(container, text=titulo, font=("Segoe UI", 10, "bold"), bg="white", fg="#2C2F33").pack(anchor="w")# titulo do aviso
        tk.Label(container, text=mensagem, font=("Segoe UI", 9), bg="white", fg="#666", wraplength=250, justify="left").pack(anchor="w", pady=10) #mensagem
        tk.Button(container, text="OK", command=janela.destroy, **self.btn_preto, width=10).pack(side="bottom", anchor="e") #botao para fechar

    def confirmar(self, titulo, mensagem, callback):
        janela = tk.Toplevel(self)#cria uma janela
        janela.overrideredirect(True)#remove as bordas da janela
        w, h = 350, 180 #tamanho da janela
        sw, sh = janela.winfo_screenwidth(), janela.winfo_screenheight()#ve as dimensoes do ecra
        janela.geometry(f"{w}x{h}+{(sw//2)-(w//2)}+{(sh//2)-(h//2)}")#centra conforme o ecra
        janela.config(bg="white", highlightthickness=1, highlightbackground="#E9ECEF")
        janela.grab_set() 
        container = tk.Frame(janela, bg="white", padx=25, pady=25)
        container.pack(fill="both", expand=True)
        self.setup_move(janela, container)#premite mexer a janela
        tk.Label(container, text=titulo, font=("Segoe UI", 10, "bold"), bg="white", fg="#2C2F33").pack(anchor="w") #titulo 
        tk.Label(container, text=mensagem, font=("Segoe UI", 9), bg="white", fg="#666", wraplength=280, justify="left").pack(anchor="w", pady=(10, 20)) #mensagem
        btn_frame = tk.Frame(container, bg="white")
        btn_frame.pack(side="bottom", fill="x")

        def acao_sim():
            janela.destroy() #fechar a janela
            callback()#executa a açao
        tk.Button(btn_frame, text="SIM", command=acao_sim, **self.btn_vermelho, width=10).pack(side="right", padx=5) #botao para confirmar
        tk.Button(btn_frame, text="NÃO", command=janela.destroy, **self.btn_cinza, width=10).pack(side="right") #botao para cancelar

    #analisa as senhas
    def analisar_passwords(self):
        try:
            with open(self.caminho_ficheiro, "r", encoding="utf-8") as f:
                dados = json.load(f) # carrega os dados do ficheiro 
            if not isinstance(dados, list):
                return 0, 0, 0, 0 #devovle zero se nao tiver nada no ficheiro
            total = len(dados) #conta o total de contas
            lista_pass = [item["password"] for item in dados] #extrais as senhas
            fracas = sum(
                1 for p in lista_pass
                if len(p) < 8 or not any(c.isdigit() for c in p)
                or not any(c in string.punctuation for c in p) # ve os criteiros de força
            )
            repetidas = sum(lista_pass.count(p) for p in set(lista_pass) if lista_pass.count(p) > 1)# ve as senhas repetidas
            forte = total - fracas
            return total, fracas, repetidas, forte
        except:
            return 0, 0, 0, 0 #devolve zeros se der algum erro

    def exportar(self):
        if not os.path.exists(self.caminho_ficheiro):
            self.aviso("AVISO", "Não existe nenhuma base de dados para exportar.")
            return #sai se o ficheiro nao exixtir
        destino = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("Ficheiro JSON", "*.json")],
            title="Guardar cópia"
        )# abre a janela para escolher onde guardar
        if destino:
            try:
                shutil.copy2(self.caminho_ficheiro, destino) #copia o ficheiro para o sitio escolhido
                self.aviso("SUCESSO", "Base de dados exportada com sucesso!")
            except Exception as e: 
                self.aviso("ERRO", f"Não foi possível exportar: {e}") # mostra o erro se a copia falhar

    def importar(self):
        origem = filedialog.askopenfilename(         # abre a janela para escolher o ficheiro
            filetypes=[("Ficheiro JSON", "*.json")],
            title="Selecionar ficheiro"
        ) 
        if not origem:
            return # sai se nao tiver escolhido nehum ficheiro
        try:
            with open(origem, "r", encoding="utf-8") as f:
                dados = json.load(f) #le o ficheiro selecionado
            if not isinstance(dados, list):
                self.aviso("ERRO", "O ficheiro selecionado não é válido.")
                return #sai se o ficheiro nao for valido

            def fazer_importacao():
                shutil.copy2(origem, self.caminho_ficheiro) #subestitui a base dados pela escolhida
                self.aviso("SUCESSO", "Base de dados importada com sucesso!")
            self.confirmar("IMPORTAR", "Isto irá substituir todos os dados atuais. Tens a certeza?", fazer_importacao)
        except Exception as e:
            self.aviso("ERRO", f"Não foi possível importar: {e}") #mostra o erro se falahar a importaçao

    def apagar_tudo(self):
        if not os.path.exists(self.caminho_ficheiro):
            self.aviso("AVISO", "Não existe nenhuma base de dados para apagar.")
            return #sai caso o ficheiro nao exixta

        def fazer_apagar():
            try:
                with open(self.caminho_ficheiro, "w", encoding="utf-8") as f:
                    json.dump([], f) #subestitui o conteudo por uma lista vazia
                self.aviso("SUCESSO", "Todos os dados foram apagados.")
            except Exception as e:
                self.aviso("ERRO", f"Não foi possível apagar: {e}") #mostra erro se o apaga nao funcionar
        self.confirmar("APAGAR TUDO", "Esta ação é irreversível. Todos os dados serão eliminados permanentemente. Tens a certeza?", fazer_apagar)
