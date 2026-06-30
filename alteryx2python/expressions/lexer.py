from __future__ import annotations


def tokenize(expression: str) -> list[str]:
    tokens: list[str] = []
    index = 0
    while index < len(expression):
        char = expression[index]
        if char.isspace():
            index += 1
            continue
        if char in {'"', "'"}:
            quote = char
            end = index + 1
            escaped = False
            while end < len(expression):
                if expression[end] == quote and not escaped:
                    break
                escaped = expression[end] == "\\" and not escaped
                if expression[end] != "\\":
                    escaped = False
                end += 1
            if end >= len(expression):
                tokens.append(expression[index:])
                break
            tokens.append(expression[index : end + 1])
            index = end + 1
            continue
        if char == "[":
            end = expression.find("]", index + 1)
            if end == -1:
                tokens.append(expression[index:])
                break
            tokens.append(expression[index : end + 1])
            index = end + 1
            continue
        if expression[index : index + 2] in {">=", "<=", "==", "!="}:
            tokens.append(expression[index : index + 2])
            index += 2
            continue
        if char in "(),+-*/><!=":
            tokens.append(char)
            index += 1
            continue
        end = index
        while end < len(expression) and not expression[end].isspace() and expression[end] not in "(),+-*/><!=":
            end += 1
        tokens.append(expression[index:end])
        index = end
    return tokens
