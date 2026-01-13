"""
Admin page.

Administrative functions for managing authors, books, and system operations.
"""

import streamlit as st

from utils.api_client import APIError, get_api_client
from utils.auth import require_admin
from utils.formatters import format_datetime
from utils.state import init_session_state

init_session_state()

st.set_page_config(page_title="Administração - Library", page_icon="⚙️", layout="wide")

st.title("⚙️ Administração")

if not require_admin():
    st.stop()

api = get_api_client()


def load_authors() -> list:
    """Load all authors."""
    try:
        response = api.get("authors", params={"page_size": 100})
        return response.get("items", [])
    except APIError as e:
        st.error(f"Erro ao carregar autores: {e.message}")
        return []


def create_author(name: str) -> tuple[bool, str]:
    """Create a new author."""
    try:
        result = api.post("authors", json={"name": name})
        author_name = result.get("name", name)
        return True, f"Autor '{author_name}' criado com sucesso!"
    except APIError as e:
        return False, e.message


def load_books() -> list:
    """Load all books with details."""
    try:
        response = api.get("books", params={"page_size": 100})
        items = response.get("items", [])
        # Enrich with details
        enriched = []
        for book in items:
            try:
                details = api.get(f"books/{book.get('id')}")
                enriched.append(details)
            except APIError:
                enriched.append(book)
        return enriched
    except APIError as e:
        st.error(f"Erro ao carregar livros: {e.message}")
        return []


def create_book(
    title: str,
    author_id: str,
    quantity: int,
    published_year: int | None = None,
    pages: int | None = None,
) -> tuple[bool, str]:
    """Create a new book with copies."""
    try:
        data = {"title": title, "author_id": author_id}
        if published_year:
            data["published_year"] = published_year
        if pages:
            data["pages"] = pages

        result = api.post("books", json=data, params={"quantity": quantity})
        book_title = result.get("book", {}).get("title", title)
        copies = result.get("copies_created", quantity)
        return True, f"Livro '{book_title}' criado com {copies} cópia(s)!"
    except APIError as e:
        return False, e.message


def add_copies(book_id: str, quantity: int) -> tuple[bool, str]:
    """Add copies to an existing book."""
    try:
        api.post(f"books/{book_id}/copies", params={"quantity": quantity})
        return True, f"{quantity} cópia(s) adicionada(s) com sucesso!"
    except APIError as e:
        return False, e.message


def process_holds() -> tuple[bool, str, int]:
    """Process pending holds."""
    try:
        response = api.post("system/process-holds")
        total = response.get("total_processed", 0)
        return True, f"{total} hold(s) processado(s)!", total
    except APIError as e:
        return False, e.message, 0


def expire_holds() -> tuple[bool, str, int]:
    """Expire old holds."""
    try:
        response = api.post("system/expire-holds")
        total = response.get("expired_count", 0)
        return True, f"{total} hold(s) expirado(s)!", total
    except APIError as e:
        return False, e.message, 0


def load_overdue_loans() -> list:
    """Load overdue loans."""
    try:
        response = api.get("loans/overdue")
        if isinstance(response, list):
            return response
        return response.get("items", [])
    except APIError as e:
        st.error(f"Erro ao carregar empréstimos atrasados: {e.message}")
        return []


tab_authors, tab_books, tab_copies, tab_system, tab_overdue = st.tabs([
    "📝 Autores",
    "📚 Livros",
    "📖 Cópias",
    "⚙️ Sistema",
    "⚠️ Atrasados",
])

with tab_authors:
    st.subheader("Criar Autor")

    author_name = st.text_input("Nome do autor", placeholder="Machado de Assis", key="new_author_name")

    if st.button("Criar Autor", use_container_width=True, key="btn_create_author"):
        if not author_name or len(author_name) < 2:
            st.error("Nome do autor deve ter pelo menos 2 caracteres")
        else:
            with st.spinner("Criando autor..."):
                success, message = create_author(author_name)
            if success:
                st.success(message)
                st.rerun()
            else:
                st.error(message)

    st.divider()
    st.subheader("Autores Cadastrados")

    with st.spinner("Carregando autores..."):
        authors = load_authors()

    if authors:
        for author in authors:
            name = author.get("name", "N/A")
            author_id = author.get("id", "")
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{name}**")
                with col2:
                    st.caption(f"ID: {author_id[:8]}...")
    else:
        st.info("Nenhum autor cadastrado.")

