from __future__ import annotations


def render_whois(record: dict[str, str | list[str]]) -> str:
    """Convert a WHOIS key-value record into a prose paragraph for embedding.

    Prose form embeds better than raw key-value pairs because it captures
    relationships between fields in natural language.
    """
    domain = record.get("domain", "unknown domain")
    registrar = record.get("registrar", "unknown registrar")
    iana_id = record.get("iana_id", "")
    created = record.get("created", "")
    expires = record.get("expires", "")
    updated = record.get("updated", "")
    registrant_email = record.get("registrant_email", "")
    name_servers = record.get("name_servers", [])
    status = record.get("status", [])

    registrar_str = f"{registrar} (IANA ID: {iana_id})" if iana_id else registrar

    parts = [f"Domain {domain} is registered with {registrar_str}."]

    if created:
        parts.append(f"It was created on {created}")
        if expires:
            parts[-1] += f" and expires on {expires}."
        else:
            parts[-1] += "."

    if updated:
        parts.append(f"Last updated: {updated}.")

    if registrant_email:
        parts.append(f"Registrant contact email: {registrant_email}.")

    if name_servers:
        ns_list = name_servers if isinstance(name_servers, list) else [name_servers]
        parts.append(f"Name servers: {', '.join(str(ns) for ns in ns_list)}.")

    if status:
        status_list = status if isinstance(status, list) else [status]
        parts.append(f"Registration status: {', '.join(str(s) for s in status_list)}.")

    return " ".join(parts)
