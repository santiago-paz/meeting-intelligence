"""Small helpers shared by every Claude call."""


def first_text(message) -> str:
    """The first text block of a response; thinking blocks are skipped."""
    for block in message.content:
        if getattr(block, "type", None) == "text":
            return block.text
    return ""
