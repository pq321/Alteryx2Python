from __future__ import annotations


def tokenize(expression: str) -> list[str]:
    return expression.replace("(", " ( ").replace(")", " ) ").split()