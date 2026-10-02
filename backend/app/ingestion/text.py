def decode(content: bytes) -> str:
    """Texto do arquivo em UTF-8 (com ou sem BOM) ou, se não for, Latin-1/Windows-1252 (R1)."""
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return content.decode("cp1252", errors="replace")


def first_line(head: bytes) -> str:
    return decode(head).splitlines()[0].strip() if head.strip() else ""
