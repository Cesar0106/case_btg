"""
API Client wrapper for the Library API.

Provides a unified interface for making HTTP requests to the backend
with proper error handling, retries, and token management.
"""

import time
from typing import Any, Optional

import requests
import streamlit as st


class APIError(Exception):
    """Custom exception for API errors."""

    def __init__(self, message: str, status_code: int = 0, detail: Any = None):
        self.message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(self.message)


class APIClient:
    """
    HTTP client for the Library API.

    Features:
        - Automatic token injection from session state
        - Retry logic for transient errors (502, 503)
        - Timeout handling
        - Structured error responses
    """

    DEFAULT_TIMEOUT = 10
    MAX_RETRIES = 2
    RETRY_DELAY = 0.5

    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize the API client.

        Args:
            base_url: Base URL for the API (without /api/v1 suffix)
        """
        self.base_url = (base_url or "http://localhost:8000").rstrip("/")
        self.api_prefix = "/api/v1"

    def _get_url(self, endpoint: str) -> str:
        """Build full URL for an endpoint."""
        endpoint = endpoint.lstrip("/")
        return f"{self.base_url}{self.api_prefix}/{endpoint}"

    def _get_headers(self, include_auth: bool = True) -> dict:
        """Build request headers."""
        headers = {"Content-Type": "application/json"}
        if include_auth and "token" in st.session_state and st.session_state.token:
            headers["Authorization"] = f"Bearer {st.session_state.token}"
        return headers

    def _handle_response(self, response: requests.Response) -> dict:
        """
        Process API response and handle errors.

        Raises:
            APIError: For non-2xx responses
        """
        if response.status_code == 401:
            from .state import clear_session
            clear_session()
            raise APIError("Sessão expirada. Faça login novamente.", 401)

        if response.status_code == 429:
            detail = response.json().get("detail", "Muitas requisições")
            raise APIError(f"Rate limit: {detail}", 429)

        if response.status_code >= 400:
            try:
                error_data = response.json()
                if isinstance(error_data.get("detail"), list):
                    messages = [e.get("msg", str(e)) for e in error_data["detail"]]
                    detail = "; ".join(messages)
                else:
                    detail = error_data.get("detail", str(error_data))
            except Exception:
                detail = response.text or f"Erro HTTP {response.status_code}"
            raise APIError(detail, response.status_code)

        if response.status_code == 204:
            return {}

        try:
            return response.json()
        except Exception:
            return {}

    def _request(
        self,
        method: str,
        endpoint: str,
        include_auth: bool = True,
        **kwargs,
    ) -> dict:
        """
        Make an HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (without /api/v1 prefix)
            include_auth: Whether to include auth token
            **kwargs: Additional arguments for requests

        Returns:
            Parsed JSON response

        Raises:
            APIError: For API errors
        """
        url = self._get_url(endpoint)
        headers = self._get_headers(include_auth)
        kwargs.setdefault("timeout", self.DEFAULT_TIMEOUT)

        last_error = None
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    **kwargs,
                )

                if response.status_code in (502, 503) and attempt < self.MAX_RETRIES:
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                    continue

                return self._handle_response(response)

            except requests.exceptions.Timeout:
                last_error = APIError("Tempo de requisição esgotado", 0)
                if attempt < self.MAX_RETRIES:
                    time.sleep(self.RETRY_DELAY)
                    continue
            except requests.exceptions.ConnectionError:
                last_error = APIError(
                    "Não foi possível conectar ao servidor. Verifique se o backend está rodando.",
                    0,
                )
                break
            except APIError:
                raise
            except Exception as e:
                last_error = APIError(f"Erro inesperado: {str(e)}", 0)
                break

        raise last_error

    def get(self, endpoint: str, params: Optional[dict] = None, **kwargs) -> dict:
        """Make a GET request."""
        return self._request("GET", endpoint, params=params, **kwargs)

    def post(self, endpoint: str, json: Optional[dict] = None, **kwargs) -> dict:
        """Make a POST request."""
        return self._request("POST", endpoint, json=json, **kwargs)

    def patch(self, endpoint: str, json: Optional[dict] = None, **kwargs) -> dict:
        """Make a PATCH request."""
        return self._request("PATCH", endpoint, json=json, **kwargs)

    def put(self, endpoint: str, json: Optional[dict] = None, **kwargs) -> dict:
        """Make a PUT request."""
        return self._request("PUT", endpoint, json=json, **kwargs)

    def delete(self, endpoint: str, **kwargs) -> dict:
        """Make a DELETE request."""
        return self._request("DELETE", endpoint, **kwargs)


def get_api_client() -> APIClient:
    """
    Get the API client instance.

    Uses the base_url from session state if configured.
    """
    base_url = st.session_state.get("base_url", "http://localhost:8000")
    return APIClient(base_url)
