"""
Book Catalog page.

Displays available books with search, details modal, and loan/reservation actions.
"""

import streamlit as st

from utils.api_client import APIError, get_api_client
from utils.auth import require_auth
from utils.state import init_session_state

init_session_state()

st.set_page_config(page_title="Catálogo - Library", page_icon="📚", layout="wide")

st.title("📚 Catálogo de Livros")

if not require_auth():
    st.stop()

api = get_api_client()


def load_authors() -> list:
    """Load all authors for filter dropdown."""
    try:
        response = api.get("authors", params={"page_size": 100})
        return response.get("items", [])
    except APIError:
        return []


def load_books(page: int = 1, page_size: int = 10, title: str = "", author_id: str = "") -> tuple[list, int]:
    """Load books from API with pagination and filters."""
    try:
        params = {"page": page, "page_size": page_size}
        if title:
            params["title"] = title
        if author_id:
            params["author_id"] = author_id

        response = api.get("books", params=params)
        items = response.get("items", [])
        total = response.get("total", 0)
        return items, total
    except APIError as e:
        st.error(f"Erro ao carregar livros: {e.message}")
        return [], 0


def load_book_details(book_id: str) -> dict | None:
    """Load detailed information for a specific book."""
    try:
        return api.get(f"books/{book_id}")
    except APIError:
        return None


def load_availability(book_id: str) -> dict | None:
    """Load availability information for a book."""
    try:
        return api.get(f"books/{book_id}/availability")
    except APIError:
        return None


def create_loan(book_title_id: str) -> tuple[bool, str]:
    """Create a new loan for a book."""
    try:
        api.post("loans", json={"book_title_id": book_title_id})
        return True, "Empréstimo realizado com sucesso!"
    except APIError as e:
        return False, e.message


def create_reservation(book_title_id: str) -> tuple[bool, str]:
    """Create a new reservation for a book."""
    try:
        api.post("reservations", json={"book_title_id": book_title_id})
        return True, "Reserva criada com sucesso!"
    except APIError as e:
        return False, e.message


@st.dialog("Detalhes do Livro", width="large")
def show_book_modal(book_id: str):
    """Modal dialog showing book details with loan/reserve actions."""
    with st.spinner("Carregando detalhes..."):
        book = load_book_details(book_id)
        availability = load_availability(book_id)

    if not book:
        st.error("Erro ao carregar livro")
        return

    st.markdown(f"## {book.get('title', 'Sem título')}")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown(f"**Autor:** {book.get('author_name', 'Desconhecido')}")

        if book.get("published_year"):
            st.markdown(f"**Ano de publicação:** {book.get('published_year')}")

        if book.get("pages"):
            st.markdown(f"**Páginas:** {book.get('pages')}")

    with col2:
        if availability:
            available_copies = availability.get("available_copies", 0)
            total_copies = availability.get("total_copies", 0)

            if availability.get("available"):
                st.success(f"**Disponível**\n\n{available_copies} de {total_copies} cópias")
            else:
                st.warning(f"**Indisponível**\n\n0 de {total_copies} cópias")
                reason = availability.get("reason")
                if reason:
                    st.caption(reason)

    st.divider()

    col_loan, col_reserve = st.columns(2)

    with col_loan:
        if st.button("📗 Emprestar", use_container_width=True, type="primary"):
            with st.spinner("Processando empréstimo..."):
                success, message = create_loan(book_id)
            if success:
                st.success(message)
                st.rerun()
            else:
                st.error(message)

    with col_reserve:
        if st.button("📋 Reservar", use_container_width=True):
            with st.spinner("Processando reserva..."):
                success, message = create_reservation(book_id)
            if success:
                st.success(message)
            else:
                st.error(message)


# Load authors for filter with spinner
with st.spinner("Carregando filtros..."):
    authors = load_authors()

author_options = {"Todos": ""}
for a in authors:
    name = a.get("name")
    author_id = a.get("id")
    if name:
        author_options[name] = author_id

# Search filters
st.subheader("🔍 Filtros")

col_title, col_author, col_year, col_available = st.columns(4)

with col_title:
    search_title = st.text_input(
        "Título",
        placeholder="Buscar por título...",
    )

with col_author:
    selected_author = st.selectbox(
        "Autor",
        options=list(author_options.keys()),
        index=0,
    )

with col_year:
    search_year = st.text_input(
        "Ano",
        placeholder="Ex: 1899",
    )

with col_available:
    availability_filter = st.selectbox(
        "Disponibilidade",
        options=["Todos", "Disponíveis", "Indisponíveis"],
        index=0,
    )

st.divider()

# Pagination state
if "catalog_page" not in st.session_state:
    st.session_state.catalog_page = 1

# Get author_id from selection
author_id_filter = author_options.get(selected_author, "")

# Load books with spinner
with st.spinner("Carregando livros..."):
    books, total = load_books(
        page=st.session_state.catalog_page,
        page_size=10,
        title=search_title,
        author_id=author_id_filter,
    )

    # Client-side year filter (backend doesn't support year filter)
    if search_year and search_year.isdigit():
        year_int = int(search_year)
        books = [b for b in books if b.get("published_year") == year_int]

    # Enrich books with author names and availability
    enriched_books = []
    for book in books:
        book_id = book.get("id")
        details = load_book_details(book_id)
        if details:
            enriched_books.append(details)
        else:
            enriched_books.append(book)

    # Client-side availability filter
    if availability_filter == "Disponíveis":
        enriched_books = [b for b in enriched_books if b.get("available_copies", 0) > 0]
    elif availability_filter == "Indisponíveis":
        enriched_books = [b for b in enriched_books if b.get("available_copies", 0) == 0]

total_pages = max(1, (total + 9) // 10)

if enriched_books:
    for book in enriched_books:
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 1, 1])

            with col1:
                title = book.get("title", "Sem título")
                st.markdown(f"### {title}")

                author_name = book.get("author_name", "Autor desconhecido")
                year = book.get("published_year")
                pages = book.get("pages")

                info_parts = [f"**Autor:** {author_name}"]
                if year:
                    info_parts.append(f"**Ano:** {year}")
                if pages:
                    info_parts.append(f"**Páginas:** {pages}")

                st.caption(" | ".join(info_parts))

            with col2:
                available = book.get("available_copies", 0)
                total_copies = book.get("total_copies", 0)

                if available > 0:
                    st.success(f"✅ {available}/{total_copies}")
                else:
                    st.warning(f"⏳ 0/{total_copies}")

            with col3:
                book_id = book.get("id")
                if st.button("📖 Detalhes", key=f"details_{book_id}", use_container_width=True):
                    show_book_modal(book_id)

    # Pagination
    col_prev, col_info, col_next = st.columns([1, 2, 1])

    with col_prev:
        if st.button("⬅️ Anterior", disabled=st.session_state.catalog_page <= 1):
            st.session_state.catalog_page -= 1
            st.rerun()

    with col_info:
        st.caption(f"Página {st.session_state.catalog_page} de {total_pages} ({total} livros)")

    with col_next:
        if st.button("Próxima ➡️", disabled=st.session_state.catalog_page >= total_pages):
            st.session_state.catalog_page += 1
            st.rerun()

else:
    st.info("Nenhum livro encontrado.")
