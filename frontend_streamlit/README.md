# Frontend Streamlit - Library API

Frontend de demonstração para a Library API, desenvolvido em Streamlit.

## Instalação

```bash
cd frontend_streamlit

# Criar ambiente virtual
python -m venv .venv

# Ativar ambiente virtual
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Instalar dependências
pip install -r requirements.txt
```

## Execução

```bash
# Certifique-se de que o backend está rodando em http://localhost:8000

# Iniciar o frontend
streamlit run app.py
```

O frontend estará disponível em http://localhost:8501

## Configuração

A URL do backend pode ser alterada na sidebar. O padrão é `http://localhost:8000`.

## Credenciais de Teste

- **Admin**: admin@library.local / Admin123!
- **Usuário**: Crie uma conta na aba "Criar Conta"

---

## Roteiro de Demo (2-3 minutos)

### Preparação
1. Certifique-se de que o backend está rodando (`uvicorn app.main:app --reload`)
2. Inicie o frontend (`streamlit run app.py`)

### Demo

#### 1. Login como Admin (30s)
- Acesse http://localhost:8501
- Faça login: `admin@library.local` / `Admin123!`
- Mostre que é admin na sidebar

#### 2. Criar Autor e Livro (45s)
- Vá para "⚙️ Gerenciar" > "📝 Autores"
- Crie um autor: "Machado de Assis"
- Vá para "📚 Livros"
- Crie um livro: "Dom Casmurro" com 2 cópias

#### 3. Login como Usuário (30s)
- Clique em "Sair"
- Vá para "Criar Conta"
- Crie: "João Silva" / joao@email.com / TestPass123!
- Mostre que agora é USER

#### 4. Emprestar até Esgotar (30s)
- Vá para "📚 Catálogo"
- Clique em "Detalhes" no livro criado
- Clique em "Emprestar"
- Repita para a segunda cópia (ou crie outro empréstimo)

#### 5. Reservar (20s)
- Com todas as cópias emprestadas, tente emprestar novamente
- Verá mensagem de erro
- Clique em "Reservar" - reserva criada!
- Vá para "📋 Minhas Reservas" - mostra status ACTIVE

#### 6. Devolver e Process Holds (30s)
- Vá para "📗 Meus Empréstimos"
- Clique em "Devolver" em um empréstimo
- Faça login como admin novamente
- Vá para "⚙️ Gerenciar" > "⚙️ Sistema"
- Clique em "Process Holds"
- Mostra que 1 hold foi processado

#### 7. Verificar Reserva (15s)
- Login como usuário novamente
- Vá para "📋 Minhas Reservas"
- Reserva agora está ON_HOLD com prazo de 24h

### Conclusão
- Mostre a sidebar com navegação
- Mostre que a configuração de URL é editável
- Mencione que é apenas um demo, não produção

---

## Estrutura do Projeto

```
frontend_streamlit/
├── app.py                 # Entrypoint
├── requirements.txt       # Dependências
├── README.md             # Este arquivo
├── utils/
│   ├── __init__.py
│   ├── api_client.py     # Wrapper HTTP com retry
│   ├── auth.py           # Login/signup/guards
│   ├── state.py          # Session state helpers
│   └── formatters.py     # Formatação de dados
└── pages/
    ├── 1_Login.py         # Autenticação
    ├── 2_Catalog.py       # Catálogo de livros
    ├── 3_My_Loans.py      # Empréstimos do usuário
    ├── 4_My_Reservations.py # Reservas do usuário
    ├── 5_Admin.py         # Administração
    └── 6_Admin_Users.py   # Gestão de usuários
```

## Funcionalidades

### Login / Signup
- Login com email/senha
- Criação de conta
- Logout

### Catálogo
- Lista paginada de livros
- Busca por título
- Detalhes e disponibilidade
- Emprestar/Reservar

### Meus Empréstimos
- Lista de empréstimos ativos
- Histórico de devoluções
- Renovar (máx 2x)
- Devolver

### Minhas Reservas
- Lista de reservas ativas
- Histórico
- Cancelar reserva
- Status ON_HOLD com prazo

### Admin
- Criar autores
- Criar livros com cópias
- Adicionar cópias
- Process/Expire holds
- Ver empréstimos atrasados

### Admin Users
- Lista de usuários
- Buscar por ID
- Ver empréstimos do usuário
