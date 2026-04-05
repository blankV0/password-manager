import string
import tkinter as tk


class verificador(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg="white")

        #os estilos visuais
        self.label_style = {"font": ("Segoe UI", 8, "bold"), "bg": "white", "fg": "#999"}
        self.input_style = {"font": ("Segoe UI", 10), "bg": "#F8F9FA", "relief": "flat"}
        self.btn_preto = {"bg": "#2C2F33", "fg": "white", "activebackground": "#23272A", "font": ("Segoe UI", 8, "bold"), "relief": "flat", "cursor": "hand2"}

        #titulo
        tk.Label(self, text="ANÁLISE DE PASSWORDS", ** self.label_style).pack(anchor="w", pady=(0, 10))

        #frame de Entrada
        self.frame_input = tk.Frame(self, bg="white")
        self.frame_input.pack(fill="x", pady=(0, 5))

        self.barra1 = tk.Entry(self.frame_input, **self.input_style, show="*") #campo do texto com a senha escondida
        self.barra1.pack(side="left", fill="x", expand=True, ipady=8)

        #botao ver
        self.btn_ver = tk.Button(self.frame_input, text="VER", **self.btn_preto, width=12)
        self.btn_ver.pack(side="right", padx=(5, 0), ipady=8)

        #botao para mostrar e esconder a senha
        self.btn_ver.bind("<ButtonPress-1>", lambda e: self.mostrar_senha()) #ao carregar mostra a senha
        self.btn_ver.bind("<ButtonRelease-1>", lambda e: self.ocultar_senha()) #ao largar esconde a senha

        self.barra1.bind("<KeyRelease>", lambda e: self.atualizar_tudo()) # atualiza conforme o tecla senao fica amostar a senha

        #barra de força
        self.canvas_barra = tk.Canvas(self, height=6, bg="#F1F3F5", highlightthickness=0)#o canvas para fazer a barra
        self.canvas_barra.pack(fill="x", pady=(10, 20))
        self.progresso = self.canvas_barra.create_rectangle(0, 0, 0, 6, fill="#E9ECEF", outline="") #barra inicial vazia

        # CHECKLIST
        self.requisitos = {
            "len": "Mínimo 12 caracteres",
            "upp": "Letra Maiúscula",
            "low": "Letra Minúscula",  
            "num": "Números",
            "sym": "Caracter Especial"
        }
        #textos
        self.labels_req = {}
        for key, texto in self.requisitos.items():
            lbl = tk.Label(self, text="• " + texto, font=("Segoe UI", 9), bg="white", fg="#999") # cria uma label para cada ponto
            lbl.pack(anchor="w", pady=2)
            self.labels_req[key] = lbl

    def mostrar_senha(self):
        self.barra1.config(show="") #para mostrar a senha

    def ocultar_senha(self):
        self.barra1.config(show="*") #para ocultar a senha

    def atualizar_tudo(self): 
        pwd = self.barra1.get() # ve o texto atual
        score = 0  #vai contar os criterios compridos

        #verificaçao
        checks = {
            "len": len(pwd) >= 12, #verificar o comprimento minimo (12 caracteres)
            "upp": any(c.isupper() for c in pwd), #verificar se tem maiusculas
            "low": any(c.islower() for c in pwd), #verifica se tem minusculas 
            "num": any(c.isdigit() for c in pwd), #verifica se tem numeros
            "sym": any(c in string.punctuation for c in pwd) # verificas os caracteres especiais
        }
        #confirmaçao
        for key, pronto in checks.items():
            cor = "#2EB872" if pronto else "#999" # verde se tiver em condicoes se nao fica cinza
            simbolo = "✓ " if pronto else "• " #certo para confirma e o ponto se nao confirmar nada
            self.labels_req[key].config(text=simbolo + self.requisitos[key], fg=cor)
            if pronto:
                score += 1 #recebe um ponto se comprir os criterios

        #as cores conforme os pontos
        cores = {0: "#E9ECEF", 1: "#FF4D4D", 2: "#FF4D4D", 3: "#FFA64D", 4: "#B2D33C", 5: "#2EB872"}
        cor_final = cores.get(score, "#E9ECEF") #recebe a cor conforme os pontos
        #barra
        self.update_idletasks() #atualiza a barra 
        largura_max = self.canvas_barra.winfo_width() # para ter a largura total da barra
        largura_barra = (min(score, 5) / 5) * largura_max  #calcula a largura da barra em questoes da pontuaçao

        self.canvas_barra.coords(self.progresso, 0, 0, largura_barra, 6) #atualiza o tamanho da barra
        self.canvas_barra.itemconfig(self.progresso, fill=cor_final) #para atualizar a cor da barra
