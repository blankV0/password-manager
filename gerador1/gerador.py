import random
import string
import tkinter as tk

class gerador(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg="white")

        #Estilos
        label_style = {"font": ("Segoe UI", 8, "bold"), "bg": "white", "fg": "#999"}
        input_style = {"font": ("Segoe UI", 10), "bg": "#F8F9FA", "relief": "flat", "justify": "center"}
        check_style = {"bg": "white", "font": ("Segoe UI", 9), "fg": "#444", "activebackground": "white", "cursor": "hand2"}

        #frame para agrupar as opções 
        frame_settings = tk.Frame(self, bg="white")
        frame_settings.pack(fill="x", pady=(0, 20))

        #configuraçao do comprimento da senha
        tk.Label(frame_settings, text=" TAMANHO", ** label_style).grid(row=0, column=0, sticky="w")
        self.barra_tamanho = tk.Entry(frame_settings, width=10, **input_style) # campo para o tamanho
        self.barra_tamanho.grid(row=1, column=0, pady=(5, 20), sticky="w", ipady=5)

        #configurraçao para quantas senhas vao ser geradas
        tk.Label(frame_settings, text="QUANTIDADE", ** label_style).grid(row=0, column=1, sticky="w", padx=(10, 0))
        self.barra_quantidade = tk.Entry(frame_settings, width=10, **input_style) # campo para a quantidade
        self.barra_quantidade.grid(row=1, column=1, pady=(5, 20), padx=(10, 0), sticky="w", ipady=5)

        #titulos dos caracteres 
        tk.Label(frame_settings, text="OPÇÕES", **label_style).grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 10))

        #frame para alinhar os quadrados(pontos)
        frame_checks = tk.Frame(frame_settings, bg="white")
        frame_checks.grid(row=3, column=0, columnspan=3, sticky="w")

        #variaveis booleanas para que caracterer incluir
        self.var_letras, self.var_numeros = tk.BooleanVar(value=True), tk.BooleanVar(value=True)
        self.var_simbolos, self.var_perigosos = tk.BooleanVar(value=True), tk.BooleanVar(value=True)

        #para ligar e desligar Letras, Números, Símbolos e Especiais
        tk.Checkbutton(frame_checks, text=" Letras (a-Z)", variable=self.var_letras, **check_style).grid(row=0, column=0, sticky="w", pady=2, padx=(0, 40))
        tk.Checkbutton(frame_checks, text=" Números (0-9)", variable=self.var_numeros, **check_style).grid(row=0, column=1, sticky="w", pady=2)
        tk.Checkbutton(frame_checks, text=" Símbolos (!@#)", variable=self.var_simbolos, **check_style).grid(row=1, column=0, sticky="w", pady=2, padx=(0, 40))
        tk.Checkbutton(frame_checks, text=" Evitar Caracteres Especiais", variable=self.var_perigosos, **check_style).grid(row=1, column=1, sticky="w", pady=2)

        #Password Unica
        tk.Label(self, text="PASSWORD ÚNICA", ** label_style).pack(anchor="w", pady=(10, 5))

        frame_unica_container = tk.Frame(self, bg="white")
        frame_unica_container.pack(fill="x", pady=(0, 20))

        #para ler e exibir a senha gerada
        self.var_unica = tk.StringVar(value="") # variavel para guardar o valor da senha
        self.entry_unica = tk.Entry(frame_unica_container, textvariable=self.var_unica, font=("Consolas", 11), bg="#F8F9FA", relief="flat", justify="center", state="readonly", readonlybackground="#F8F9FA")
        self.entry_unica.pack(side="left", fill="x", expand=True, padx=(0, 10), ipady=10)

        #botoes
        tk.Button(frame_unica_container, text="GERAR", command=self.gerar_uma_apenas, bg="#2C2F33", fg="white", font=("Segoe UI", 9, "bold"), padx=15, cursor="hand2", relief="flat").pack(side="left", ipady=6)
        tk.Button(frame_unica_container, text="COPIAR", command=self.copy_unica, bg="#E9ECEF", fg="#2C2F33", font=("Segoe UI", 9, "bold"), padx=15, cursor="hand2", relief="flat").pack(side="left", padx=(5, 0), ipady=6)

        #Varias Passwords
        tk.Label(self, text="VARIAS PASSWORDS", ** label_style).pack(anchor="w", pady=(10, 5))

        frame_lista_container = tk.Frame(self, bg="white")
        frame_lista_container.pack(fill="both", expand=True)

        # Scrollbar
        scroll = tk.Scrollbar(frame_lista_container)
        scroll.pack(side="right", fill="y")

        # Caixa de texto
        self.caixa_texto = tk.Text(frame_lista_container, height=6, width=50, yscrollcommand=scroll.set, font=("Consolas", 11), bg="#F8F9FA", relief="flat", padx=15, pady=15, state="disabled")
        self.caixa_texto.pack(side="left", fill="both", expand=True)
        scroll.config(command=self.caixa_texto.yview) # para ligar a scrollbar a caixa de texto

        #frame dos botoes da lista de senhas
        frame_acoes_lista = tk.Frame(self, bg="white")
        frame_acoes_lista.pack(fill="x", pady=15)

        #botoes gerar e copiar
        tk.Button(frame_acoes_lista, text="GERAR", command=self.gerar_gui, bg="#2C2F33", fg="white", font=("Segoe UI", 9, "bold"), padx=20, cursor="hand2", relief="flat").pack(side="left", ipady=8)
        tk.Button(frame_acoes_lista, text="COPIAR", command=self.copiar_texto, bg="#E9ECEF", fg="#2C2F33", font=("Segoe UI", 9, "bold"), padx=20, cursor="hand2", relief="flat").pack(side="left", padx=5, ipady=8)

    #funçao para gera a string aleatoria com base nos criterios escolhidos
    def gerar_password_logica(self, tamanho, q_letras, q_nums, q_syms, evitar):
        chars = "" #conjunto de caracteres premitidos
        if q_letras:
            chars += string.ascii_letters #adiciona maisculas e minusculas
        if q_nums:
            chars += string.digits #adiciona numeros de 0 a 9
        if q_syms:
            chars += string.punctuation # adiciona simbolos
        #remove caracteres que podem dar problemas
        if evitar:
            chars = ''.join(c for c in chars if c not in "\"'\\/|~`<>[]{}") # caractereres problematicos(pode ter mais)
        if not chars:
            return None
        return ''.join(random.choice(chars) for _ in range(tamanho)) #vai gerear aleatoriamente as senha com o tamanho escolhido

    # Gera uma unica senha
    def gerar_uma_apenas(self):
        try:
            val = self.barra_tamanho.get() #recebe o valor do tamanho
            tamanho = int(val) if val else 16 #usa 16 caracteres por defeito(ver isto depois)
        except:
            tamanho = 16  

        res = self.gerar_password_logica(tamanho, self.var_letras.get(), self.var_numeros.get(), self.var_simbolos.get(), self.var_perigosos.get())
        if res:
            self.entry_unica.config(state="normal")
            self.var_unica.set(res) # para inserir a senha gerada
            self.entry_unica.config(state="readonly") #

    #para copiar a senha
    def copy_unica(self):
        senha = self.var_unica.get() 
        if senha:
            self.master.clipboard_clear()
            self.master.clipboard_append(senha)

    # Gere as senhas e mete na caixa de texto
    def gerar_gui(self):
        try:
            t_val = self.barra_tamanho.get() # recebe o valor do tamanho
            q_val = self.barra_quantidade.get() # receber o valor da quantidade
            tamanho = int(t_val) if t_val else 16 #usa 16 caracteres por defeito(ver isto)
            quantidade = int(q_val) if q_val else 10 #usa 10 valor por defeito(ver isto)
        except:
            return #sai da funçao se os valores nao forem validos

        self.caixa_texto.config(state="normal") #ativa a caixa de texto
        self.caixa_texto.delete("1.0", tk.END)  #limpa resultados anteriores
        #gera as senhas (limite de 500 o senao da asneira)
        for _ in range(min(quantidade, 500)):
            res = self.gerar_password_logica(tamanho, self.var_letras.get(), self.var_numeros.get(), self.var_simbolos.get(), self.var_perigosos.get())#gera cada senha
            if res:
                self.caixa_texto.insert(tk.END, res + "\n")# insere as senhas na caixa de texto
        self.caixa_texto.config(state="disabled") #bloqeuia a pos gerar as senhas

    #copia toda a lista de passwords
    def copiar_texto(self):
        conteudo = self.caixa_texto.get("1.0", tk.END).strip() 
        if conteudo:
            self.master.clipboard_clear() #para limpar caixa de texto
            self.master.clipboard_append(conteudo) #para copiar a area de texto
