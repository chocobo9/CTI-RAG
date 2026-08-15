from __future__ import annotations

import ipaddress
import re
from urllib.parse import SplitResult, urlsplit, urlunsplit

URL_TOKEN_RE = re.compile(r"(?i)\b(?:https?|hxxps?)://[^\s<>{}\"']+")
IP_TOKEN_RE = re.compile(
    r"(?<![\w.])(?:"
    r"(?:\d{1,3}\.){3}\d{1,3}|"
    r"(?:[0-9a-f]{0,4}:){2,7}[0-9a-f]{0,4}"
    r")(?![\w.:])",
    re.IGNORECASE,
)
DOMAIN_TOKEN_RE = re.compile(
    r"(?i)(?<![\w@.-])"
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.|\[\.\]))+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?![\w.-])"
)

_TRAILING_URL_PUNCTUATION = ".,;:!?)]}\"'"
_DEFANGED_SCHEME_RE = re.compile(r"(?i)^hxxps?://")


def restore_defanged_url(value: str) -> str:
    cleaned = value.strip().rstrip(_TRAILING_URL_PUNCTUATION)
    cleaned = cleaned.replace("[.]", ".").replace("(.)", ".").replace("[:]", ":")
    return _DEFANGED_SCHEME_RE.sub(
        lambda match: "https://" if match.group().lower() == "hxxps://" else "http://",
        cleaned,
    )


def normalize_domain(value: str) -> str | None:
    value = value.strip().rstrip(".").replace("[.]", ".").replace("(.)", ".").lower()
    if not value or value.startswith("*.") or len(value) > 253 or "." not in value:
        return None
    try:
        value = value.encode("idna").decode("ascii")
        ipaddress.ip_address(value)
        return None
    except UnicodeError:
        return None
    except ValueError:
        pass
    if len(value) > 253:
        return None
    labels = value.split(".")
    if any(
        not label or len(label) > 63 or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
        for label in labels
    ):
        return None
    return value


def _parse_port(value: str) -> int | None:
    try:
        port = int(value)
    except (TypeError, ValueError):
        return None
    return port if 0 < port <= 65535 else None


def normalize_ip(value: str) -> tuple[str | None, int | None]:
    raw = value.strip()
    port: int | None = None
    if "|" in raw:
        raw, port_text = raw.split("|", 1)
        port = _parse_port(port_text)
        if port is None:
            return None, None
    elif raw.startswith("["):
        closing = raw.find("]")
        if closing < 0:
            return None, None
        host = raw[1:closing]
        suffix = raw[closing + 1 :]
        if suffix:
            if not suffix.startswith(":"):
                return None, None
            port = _parse_port(suffix[1:])
            if port is None:
                return None, None
        raw = host
    elif raw.count(":") == 1:
        host, port_text = raw.rsplit(":", 1)
        parsed_port = _parse_port(port_text)
        if parsed_port is not None:
            raw, port = host, parsed_port

    try:
        return ipaddress.ip_address(raw.strip()).compressed.lower(), port
    except ValueError:
        return None, None


def normalize_url(value: str) -> str | None:
    cleaned = restore_defanged_url(value)
    try:
        parts = urlsplit(cleaned)
        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
            return None
        host = parts.hostname.lower()
        try:
            host = ipaddress.ip_address(host).compressed.lower()
            host_text = f"[{host}]" if ":" in host else host
        except ValueError:
            host_text = normalize_domain(host) or ""
            if not host_text:
                return None
        port = f":{parts.port}" if parts.port is not None else ""
        userinfo = ""
        if parts.username is not None:
            userinfo = parts.username
            if parts.password is not None:
                userinfo += f":{parts.password}"
            userinfo += "@"
        normalised = SplitResult(
            parts.scheme.lower(),
            userinfo + host_text + port,
            parts.path or "/",
            parts.query,
            "",
        )
        return urlunsplit(normalised)
    except (ValueError, UnicodeError):
        return None


def normalize_misp_url(value: str) -> str | None:
    normalized = normalize_url(value)
    if normalized:
        return normalized
    cleaned = restore_defanged_url(value)
    if not cleaned or cleaned.startswith(("/", "#")) or any(char.isspace() for char in cleaned):
        return None
    if cleaned.startswith("//"):
        return normalize_url(f"http:{cleaned}")
    host_candidate = cleaned.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    if "." not in host_candidate and normalize_ip(host_candidate)[0] is None:
        return None
    return normalize_url(f"http://{cleaned}")
