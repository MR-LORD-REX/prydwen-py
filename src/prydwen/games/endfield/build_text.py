"""Deterministic prose-only concise views; structural guide data always stays intact."""

from __future__ import annotations

import re
from typing import Any

from prydwen.core.models import Model

from .models.builds import CharacterBuild, CharacterReview, GuideBlock


def concise_text(value: str, highlights: list[str] | None = None) -> str:
    """Extract source sentences favoring emphasis, conditions, and actionable recommendations."""
    if len(value) <= 240:
        return value
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z"(])', value)
    if len(sentences) < 2:
        return value
    emphasis = highlights or []

    def score(sentence: str) -> int:
        """Prefer source emphasis and concrete conditions without rewriting their meaning."""
        return (
            sum(phrase.casefold() in sentence.casefold() for phrase in emphasis) * 5
            + len(
                re.findall(
                    r"\b(?:best|must|only|requires?|unless|when|however|instead|avoid|recommended|important)\b",
                    sentence,
                    re.I,
                )
            )
            * 2
            + bool(re.search(r"\d", sentence))
        )

    selected = {0}
    for index in sorted(
        range(1, len(sentences)), key=lambda position: (-score(sentences[position]), position)
    ):
        if len(selected) >= 2 or sum(len(sentences[position]) for position in selected) >= 220:
            break
        selected.add(index)
    return " ".join(sentences[index] for index in sorted(selected))


def concise_build(data: CharacterBuild) -> CharacterBuild:
    """Shorten prose only, preserving all records, emphasis, links, charts, and rotations."""

    def visit(value: Any) -> Any:
        """Copy nested models and shorten only explicitly descriptive text fields."""
        if isinstance(value, Model):
            updates = {name: visit(getattr(value, name)) for name in type(value).model_fields}
            if isinstance(value, GuideBlock):
                if value.text is not None and value.kind in {"paragraph", "callout"}:
                    updates["text"] = concise_text(value.text, value.highlights)
                updates["items"] = [concise_text(item, value.highlights) for item in value.items]
            elif isinstance(value, CharacterReview):
                updates["pros"] = [concise_text(item) for item in value.pros]
                updates["cons"] = [concise_text(item) for item in value.cons]
            return value.model_copy(update=updates)
        if isinstance(value, list):
            return [visit(child) for child in value]
        if isinstance(value, dict):
            return {key: visit(child) for key, child in value.items()}
        return value

    result: CharacterBuild = visit(data)
    return result.model_copy(update={"detailed": False})
