import tkinter as tk
import json
import string

#nome do ficheiro da bases de dados(Vai ser mudado depois)
FICHEIRO_PASSWORDS = "passwords.json"

#Classe inicio
class inicio(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg="white")
        self.master_app = master.master #pagina principal para andar pelas paginas

        #estilos dos títulos ,cartoes e botoes (o cartao tava a dar erros)
        self.titulo_style = {"font": ("Segoe UI", 16, "bold"), "bg": "white", "fg": "#2C2F33"}
        self.card_style = {"bg": "#F8F9FA", "padx": 20, "pady": 20, "highlightthickness": 1, "highlightbackground": "#E9ECEF"}
        self.btn_base = {"font": ("Segoe UI", 10, "bold"), "relief": "flat", "cursor": "hand2", "padx": 20}

        #ve a segurnaça ao anilisar o ficheiro json que ta no gerenciador
        total_pass, fracas, repetidas = self.analisar_gerenciador()

        #os textos que vao sendo atilizados conforme a segurança do gerenciador
        tk.Label(self, text="Bem-vindo de volta,", ** self.titulo_style).pack(anchor="w", pady=(20, 0))

        if total_pass == 0:
            sub_msg = "Ainda não tens passwords guardadas." # caso no tenha nada
        elif fracas > 0:
            sub_msg = "Tens passwords inseguras! Atualiza-as o mais rápido possível." #caso tenha senhas fracas
        elif repetidas > 0:
            sub_msg = "Tens passwords repetidas. Considera alterá-las." #caso tenha senhas repetidas
        else:
            sub_msg = "O teu gerenciador está protegido e atualizado." #quando esta tudo seguro

        tk.Label(self, text=sub_msg, font=("Segoe UI", 10), bg="white", fg="#999").pack(anchor="w", pady=(0, 30)) #mostra um mensagem de estado segurnça

        #Frame que mete os cartoes lado a lado
        frame_cards = tk.Frame(self, bg="white")
        frame_cards.pack(fill="x")

        #Mostra o número total de passwords adicionadas
        card1 = tk.Frame(frame_cards, **self.card_style)
        card1.pack(side="left", fill="both", expand=True, padx=(0, 10))
        tk.Label(card1, text="PASSWORDS GUARDADAS", font=("Segoe UI", 8, "bold"), bg="#F8F9FA", fg="#999").pack() #titulo do cartao
        tk.Label(card1, text=str(total_pass), font=("Segoe UI", 24, "bold"), bg="#F8F9FA", fg="#2C2F33").pack() #numero de senhas

        #Cartao que muda de cor e texto conforme a segurança do gerenciador
        card2 = tk.Frame(frame_cards, **self.card_style)
        card2.pack(side="left", fill="both", expand=True, padx=10)
        tk.Label(card2, text="ESTADO DO GERENCIADOR", font=("Segoe UI", 8, "bold"), bg="#F8F9FA", fg="#999").pack()#titulo do cartao

        #define as cores e mensagens com base nos riscos
        if total_pass == 0:
            estado_txt, estado_cor = "VAZIO", "#BBB"
            sub_texto, sub_cor = "", "#BBB"
        elif fracas > 0:
            #Prioridade para senhas inseguras
            estado_txt, estado_cor = "INSEGURO", "#FF4D4D"
            texto_unidade = "Password Insegura" if fracas == 1 else "Passwords Inseguras"
            sub_texto, sub_cor = f"{fracas} {texto_unidade}", "#FF4D4D"
        elif repetidas > 0:
            #Alerta para senhas iguais
            estado_txt, estado_cor = "ALERTA", "#FFA500"
            texto_unidade = "Password Repetida" if repetidas == 1 else "Passwords Repetidas"
            sub_texto, sub_cor = f"{repetidas} {texto_unidade}", "#FFA500"
        else:
            #se tiver tudo bem
            estado_txt, estado_cor = "SEGURO", "#2EB872"
            sub_texto, sub_cor = "Tudo Normal", "#2EB872"

        #mostra estado e o subtexto 
        tk.Label(card2, text=estado_txt, font=("Segoe UI", 18, "bold"), bg="#F8F9FA", fg=estado_cor).pack(pady=(5, 0))

        if sub_texto:
            tk.Label(card2, text=sub_texto, font=("Segoe UI", 7, "bold"), bg="#F8F9FA", fg=sub_cor).pack()

        #botoes para ir pa outros sitios
        tk.Label(self, text="AÇÕES RÁPIDAS", font=("Segoe UI", 8, "bold"), bg="white", fg="#999").pack(anchor="w", pady=(40, 10))

        #botao para o gerador
        tk.Button(self, text="GERAR NOVA PASSWORD", **self.btn_base, bg="#2C2F33", fg="white", command=lambda: self.master_app.mudar_tela("Gerador")).pack(fill="x", ipady=15, pady=5)

        #botao para o gerenciador
        tk.Button(self, text="ABRIR O GERENCIADOR", **self.btn_base, bg="#E9ECEF", fg="#2C2F33", command=lambda: self.master_app.mudar_tela("Gerenciador")).pack(fill="x", ipady=15, pady=5)

    #funçao para ver o ficheiro JSON para calcular o nivel segurança
    def analisar_gerenciador(self):
        try:
            with open(FICHEIRO_PASSWORDS, "r", encoding="utf-8") as f:
                dados = json.load(f) #carrega os dados do ficheiro
                total = len(dados) # conta o numero de contas

                fracas = 0 #contador de senhas fracas
                lista_passwords = [] #lista para guardar todas a senhas
                for item in dados:
                    p = item["password"] #vai estrair cada senha
                    lista_passwords.append(p) #adiciona a lista
                    #para ver a força: comprimento, numeros e símbolos
                    tem_num = any(c.isdigit() for c in p) #ve se tem numeros
                    tem_sym = any(c in string.punctuation for c in p) #ve se tem simbolos
                    if len(p) < 8 or not tem_num or not tem_sym:
                        fracas += 1 # aumenta um valor se a senha for fraca

                #ve se as senhas se repetem entre os diferentes serviços
                repetidas = 0 #contador de senhas repetidas
                for p in set(lista_passwords):  #ve a lista de senhas unicas
                    count = lista_passwords.count(p) # conta quantas vezes aparece
                    if count > 1:
                        repetidas += count #para adicionar ao contador as senhas repetidas

                return total, fracas, repetidas # devolve o que foi calculado
        except (FileNotFoundError, json.JSONDecodeError):
            #se o ficheiro nao tiver nada retorna como vazio
            return 0, 0, 0
