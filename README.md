# Library API - Case BTG

API RESTful para gerenciamento de biblioteca desenvolvida com FastAPI, PostgreSQL e Redis.

---

## Sumário

- [Funcionalidades Implementadas](#funcionalidades-implementadas)
- [Stack Tecnológica](#stack-tecnológica)
- [Decisões Arquiteturais](#decisões-arquiteturais)
- [Instalação e Execução](#instalação-e-execução)
- [Variáveis de Ambiente](#variáveis-de-ambiente)
- [Executando os Testes](#executando-os-testes)
- [Documentação da API](#documentação-da-api)
- [Exemplos de Uso da API](#exemplos-de-uso-da-api)
- [Rate Limiting e Cache](#rate-limiting-e-cache)
- [Fluxo de Reservas](#fluxo-de-reservas)
- [Estrutura do Projeto](#estrutura-do-projeto)

---

## Funcionalidades Implementadas

### Autenticação e Autorização
- **Cadastro de usuários** com validação de senha forte
- **Login com JWT** (JSON Web Token) com expiração configurável
- **Dois níveis de acesso**: USER (usuário comum) e ADMIN (administrador)
- **Hash seguro de senhas** com bcrypt (custo configurável)

### Gestão de Autores
- Criar, listar, buscar e atualizar autores
- Listagem paginada com busca por nome
- Visualização de livros por autor

### Gestão de Livros
- Criar livros com múltiplas cópias físicas
- Listagem paginada com filtros (título, autor, ano)
- Adicionar novas cópias a títulos existentes
- **Consulta de disponibilidade** com cache Redis

### Sistema de Empréstimos
- Empréstimo automático de cópia disponível
- **Prazo padrão de 14 dias**
- **Renovação** com extensão de prazo (máximo 1 renovações)
- **Cálculo automático de multas** por atraso (R$ 2,00/dia)
- Histórico completo de empréstimos por usuário
- Listagem de empréstimos atrasados (admin)

### Sistema de Reservas (Fila FIFO)
- Reserva quando não há cópias disponíveis
- **Fila de espera** ordenada por data de criação
- **Status ON_HOLD** com prazo de 24h para retirada
- Processamento automático da fila quando cópia é devolvida
- Expiração automática de holds não utilizados

### Gestão de Usuários (Admin)
- Listagem paginada de todos os usuários
- Filtros por role (ADMIN/USER) e busca por nome/email
- Estatísticas de empréstimos por usuário
- Histórico de empréstimos de qualquer usuário

### Recursos Técnicos
- **Rate Limiting** com Redis (sliding window)
- **Cache** de disponibilidade com invalidação automática
- **Paginação** em todas as listagens
- **Validação** de dados com Pydantic v2
- **Logging estruturado** com níveis configuráveis

---

## Stack Tecnológica

| Componente | Tecnologia | Justificativa |
|------------|------------|---------------|
| Framework | FastAPI | Async nativo, tipagem forte, documentação automática |
| Banco de Dados | PostgreSQL 15+ | Robusto, suporte a UUID, índices avançados |
| ORM | SQLAlchemy 2.0 (async) | Mapeamento relacional moderno, suporte async |
| Migrações | Alembic | Versionamento de schema, rollbacks |
| Cache/Rate Limit | Redis 7+ | Alta performance, estruturas de dados avançadas |
| Autenticação | JWT + bcrypt | Padrão da indústria, stateless, seguro |
| Validação | Pydantic v2 | Performance, validação declarativa |
| Testes | pytest + pytest-asyncio | Suporte a código assíncrono |

---

## Decisões Arquiteturais

### 1. Arquitetura em Camadas

```
┌─────────────────────────────────────────────────────────────┐
│                      API Layer (FastAPI)                     │
│   Responsável por: HTTP, validação, serialização, auth      │
├─────────────────────────────────────────────────────────────┤
│                     Service Layer                            │
│   Responsável por: Regras de negócio, orquestração          │
├─────────────────────────────────────────────────────────────┤
│                   Repository Layer                           │
│   Responsável por: Acesso a dados, queries                  │
├─────────────────────────────────────────────────────────────┤
│                    Model Layer (SQLAlchemy)                  │
│   Responsável por: Mapeamento ORM, relacionamentos          │
└─────────────────────────────────────────────────────────────┘
```

**Justificativa**: Separação clara de responsabilidades facilita testes unitários, manutenção e evolução do código. Cada camada pode ser testada isoladamente com mocks.

### 2. Async/Await em Todo o Stack

Todo o código utiliza operações assíncronas:
- Endpoints FastAPI são `async def`
- SQLAlchemy com `AsyncSession` e `asyncpg`
- Redis com `aioredis` (integrado ao redis-py)

**Justificativa**: Melhor utilização de recursos em operações I/O-bound (banco, cache, rede). Uma única thread pode atender múltiplas requisições concorrentemente.

### 3. Modelo de Cópias Físicas

```
BookTitle (1) ──────── (N) BookCopy
    │                        │
    │                        │
    └── title, author_id     └── status (AVAILABLE, LOANED, ON_HOLD)
        published_year           book_title_id
```

**Justificativa**: Permite rastrear cada exemplar físico individualmente. Essencial para:
- Saber qual cópia está emprestada
- Histórico de empréstimos por cópia
- Sistema de reservas que bloqueia cópia específica

### 4. Sistema de Reservas FIFO

```
Reservation
├── user_id          (quem reservou)
├── book_title_id    (qual livro quer)
├── status           (ACTIVE → ON_HOLD → FULFILLED/EXPIRED/CANCELLED)
├── created_at       (posição na fila)
├── hold_copy_id     (cópia reservada quando ON_HOLD)
└── hold_expires_at  (quando o hold expira)
```

**Justificativa**:
- **FIFO** garante justiça na fila
- **Status ON_HOLD** dá tempo para o usuário buscar o livro
- **Expiração automática** libera cópias não retiradas
- Separação entre título desejado e cópia física atribuída

### 5. Rate Limiting com Sliding Window

```
Algoritmo: Sliding Window Log
Armazena timestamps das requisições em sorted set do Redis
Remove entradas fora da janela de tempo
Conta entradas restantes para verificar limite
```

**Justificativa**:
- Mais preciso que fixed window (sem bursts na borda)
- Mais simples que sliding window counter
- Redis sorted set é eficiente para essa operação

### 6. Cache com Invalidação Explícita

O endpoint `/books/{id}/availability` é cacheado com TTL de 15 segundos.

**Eventos que invalidam o cache**:
- Criação de empréstimo
- Devolução de empréstimo
- Processamento de holds
- Expiração de holds

**Justificativa**: Consulta de disponibilidade é frequente e envolve múltiplas queries. Cache reduz carga no banco. Invalidação explícita garante consistência.

### 7. Injeção de Dependências

```python
# Dependências definidas em app/core/deps.py
DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(get_admin_user)]
```

**Justificativa**:
- Código mais limpo nos endpoints
- Facilita testes com override de dependências
- Centraliza lógica de autenticação/autorização

### 8. Pydantic v2 para Validação

```python
class LoanCreate(BaseModel):
    book_title_id: UUID

    model_config = ConfigDict(strict=True)
```

**Justificativa**:
- Validação automática de tipos
- Serialização/deserialização JSON
- Documentação OpenAPI gerada automaticamente
- Performance superior ao Pydantic v1

---

## Instalação e Execução

### Pré-requisitos

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Docker e Docker Compose (opcional)

### Opção 1: Usando Docker Compose (Recomendado)

```bash
# Clonar o repositório
cd case_btg

# Subir PostgreSQL e Redis
docker compose up -d

# Os serviços estarão disponíveis em:
# - PostgreSQL: localhost:5432
# - Redis: localhost:6379
```

### Opção 2: Instalação Manual

Certifique-se de que PostgreSQL e Redis estão rodando localmente.

### Configuração da Aplicação

```bash
# Navegar para a pasta backend
cd backend

# Criar ambiente virtual
python -m venv .venv

# Ativar ambiente virtual
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Instalar dependências
pip install -e ".[dev]"

# Copiar template de variáveis de ambiente
cp .env.example .env
# Editar .env com suas credenciais

# Executar migrações do banco de dados
alembic upgrade head

# Criar usuário admin inicial
python -m app.db.seed

# Iniciar o servidor
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Verificação Rápida

```bash
# Testar se a API está funcionando
curl http://localhost:8000/health

# Resposta esperada:
# {"status":"healthy","timestamp":"2024-...","version":"1.0.0"}
```

---

## Variáveis de Ambiente

Criar arquivo `.env` na pasta `backend/`:

```env
# ============================================
# APLICAÇÃO
# ============================================
APP_NAME=Library API
DEBUG=false
ENVIRONMENT=development

# ============================================
# BANCO DE DADOS
# ============================================
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/library_db

# ============================================
# REDIS
# ============================================
REDIS_URL=redis://localhost:6379/0

# ============================================
# AUTENTICAÇÃO JWT
# (OBRIGATÓRIO alterar em produção!)
# ============================================
JWT_SECRET=sua-chave-secreta-muito-segura-alterar-em-producao
JWT_ALGORITHM=HS256
JWT_EXPIRES_MINUTES=30

# ============================================
# ADMIN INICIAL
# (OBRIGATÓRIO alterar em produção!)
# ============================================
ADMIN_EMAIL=admin@library.com
ADMIN_PASSWORD=Admin123!

# ============================================
# RATE LIMITING
# ============================================
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=60
RATE_LIMIT_WINDOW_SECONDS=60

# ============================================
# CACHE
# ============================================
CACHE_ENABLED=true
CACHE_AVAILABILITY_TTL_SECONDS=15
```

---

## Executando os Testes

```bash
cd backend

# Executar todos os testes
pytest

# Executar com relatório de cobertura
pytest --cov=app --cov-report=html

# Executar testes específicos
pytest tests/test_loans.py -v

# Executar apenas testes unitários (sem banco)
pytest tests/test_security.py tests/test_rate_limit_cache.py -v
```

> **Nota**: Testes de integração requerem banco de dados rodando. Testes unitários rodam sem dependências externas.

---

## Documentação da API

Com o servidor rodando, acesse:

| Recurso | URL |
|---------|-----|
| Swagger UI (interativo) | http://localhost:8000/docs |
| ReDoc (documentação) | http://localhost:8000/redoc |
| OpenAPI JSON | http://localhost:8000/openapi.json |

---

## Exemplos de Uso da API

### 1. Autenticação

#### Criar conta de usuário
```bash
curl -X POST http://localhost:8000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "name": "João Silva",
    "email": "joao@email.com",
    "password": "MinhaSenh@123"
  }'
```

**Resposta:**
```json
{
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "João Silva",
    "email": "joao@email.com",
    "role": "USER"
  },
  "token": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer"
  }
}
```

#### Fazer login
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "joao@email.com",
    "password": "MinhaSenh@123"
  }'
```

#### Obter dados do usuário logado
```bash
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer SEU_TOKEN_AQUI"
```

---

### 2. Gestão de Autores (Admin)

#### Criar autor
```bash
curl -X POST http://localhost:8000/api/v1/authors \
  -H "Authorization: Bearer TOKEN_ADMIN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Machado de Assis"
  }'
```

**Resposta:**
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "Machado de Assis",
  "created_at": "2024-01-15T10:30:00Z"
}
```

#### Listar autores com paginação
```bash
curl "http://localhost:8000/api/v1/authors?page=1&page_size=10&search=machado" \
  -H "Authorization: Bearer SEU_TOKEN"
```

**Resposta:**
```json
{
  "items": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "name": "Machado de Assis",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 10,
  "pages": 1
}
```

---

### 3. Gestão de Livros

#### Criar livro com cópias (Admin)
```bash
curl -X POST "http://localhost:8000/api/v1/books?quantity=3" \
  -H "Authorization: Bearer TOKEN_ADMIN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Dom Casmurro",
    "author_id": "123e4567-e89b-12d3-a456-426614174000",
    "published_year": 1899,
    "pages": 256
  }'
```

**Resposta:**
```json
{
  "book": {
    "id": "789e0123-e89b-12d3-a456-426614174000",
    "title": "Dom Casmurro",
    "author_id": "123e4567-e89b-12d3-a456-426614174000",
    "author_name": "Machado de Assis",
    "published_year": 1899,
    "pages": 256
  },
  "copies_created": 3
}
```

#### Consultar disponibilidade
```bash
curl http://localhost:8000/api/v1/books/789e0123-e89b-12d3-a456-426614174000/availability \
  -H "Authorization: Bearer SEU_TOKEN"
```

**Resposta:**
```json
{
  "book_title_id": "789e0123-e89b-12d3-a456-426614174000",
  "title": "Dom Casmurro",
  "available": true,
  "available_copies": 2,
  "total_copies": 3,
  "queue_position": null
}
```

#### Listar livros com filtros
```bash
curl "http://localhost:8000/api/v1/books?search=casmurro&author_id=123e4567&page=1" \
  -H "Authorization: Bearer SEU_TOKEN"
```

---

### 4. Sistema de Empréstimos

#### Criar empréstimo
```bash
curl -X POST http://localhost:8000/api/v1/loans \
  -H "Authorization: Bearer SEU_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "book_title_id": "789e0123-e89b-12d3-a456-426614174000"
  }'
```

**Resposta:**
```json
{
  "id": "abc12345-e89b-12d3-a456-426614174000",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "book_copy_id": "copy-uuid-here",
  "book_title": "Dom Casmurro",
  "status": "ACTIVE",
  "loaned_at": "2024-01-15T14:00:00Z",
  "due_date": "2024-01-29T14:00:00Z",
  "renewals_count": 0
}
```

#### Listar meus empréstimos
```bash
curl http://localhost:8000/api/v1/loans/my \
  -H "Authorization: Bearer SEU_TOKEN"
```

#### Renovar empréstimo
```bash
curl -X PATCH http://localhost:8000/api/v1/loans/abc12345-e89b-12d3-a456-426614174000/renew \
  -H "Authorization: Bearer SEU_TOKEN"
```

**Resposta:**
```json
{
  "message": "Empréstimo renovado com sucesso",
  "new_due_date": "2024-02-12T14:00:00Z",
  "renewals_count": 1,
  "renewals_remaining": 1
}
```

#### Devolver livro
```bash
curl -X PATCH http://localhost:8000/api/v1/loans/abc12345-e89b-12d3-a456-426614174000/return \
  -H "Authorization: Bearer SEU_TOKEN"
```

**Resposta (sem atraso):**
```json
{
  "message": "Livro devolvido com sucesso",
  "loan": {
    "id": "abc12345-e89b-12d3-a456-426614174000",
    "status": "RETURNED",
    "returned_at": "2024-01-20T10:00:00Z"
  },
  "fine": null
}
```

**Resposta (com atraso):**
```json
{
  "message": "Livro devolvido com sucesso",
  "loan": {
    "id": "abc12345-e89b-12d3-a456-426614174000",
    "status": "RETURNED",
    "returned_at": "2024-02-05T10:00:00Z"
  },
  "fine": {
    "days_overdue": 7,
    "amount": 14.00,
    "daily_rate": 2.00
  }
}
```

---

### 5. Sistema de Reservas

#### Criar reserva (quando não há cópias disponíveis)
```bash
curl -X POST http://localhost:8000/api/v1/reservations \
  -H "Authorization: Bearer SEU_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "book_title_id": "789e0123-e89b-12d3-a456-426614174000"
  }'
```

**Resposta:**
```json
{
  "id": "res-12345-uuid",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "book_title_id": "789e0123-e89b-12d3-a456-426614174000",
  "book_title": "Dom Casmurro",
  "status": "ACTIVE",
  "queue_position": 1,
  "created_at": "2024-01-15T15:00:00Z"
}
```

#### Listar minhas reservas
```bash
curl http://localhost:8000/api/v1/reservations/my \
  -H "Authorization: Bearer SEU_TOKEN"
```

#### Cancelar reserva
```bash
curl -X PATCH http://localhost:8000/api/v1/reservations/res-12345-uuid/cancel \
  -H "Authorization: Bearer SEU_TOKEN"
```

---

### 6. Operações Administrativas

#### Listar todos os usuários (Admin)
```bash
curl "http://localhost:8000/api/v1/users?role=USER&page=1&page_size=20" \
  -H "Authorization: Bearer TOKEN_ADMIN"
```

**Resposta:**
```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "João Silva",
      "email": "joao@email.com",
      "role": "USER",
      "active_loans_count": 2,
      "total_loans_count": 15
    }
  ],
  "total": 150,
  "page": 1,
  "page_size": 20,
  "pages": 8
}
```

#### Listar empréstimos de um usuário (Admin)
```bash
curl "http://localhost:8000/api/v1/users/550e8400-uuid/loans?status=active" \
  -H "Authorization: Bearer TOKEN_ADMIN"
```

#### Listar empréstimos atrasados (Admin)
```bash
curl http://localhost:8000/api/v1/loans/overdue \
  -H "Authorization: Bearer TOKEN_ADMIN"
```

#### Processar fila de reservas (Admin)
```bash
curl -X POST http://localhost:8000/api/v1/system/process-holds \
  -H "Authorization: Bearer TOKEN_ADMIN"
```

**Resposta:**
```json
{
  "results": [
    {
      "reservation_id": "res-uuid",
      "user_email": "joao@email.com",
      "book_title": "Dom Casmurro",
      "status": "ON_HOLD",
      "expires_at": "2024-01-16T15:00:00Z"
    }
  ],
  "total_processed": 1
}
```

#### Expirar holds não utilizados (Admin)
```bash
curl -X POST http://localhost:8000/api/v1/system/expire-holds \
  -H "Authorization: Bearer TOKEN_ADMIN"
```

---

### Exemplos em PowerShell (Windows)

```powershell
# Login e salvar token
$body = @{email="joao@email.com";password="MinhaSenh@123"} | ConvertTo-Json
$response = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/auth/login" `
  -Method POST -Body $body -ContentType "application/json"
$token = $response.token.access_token

# Listar livros
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/books" `
  -Headers @{Authorization="Bearer $token"}

# Criar empréstimo
$body = @{book_title_id="789e0123-e89b-12d3-a456-426614174000"} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/loans" `
  -Method POST -Body $body -ContentType "application/json" `
  -Headers @{Authorization="Bearer $token"}
```

---

## Rate Limiting e Cache

### Rate Limiting

O sistema utiliza Redis com algoritmo de sliding window para limitar requisições.

| Endpoint | Limite | Finalidade |
|----------|--------|------------|
| POST /auth/signup | 10/min | Prevenir abuso de cadastros |
| POST /auth/login | 10/min | Prevenir força bruta |
| POST /loans | 60/min | Prevenir spam de empréstimos |
| PATCH /loans/{id}/renew | 60/min | Prevenir spam de renovações |
| POST /reservations | 60/min | Prevenir spam de reservas |

**Desabilitar rate limiting:**
```env
RATE_LIMIT_ENABLED=false
```

### Cache

O endpoint de disponibilidade (`GET /books/{id}/availability`) é cacheado com TTL de 15 segundos.

**Eventos que invalidam o cache:**
- Criação de empréstimo
- Devolução de empréstimo
- Processamento de holds
- Expiração de holds

**Desabilitar cache:**
```env
CACHE_ENABLED=false
```

---

## Fluxo de Reservas

O sistema implementa uma fila FIFO (First In, First Out):

```
┌─────────────────────────────────────────────────────────────────┐
│                    FLUXO DE RESERVA                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Usuário solicita reserva (todas as cópias emprestadas)      │
│     └─> Reserva criada com status: ACTIVE                       │
│         └─> Usuário entra na fila (posição por data)            │
│                                                                 │
│  2. Uma cópia fica disponível (devolvida por outro usuário)     │
│     └─> Admin executa: POST /system/process-holds               │
│         └─> Primeira reserva ACTIVE → ON_HOLD                   │
│         └─> Cópia status → ON_HOLD (expira em 24h)              │
│                                                                 │
│  3. Usuário com reserva ON_HOLD:                                │
│     ├─> Cria empréstimo em 24h → Reserva: FULFILLED             │
│     └─> Não retira em 24h → Admin executa expire-holds          │
│         └─> Reserva: EXPIRED                                    │
│         └─> Cópia: AVAILABLE                                    │
│         └─> Próxima reserva da fila é processada                │
│                                                                 │
│  Caminhos alternativos:                                         │
│  • Usuário cancela → Reserva: CANCELLED                         │
│  • Usuário cancela ON_HOLD → Cópia liberada, próximo da fila    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Status das Reservas

| Status | Descrição |
|--------|-----------|
| ACTIVE | Na fila, aguardando cópia disponível |
| ON_HOLD | Cópia reservada, usuário tem 24h para retirar |
| FULFILLED | Usuário criou empréstimo a partir desta reserva |
| EXPIRED | Hold expirou (não retirou a tempo) |
| CANCELLED | Usuário cancelou a reserva |

---

## Estrutura do Projeto

```
case_btg/
├── backend/
│   ├── app/
│   │   ├── api/v1/              # Endpoints da API
│   │   │   ├── auth.py          # Autenticação (signup, login, me)
│   │   │   ├── authors.py       # CRUD de autores
│   │   │   ├── books.py         # CRUD de livros + disponibilidade
│   │   │   ├── loans.py         # Empréstimos
│   │   │   ├── reservations.py  # Fila de reservas
│   │   │   ├── users.py         # Gestão de usuários (admin)
│   │   │   └── system.py        # Operações administrativas
│   │   ├── core/                # Utilitários centrais
│   │   │   ├── config.py        # Configurações (Pydantic Settings)
│   │   │   ├── deps.py          # Dependências FastAPI
│   │   │   ├── security.py      # JWT + bcrypt
│   │   │   ├── rate_limit.py    # Rate limiter
│   │   │   └── cache.py         # Serviço de cache
│   │   ├── db/                  # Banco de dados
│   │   │   ├── session.py       # Configuração SQLAlchemy
│   │   │   ├── redis.py         # Cliente Redis
│   │   │   └── seed.py          # Seed do admin inicial
│   │   ├── models/              # Modelos SQLAlchemy
│   │   │   ├── user.py          # Usuário
│   │   │   ├── author.py        # Autor
│   │   │   ├── book.py          # BookTitle + BookCopy
│   │   │   ├── loan.py          # Empréstimo
│   │   │   └── reservation.py   # Reserva
│   │   ├── schemas/             # Schemas Pydantic
│   │   ├── repositories/        # Camada de acesso a dados
│   │   └── services/            # Regras de negócio
│   ├── tests/                   # Testes automatizados
│   ├── alembic/                 # Migrações do banco
│   ├── pyproject.toml           # Dependências Python
│   └── .env.example             # Template de variáveis
├── api-client/
│   └── Library_API.postman_collection.json  # Collection Postman
├── docker-compose.yml           # PostgreSQL + Redis
└── README.md                    # Esta documentação
```

---

## Notas de Segurança

> **IMPORTANTE**: Configurar obrigatoriamente em produção:

1. **JWT_SECRET**: Deve ser uma chave forte e única
   ```env
   JWT_SECRET=sua-chave-de-256-bits-muito-segura
   ```

2. **ADMIN_EMAIL e ADMIN_PASSWORD**: Alterar credenciais padrão
   ```env
   ADMIN_EMAIL=admin@suaempresa.com
   ADMIN_PASSWORD=SenhaForte123!@#
   ```

3. **DATABASE_URL**: Usar credenciais seguras
   ```env
   DATABASE_URL=postgresql+asyncpg://usuario:senha@host:5432/banco
   ```

4. **Modo Debug**: Desabilitar em produção
   ```env
   DEBUG=false
   ENVIRONMENT=production
   ```

---

## Collection Postman

A collection Postman está disponível em `api-client/Library_API.postman_collection.json`.

### Importar no Postman

1. Abrir Postman
2. Clicar em **Import**
3. Selecionar o arquivo `Library_API.postman_collection.json`
4. A collection aparecerá na sidebar

### Ordem de Execução Recomendada

1. **Health** - Verificar se API está rodando
2. **Auth** - Signup → Login User → Login Admin
3. **Users** - Listar usuários (admin)
4. **Authors** - Criar autor
5. **Books** - Criar livro → Verificar disponibilidade
6. **Loans** - Criar empréstimo → Renovar → Devolver
7. **Reservations** - Criar reserva (quando sem cópias)
8. **System** - Processar holds → Expirar holds

### Variáveis da Collection

| Variável | Descrição |
|----------|-----------|
| `user_token` | Token JWT do usuário comum |
| `admin_token` | Token JWT do administrador |
| `user_id` | UUID do usuário logado |
| `author_id` | UUID do último autor criado |
| `book_id` | UUID do último livro criado |
| `loan_id` | UUID do último empréstimo criado |
| `reservation_id` | UUID da última reserva criada |

---
