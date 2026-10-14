from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit


def _public_addresses(host: str) -> list[str]:
    """Resolve a hostname and reject anything that points at a non-public IP."""
    try:
        answers = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("Não foi possível localizar o domínio do link.") from exc

    addresses: list[str] = []
    for answer in answers:
        address = answer[4][0]
        parsed = ipaddress.ip_address(address)
        if not parsed.is_global:
            raise ValueError("Esse endereço não pode ser acessado pelo serviço.")
        addresses.append(address)
    if not addresses:
        raise ValueError("Não foi possível localizar o domínio do link.")
    return addresses


def validate_url(url: str) -> str:
    """Accept public HTTP(S) URLs only; reject credentials and local targets."""
    try:
        candidate = url.strip()
        if not candidate or any(ord(char) < 32 for char in candidate):
            raise ValueError("Esse link não parece válido.")
        parsed = urlsplit(candidate)
        scheme = parsed.scheme.lower()
        if scheme not in {"http", "https"}:
            raise ValueError("Use um link que comece com http:// ou https://.")
        if not parsed.hostname:
            raise ValueError("Esse link não parece válido.")
        if parsed.username or parsed.password:
            raise ValueError("Links com usuário ou senha embutidos não são aceitos.")
        # Restrict ports to ordinary web traffic; this is an important SSRF guard.
        port = parsed.port
        expected_port = 443 if scheme == "https" else 80
        if port is not None and port != expected_port:
            raise ValueError("Links com portas fora do padrão não são aceitos.")
        host = parsed.hostname.rstrip(".").lower()
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            raise ValueError("Esse endereço não pode ser acessado pelo serviço.")
        _public_addresses(host)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Esse link não parece válido.") from exc
    return candidate
