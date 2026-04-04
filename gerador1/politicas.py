import tkinter as tk

class politicas(tk.Frame): # Cria o frame da aba “Políticas” dentro da interface
    def __init__(self, master):
        super().__init__(master, bg="white")

        LARGURA_TEXTO = 800 # tamanho ate onde o texto vai

        #Scrollbar
        scrollbar = tk.Scrollbar(self, orient="vertical")#cria a a scrollbar na vertical
        scrollbar.pack(side="right", fill="y") #A barra fica na direita e ocupa altura toda
        
        #Canvas onde vamos meter a regras para que a scroll funcione
        canvas = tk.Canvas(self, bg="white", yscrollcommand=scrollbar.set, highlightthickness=0)#fundo branco conecta a scroll e remove as bordas do canvas
        canvas.pack(side="left", fill="both", expand=True) # posicona a esquerda da scroll e preenche a largura e altura disponbel

        scrollbar.config(command=canvas.yview)# faz a conecçao a scroll para que funcione ou seja quando mover move o conteudo

        interior = tk.Frame(canvas, bg="white")# frame onde vai conter o conteudo
        interior_id = canvas.create_window((0, 0), window=interior, anchor="nw")#para que o texto começe a esquerda do frame

        def on_configure(event): #para que scrollbar funcione em codiçoes quando adicionarmos mais informaçoes
            canvas.configure(scrollregion=canvas.bbox("all"))
        interior.bind("<Configure>", on_configure)

        def on_canvas_resize(event): # para que o o texto acompanhe a largura do canvas
            canvas.itemconfig(interior_id, width=event.width)
        canvas.bind("<Configure>", on_canvas_resize)

        def on_mousewheel(event): # para quando for rodar a rodinha do rato funcione
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        #Texto da introduçao
        intro_text = ("Para proteger os teus dados, esta aplicação segue políticas de segurança e privacidade claras. Lê as diretrizes abaixo para saberes como a tua informação é tratada.")
        tk.Label(interior, text=intro_text, font=("Segoe UI", 11, "italic"), bg="white", fg="#666", wraplength=LARGURA_TEXTO, justify="left").pack(anchor="w", padx=0, pady=(20, 15))

        #Lista da regras
        regras = [
            ("Armazenamento na Nuvem","As tuas credenciais são guardadas numa base de dados encriptada na nuvem, acessível apenas por dispositivos autorizados."),
            ("Criptografia e Privacidade","Todos os dados são protegidos por criptografia. Não partilhes ficheiros ou exportações da aplicação."),
            ("Requisitos de Password","As passwords devem cumprir os critérios do verificador para garantir proteção contra ataques comuns."),
            ("Boas Práticas","Evita reutilizar passwords em diferentes serviços. A aplicação ajuda-te a gerar chaves únicas e seguras."),
            ("Password Principal","A tua password é necessária para aceder aos teus dados. Se a perderes, podes recuperá‑la através do teu email ou número de telemóvel associados à conta."),
            ("Proteção por Tentativas","Após várias tentativas falhadas, o acesso é temporariamente bloqueado para proteger a tua conta."),
            ("Atualizações","Mantém a aplicação atualizada para beneficiares das últimas melhorias de segurança."),
        ]

        # Gerar os blocos de políticas automaticamente
        for i, (titulo, desc) in enumerate(regras):#ve a lista de regras onde tem titulo e descriçao
            f = tk.Frame(interior, bg="white")#cria frames individuais para cada regra do "interior"
            f.pack(fill="x", padx=0, pady=10) #adiciona um espaço entre frames
            tk.Label(f, text=titulo, font=("Segoe UI", 12, "bold"), bg="white", fg="#2C2F33").pack(anchor="w") #titulo
            tk.Label(f, text=desc, font=("Segoe UI", 11, "italic"), bg="white", fg="#666", wraplength=LARGURA_TEXTO, justify="left").pack(anchor="w") #descriçao

            if i < len(regras) - 1: #adiciona um linha para separar as regras
                tk.Frame(interior, bg="#E9ECEF", height=1).pack(fill="x", pady=(10, 0))

        #Rodape a dizer quando e que foi atualizado
        tk.Label(interior, text="Atualizado em Março de 2026", font=("Segoe UI", 8, "bold"), bg="white", fg="#BBB").pack(side="bottom", anchor="w", padx=0, pady=20)
