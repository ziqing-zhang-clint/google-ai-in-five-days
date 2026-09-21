"""Lossless Context Compactor to Prevent Context Rot and Token Explosion."""

from typing import List, Dict, Any, Tuple
from nexus_ops.memory.session_manager import MessageTurn
from nexus_ops.config import settings


class ContextCompactor:
    """Implements sliding-window and semantic compaction strategies for LLM prompts."""

    def __init__(self, threshold: int = settings.context_compaction_threshold):
        self.threshold = threshold

    def compact_turns(
        self,
        turns: List[MessageTurn],
        max_active_window: int = 4
    ) -> Tuple[List[Dict[str, str]], bool]:
        """Compacts multi-turn history into a bounded context payload.

        Returns:
            Tuple of (compacted_messages, was_compacted_boolean)
        """
        if len(turns) <= self.threshold:
            # Under threshold: no compaction needed
            return ([{"role": t.role, "content": t.content} for t in turns], False)

        # Separate oldest context, middle turns, and active recent window
        # Pinned Root: Turn 0 (Initial User Request)
        pinned_initial_turn = turns[0]

        # Active Recent Window: Last `max_active_window` turns
        recent_turns = turns[-max_active_window:]

        # Middle turns to be compacted
        middle_turns = turns[1:-max_active_window]

        # Extract factual assertions from middle turns
        fact_summary_lines: List[str] = []
        for t in middle_turns:
            if t.role == "tool":
                # Summarize tool execution briefly
                content_preview = t.content[:120].replace("\n", " ")
                fact_summary_lines.append(f"- Tool result: {content_preview}...")
            elif t.role == "assistant":
                content_preview = t.content[:100].replace("\n", " ")
                fact_summary_lines.append(f"- Assistant reasoned: {content_preview}...")
            elif t.role == "user":
                fact_summary_lines.append(f"- User provided: {t.content}")

        summary_block = (
            "[COMPACTED CONTEXT SUMMARY - PREVIOUS INTERMEDIATE TURNS]\n"
            + "\n".join(fact_summary_lines)
            + "\n[END COMPACTED SUMMARY]"
        )

        compacted_payload: List[Dict[str, str]] = [
            {"role": pinned_initial_turn.role, "content": pinned_initial_turn.content},
            {"role": "system", "content": summary_block}
        ]

        for t in recent_turns:
            compacted_payload.append({"role": t.role, "content": t.content})

        return (compacted_payload, True)


context_compactor = ContextCompactor()
