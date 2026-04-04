import tkinter as tk
from tkinter import ttk #treview
import json
import string

#ficheiro onde os dados serão guardados
FICHEIRO_PASSWORDS = "passwords.json"

# Classe do gerenciador
class gerenciador(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg="white")

        #estilos visuais para a tabela (Treeview)
        style = ttk.Style()
        style.theme_use("clam") #o tema visual da tabela
        style.configure("Treeview", background="#FFFFFF", foreground="#444", rowheight=40, fieldbackground="#FFFFFF", font=("Segoe UI", 10)) #estilo das linhas
        style.configure("Treeview.Heading", font=("Segoe UI", 8, "bold"), background="#F8F9FA", foreground="#999", relief="flat")# estirlo do cabecalho

        #frame tabela com borda cinza
        self.frame_tabela = tk.Frame(self, bg="white", highlightthickness=1, highlightbackground="#E9ECEF")
        self.frame_tabela.pack(fill="both", expand=True, pady=(10, 0))

        #scrollbar
        scroll = tk.Scrollbar(self.frame_tabela, orient="vertical", bg="#F8F9FA", bd=0, width=12)
        scroll.pack(side="right", fill="y")

        #titulos das colunas da tabela
        self.tabela = ttk.Treeview(self.frame_tabela, columns=("Serviço", "Utilizador", "Password"), show="headings", selectmode="browse", yscrollcommand=scroll.set)

        #cores para as senhas inseguras ou repetidas
        self.tabela.tag_configure("insegura", background="#FFD6D6") #vermelho para as senhas inseguras
        self.tabela.tag_configure("repetida", background="#FFE4B3") #laranjas para as senhas repetidas

        #titulos e alinhamento das colunas
        self.tabela.heading("Serviço", text="  SERVIÇO")
        self.tabela.heading("Utilizador", text="  UTILIZADOR/EMAIL")
        self.tabela.heading("Password", text="  PASSWORD")
        self.tabela.column("Serviço", width=150, anchor="w")
        self.tabela.column("Utilizador", width=250, anchor="w")
        self.tabela.column("Password", width=120, anchor="center")
        self.tabela.pack(fill="both", expand=True)
        scroll.config(command=self.tabela.yview) #para ter o scrol ligado a tabela

        #Botoes
        frame_botoes = tk.Frame(self, bg="white")
        frame_botoes.pack(fill="x", pady=20)

        #estilo para os botões
        self.btn_preto = {"bg": "#2C2F33", "fg": "white", "font": ("Segoe UI", 9, "bold"), "relief": "flat", "cursor": "hand2"}
        self.btn_cinza = {"bg": "#E9ECEF", "fg": "#2C2F33", "font": ("Segoe UI", 9, "bold"), "relief": "flat", "cursor": "hand2"}

        #botões da interface principal
        tk.Button(frame_botoes, text="ADICIONAR", command=self.janela_adicionar, **self.btn_preto, padx=20).pack(side="left", ipady=8) #abre o formulario para adicionar
        tk.Button(frame_botoes, text="EDITAR", command=self.janela_editar, **self.btn_preto, padx=20).pack(side="left", padx=10, ipady=8) #abre o formulario para editar
        tk.Button(frame_botoes, text="VER", command=self.mostrar_ou_ocultar, **self.btn_cinza, padx=25).pack(side="left", ipady=8)#para amostrar os detalhes da conta selecionada
        tk.Button(frame_botoes, text="APAGAR", command=self.apagar, **self.btn_cinza, padx=15).pack(side="left", padx=10, ipady=8)#apaga a conta escolhida

        self.atualizar()

    #Avisos(Cuidado deu so problemas mais valia ter feito a parte)(so piora mas agora fica assim)
    def setup_move(self, window, widget):
        def start_move(event):
            window.offset_x = event.x_root - window.winfo_x() #calcula quando mexe o rato na horizontal
            window.offset_y = event.y_root - window.winfo_y() #calcula quando mese o rato na vertical

        def do_move(event):
            window.geometry(f"+{event.x_root - window.offset_x}+{event.y_root - window.offset_y}") #move a janela quando se mexe rato
        widget.bind("<Button-1>", start_move)#quando se clica ja se pode mexer
        widget.bind("<B1-Motion>", do_move)#ao mexer o rato a janela mexe

    def mostrar_aviso(self, mensagem):
        aviso = tk.Toplevel(self) #cria uma janela
        aviso.overrideredirect(True)  # Remove bordas padrão
        w, h = 320, 160 #tamanho da janela
        ws, hs = aviso.winfo_screenwidth(), aviso.winfo_screenheight() #ve o tamanho do ecra
        aviso.geometry(f"{w}x{h}+{(ws//2)-(w//2)}+{(hs//2)-(h//2)}") #centra a janela com o ecra
        aviso.config(bg="white", highlightthickness=1, highlightbackground="#E9ECEF")
        aviso.grab_set()
        btn_x = tk.Label(aviso, text="✕", bg="white", font=("Segoe UI", 10), cursor="hand2") #botao fechar
        btn_x.place(x=290, y=5)
        btn_x.bind("<Button-1>", lambda e: aviso.destroy()) #fecha a janela ao carregar no x
        container = tk.Frame(aviso, bg="white", padx=25, pady=25)
        container.pack(fill="both", expand=True)
        self.setup_move(aviso, container) # premite mexer a janela
        tk.Label(container, text="AVISO", font=("Segoe UI", 10, "bold"), bg="white", fg="#2C2F33").pack(anchor="w") # titulo do aviso
        tk.Label(container, text=mensagem, font=("Segoe UI", 9), bg="white", fg="#666", wraplength=250, justify="left").pack(anchor="w", pady=10) #mensagem
        tk.Button(container, text="OK", command=aviso.destroy, **self.btn_preto, width=10).pack(side="bottom", anchor="e")#botao para fcehar

    def confirmar_acao(self, titulo, mensagem, callback):
        win = tk.Toplevel(self) #cria uma janela
        win.overrideredirect(True)#remove as bordas da janela
        w, h = 350, 180 #tamanho da janela
        ws, hs = win.winfo_screenwidth(), win.winfo_screenheight() #ve o tamanho do ecra
        win.geometry(f"{w}x{h}+{(ws//2)-(w//2)}+{(hs//2)-(h//2)}") # centra a janela no ecra
        win.config(bg="white", highlightthickness=1, highlightbackground="#E9ECEF")
        win.grab_set()
        btn_x = tk.Label(win, text="✕", bg="white", font=("Segoe UI", 10), cursor="hand2")
        btn_x.place(x=320, y=5)
        btn_x.bind("<Button-1>", lambda e: win.destroy()) #fecha a janela no x
        container = tk.Frame(win, bg="white", padx=25, pady=25)
        container.pack(fill="both", expand=True)
        self.setup_move(win, container) #premite arrastar a janela
        tk.Label(container, text=titulo, font=("Segoe UI", 10, "bold"), bg="white", fg="#2C2F33").pack(anchor="w") # titulo
        tk.Label(container, text=mensagem, font=("Segoe UI", 9), bg="white", fg="#666", wraplength=280, justify="left").pack(anchor="w", pady=(10, 20)) #mensagem
        btn_frame = tk.Frame(container, bg="white")
        btn_frame.pack(side="bottom", fill="x")

        def acao_sim():
            win.destroy() #fecha a janela
            callback() #executa a açao
        tk.Button(btn_frame, text="SIM", command=acao_sim, **self.btn_preto, width=10).pack(side="right", padx=5) #botao para confirmar
        tk.Button(btn_frame, text="NÃO", command=win.destroy, **self.btn_cinza, width=10).pack(side="right") #botao para cancelar

    #le as senhas guardadas no ficheiro 
    def ler(self):
        try:
            with open(FICHEIRO_PASSWORDS, "r", encoding="utf-8") as f:
                return json.load(f)#devovle os dados do ficheiro
        except:
            return []  #retorna lista vazia se o ficheiro não existir

    #escreve a lista de senhas no ficheiro 
    def escrever(self, lista):
        with open(FICHEIRO_PASSWORDS, "w", encoding="utf-8") as f:
            json.dump(lista, f, indent=4) #guardas os dados de maneira a facilitar a leitura

    #atualiza o conteúdo da tabela
    def atualizar(self):
        # Limpa a tabela atual
        for item in self.tabela.get_children():
            self.tabela.delete(item) #remove  linha que exixte
        dados = self.ler() #adiciona os dados atuais do ficheiro
        lista_pass = [item["password"] for item in dados] #estrai todas as senhas para ve se ta repetido

        for i, item in enumerate(dados):
            p = item["password"] #tem a senha de entrada atual
            #regras para validar se a senha é fraca
            is_weak = (len(p) < 8 or not any(c.isdigit() for c in p) or not any(c in string.punctuation for c in p))

            #atribui tags de cor conforme o estado da senha
            if is_weak:
                tags = ("insegura",) #tag vermelha inseguras
            elif lista_pass.count(p) > 1:
                tags = ("repetida",) #tag laranja repetidas
            else:
                tags = () #sem tag para seguras

            # Insere na tabela ocultando a password real com círculos
            self.tabela.insert("", "end", iid=i, values=(
                item["servico"].upper(), item["username"], "••••••••"), tags=tags)

    #atalho para adicionar 
    def janela_adicionar(self): self.abrir_form() #abre um formolario sem dados 

    #prepara os dados para editar e abre o formolario
    def janela_editar(self):
        sel = self.tabela.selection() #ve a linha selecionada
        if not sel:
            self.mostrar_aviso("Selecione uma linha na tabela para editar.")
            return #sai se nao tiver feito nada
        index = int(sel[0])
        self.abrir_form(edit_index=index, dados_iniciais=self.ler()[index]) #abre o formolario com os dados da lina

    #janela para adicionar, editar ou visualizar dados(a mesma coisa so que pior)
    def abrir_form(self, edit_index=None, dados_iniciais=None, modo_ver=False):
        win = tk.Toplevel(self) #cria a janela do formulario
        win.overrideredirect(True) #remove as bordas
        largura, altura = 350, 480 #tamanho da janela
        ws, hs = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"{largura}x{altura}+{(ws//2)-(largura//2)}+{(hs//2)-(altura//2)}") #centra a janela no ecra
        win.config(bg="white", highlightthickness=1, highlightbackground="#E9ECEF")
        win.grab_set()#foca na janela
        barra_topo = tk.Frame(win, bg="white", height=40)
        barra_topo.pack(fill="x")
        self.setup_move(win, barra_topo) #premite mexer na janela
        btn_x = tk.Label(barra_topo, text="✕", bg="white", fg="black", font=("Segoe UI", 11), width=4, cursor="hand2")#botao para fechar
        btn_x.pack(side="right", fill="y")
        btn_x.bind("<Button-1>", lambda e: win.destroy()) #fecha a janela ao clicar no x
        container = tk.Frame(win, bg="white", padx=30)
        container.pack(fill="both", expand=True)
        lbl_style = {"font": ("Segoe UI", 8, "bold"), "bg": "white", "fg": "#999"} #estilo do formolario
        ent_style = {"font": ("Segoe UI", 10), "bg": "#F8F9FA", "relief": "flat"} #estilo dos campos

        #efine os textos defenir ou nova
        titulo = "DETALHES" if modo_ver else ( "EDITAR CREDENCIAL" if dados_iniciais else "NOVA CREDENCIAL")
        tk.Label(container, text=titulo, font=("Segoe UI", 12, "bold"), bg="white", fg="#2C2F33").pack(pady=(0, 25))

        #campos do formulario (Serviço, Utilizador, Password)
        tk.Label(container, text="SERVIÇO", **lbl_style).pack(anchor="w")
        e_servico = tk.Entry(container, **ent_style) #campo de entrada do serviço
        e_servico.pack(fill="x", pady=(5, 15), ipady=10)

        tk.Label(container, text="UTILIZADOR / EMAIL", **lbl_style).pack(anchor="w")
        e_user = tk.Entry(container, **ent_style) #campo de entrada do utilizador
        e_user.pack(fill="x", pady=(5, 15), ipady=10)

        tk.Label(container, text="PASSWORD", **lbl_style).pack(anchor="w")
        e_pass = tk.Entry(container, **ent_style) #campoo de entrada da senha
        e_pass.pack(fill="x", pady=(5, 25), ipady=10)

        #preenche os campos se estiver em modo de edição ou visualização
        if dados_iniciais:
            e_servico.insert(0, dados_iniciais["servico"])
            e_user.insert(0, dados_iniciais["username"])
            e_pass.insert(0, dados_iniciais["password"])

        #se for pa ver fica bloqueado e adiciona um botao pa copiar
        if modo_ver:
            e_servico.config(state="readonly")
            e_user.config(state="readonly")
            e_pass.config(state="readonly")

            def copiar():
                self.clipboard_clear() #para limpar 
                self.clipboard_append(e_pass.get()) #para copiar os dados
            tk.Button(container, text="COPIAR PASSWORD", command=copiar, **self.btn_preto).pack(fill="x", ipady=12)
        else:
            #caso contrario pode se guardar(ver isto tava a dar problemas nao sei porque)
            def guardar():
                s, u, p = e_servico.get().strip(), e_user.get().strip(), e_pass.get().strip() #obetem os valore dos campos
                if s and u and p:
                    dados = self.ler() #carrega os dados atuais
                    if edit_index is not None:
                        dados[edit_index] = {"servico": s, "username": u, "password": p} #atualiza a entrada dos dados que ja exite
                    else:
                        dados.append(
                            {"servico": s, "username": u, "password": p})
                    self.escrever(dados)#guarda os dados no ficheiro
                    self.atualizar()#atualiza a tabela
                    win.destroy() #fecha o formulario
                else:
                    self.mostrar_aviso("Preencha todos os campos.")
            tk.Button(container, text="GUARDAR DADOS", command=guardar, **self.btn_preto).pack(fill="x", ipady=12)

    #gere a visualização segura dos dados de cada conta
    def mostrar_ou_ocultar(self):
        sel = self.tabela.selection() #obtem a linha que escolhemos
        if not sel:
            self.mostrar_aviso("Selecione uma conta para visualizar.")
            return #sai se nao for escolhido
        idx = int(sel[0])
        #pede confirmação antes de mostrar os dados 
        self.confirmar_acao("SEGURANÇA", "Deseja ver os detalhes desta conta?", lambda: self.abrir_form(dados_iniciais=self.ler()[idx], modo_ver=True))

    #remove uma conta selecionada depois de confirmar
    def apagar(self):
        sel = self.tabela.selection() #obetem a linha escolhida
        if not sel:
            self.mostrar_aviso("Selecione uma conta para apagar.")
            return #sai se nao houver escolha

        def realizar_exclusao():
            dados = self.ler()  #carrega os dados atuais
            dados.pop(int(sel[0])) #remove a entrada escolhida
            self.escrever(dados) #guarda os dados atualizados
            self.atualizar() #atualiza a tabela
        self.confirmar_acao("APAGAR CONTA", "Deseja apagar esta conta permanentemente?", realizar_exclusao)