with tab_books:
    st.subheader("Criar Livro")

    with st.spinner("Carregando autores..."):
        authors = load_authors()

    author_options = {}
    for a in authors:
        name = a.get("name")
        aid = a.get("id")
        if name and aid:
            author_options[name] = aid

    if not author_options:
        st.warning("Crie um autor antes de criar livros.")
    else:
        book_title = st.text_input("Título do livro", placeholder="Dom Casmurro", key="new_book_title")

        selected_author = st.selectbox(
            "Autor",
            options=list(author_options.keys()),
            key="new_book_author",
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            quantity = st.number_input("Número de cópias", min_value=1, max_value=100, value=1, key="new_book_qty")
        with col2:
            published_year = st.number_input(
                "Ano (opcional)",
                min_value=1000,
                max_value=2100,
                value=None,
                step=1,
                key="new_book_year",
            )
        with col3:
            pages = st.number_input(
                "Páginas (opcional)",
                min_value=1,
                max_value=50000,
                value=None,
                step=1,
                key="new_book_pages",
            )

        if st.button("Criar Livro", use_container_width=True, key="btn_create_book"):
            if not book_title:
                st.error("Título é obrigatório")
            elif not selected_author:
                st.error("Selecione um autor")
            else:
                with st.spinner("Criando livro..."):
                    author_id = author_options[selected_author]
                    success, message = create_book(
                        book_title,
                        author_id,
                        quantity,
                        published_year if published_year else None,
                        pages if pages else None,
                    )
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)

with tab_copies:
    st.subheader("Adicionar Cópias a Livro Existente")

    with st.spinner("Carregando livros..."):
        books = load_books()

    book_options = {}
    for b in books:
        title = b.get("title", "Sem título")
        author = b.get("author_name", "")
        bid = b.get("id")
        if bid:
            display = f"{title}" + (f" - {author}" if author else "")
            book_options[display] = bid

    if not book_options:
        st.warning("Nenhum livro cadastrado.")
    else:
        selected_book = st.selectbox(
            "Selecione o livro",
            options=list(book_options.keys()),
            key="add_copies_book",
        )

        quantity = st.number_input("Número de cópias a adicionar", min_value=1, max_value=100, value=1, key="add_copies_qty")

        if st.button("Adicionar Cópias", use_container_width=True, key="btn_add_copies"):
            if selected_book:
                with st.spinner("Adicionando cópias..."):
                    book_id = book_options[selected_book]
                    success, message = add_copies(book_id, quantity)
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)

with tab_system:
    st.subheader("Operações do Sistema")

    st.markdown("""
    **Process Holds**: Processa reservas pendentes, atribuindo cópias disponíveis
    aos primeiros da fila.

    **Expire Holds**: Expira holds que ultrapassaram o prazo de 24h sem retirada.
    """)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔄 Process Holds", use_container_width=True, type="primary"):
            with st.spinner("Processando holds..."):
                success, message, total = process_holds()
            if success:
                st.success(message)
            else:
                st.error(message)

    with col2:
        if st.button("⏰ Expire Holds", use_container_width=True):
            with st.spinner("Expirando holds..."):
                success, message, total = expire_holds()
            if success:
                st.success(message)
            else:
                st.error(message)

with tab_overdue:
    st.subheader("Empréstimos Atrasados")

    if st.button("🔄 Atualizar Lista"):
        st.rerun()

    with st.spinner("Carregando empréstimos atrasados..."):
        overdue_loans = load_overdue_loans()

    if not overdue_loans:
        st.success("Nenhum empréstimo atrasado!")
    else:
        st.warning(f"⚠️ {len(overdue_loans)} empréstimo(s) atrasado(s)")

        for loan in overdue_loans:
            with st.container(border=True):
                col1, col2, col3 = st.columns([2, 1, 1])

                with col1:
                    st.markdown(f"**{loan.get('book_title', 'Título desconhecido')}**")
                    st.caption(f"Usuário: {loan.get('user_email', 'N/A')}")

                with col2:
                    due_date = loan.get("due_date")
                    st.error(f"Venceu em: {format_datetime(due_date)}")

                with col3:
                    fine = loan.get("fine_amount") or loan.get("fine_amount_current")
                    if fine:
                        st.markdown(f"Multa: **R$ {float(fine):.2f}**")
