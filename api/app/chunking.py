from app.models import Chunk, Turn

DEFAULT_MAX_TOKENS = 500


def estimate_tokens(text: str) -> int:
    """Rough token count, about four characters per token.

    The exact tokenizer belongs to the embedding model, not to us, and a
    20% error in chunk size does not change retrieval quality.
    """
    return max(1, len(text) // 4)


def build_chunks(turns: list[Turn], max_tokens: int = DEFAULT_MAX_TOKENS) -> list[Chunk]:
    """Window consecutive turns into chunks of roughly max_tokens.

    A turn is never split, so a single turn longer than the budget becomes
    a chunk on its own. Consecutive chunks share one turn so that a question
    and its answer land together in at least one of them.
    """
    chunks: list[Chunk] = []
    window: list[Turn] = []
    for turn in turns:
        if window and _size(window + [turn]) > max_tokens:
            chunks.append(_to_chunk(len(chunks), window))
            # Overlap: repeat the last turn, unless it is so long that carrying
            # it would push the next chunk over budget too.
            carry = window[-1]
            window = [carry] if _size([carry, turn]) <= max_tokens else []
        window.append(turn)
    if window:
        chunks.append(_to_chunk(len(chunks), window))
    return chunks


def _size(window: list[Turn]) -> int:
    return estimate_tokens(_render(window))


def _render(window: list[Turn]) -> str:
    return "\n".join(_render_turn(turn) for turn in window)


def _to_chunk(idx: int, window: list[Turn]) -> Chunk:
    text = _render(window)
    return Chunk(
        idx=idx,
        turn_start=window[0].idx,
        turn_end=window[-1].idx,
        text=text,
        token_estimate=estimate_tokens(text),
    )


def _render_turn(turn: Turn) -> str:
    return f"{turn.speaker} [{format_timestamp(turn.start_seconds)}]: {turn.text}"


def format_timestamp(seconds: int) -> str:
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def render_numbered_turn(turn: Turn) -> str:
    """One line with the turn index the model cites: #5 Marco [00:00:46]: text."""
    return f"#{turn.idx} {turn.speaker} [{format_timestamp(turn.start_seconds)}]: {turn.text}"


def render_numbered_turns(turns: list[Turn]) -> str:
    return "\n".join(render_numbered_turn(turn) for turn in turns)
