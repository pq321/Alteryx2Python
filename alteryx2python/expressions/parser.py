from __future__ import annotations

from alteryx2python.expressions.ast import (
    BinaryExpression,
    ConditionalExpression,
    FieldReference,
    FunctionExpression,
    LiteralExpression,
    UnaryExpression,
)
from alteryx2python.expressions.errors import UnsupportedExpressionError
from alteryx2python.expressions.lexer import tokenize


SUPPORTED_FUNCTIONS = {
    "DATETIMEADD",
    "DATETIMEDIFF",
    "AVERAGE",
    "ISNULL",
    "ISEMPTY",
    "LEFT",
    "PADLEFT",
    "REPLACE",
    "REGEX_MATCH",
    "REGEX_REPLACE",
    "ROUND",
    "RIGHT",
    "STARTSWITH",
    "TITLECASE",
    "TRIM",
    "TOSTRING",
    "NULL",
    "UPPERCASE",
}


class _ExpressionParser:
    def __init__(self, tokens: list[str]) -> None:
        self.tokens = tokens
        self.position = 0

    def parse(self):
        if self._match_keyword("IF"):
            return self._parse_if()
        node = self._parse_or()
        if self._peek() is not None:
            raise UnsupportedExpressionError(f"Unexpected expression token: {self._peek()}")
        return node

    def _parse_if(self):
        condition = self._parse_or()
        self._expect_keyword("THEN")
        true_value = self._parse_or(stop_keywords={"ELSE", "ELSEIF"})
        if self._match_keyword("ELSEIF"):
            false_value = self._parse_if_tail()
        else:
            self._expect_keyword("ELSE")
            false_value = self._parse_or(stop_keywords={"ENDIF"})
        self._expect_keyword("ENDIF")
        return ConditionalExpression(condition=condition, true_value=true_value, false_value=false_value)

    def _parse_if_tail(self):
        condition = self._parse_or()
        self._expect_keyword("THEN")
        true_value = self._parse_or(stop_keywords={"ELSE", "ELSEIF"})
        if self._match_keyword("ELSEIF"):
            false_value = self._parse_if_tail()
        else:
            self._expect_keyword("ELSE")
            false_value = self._parse_or(stop_keywords={"ENDIF"})
        return ConditionalExpression(condition=condition, true_value=true_value, false_value=false_value)

    def _parse_or(self, stop_keywords: set[str] | None = None):
        node = self._parse_and(stop_keywords)
        while self._match_keyword("OR", stop_keywords):
            node = BinaryExpression(node, "OR", self._parse_and(stop_keywords))
        return node

    def _parse_and(self, stop_keywords: set[str] | None = None):
        node = self._parse_comparison(stop_keywords)
        while self._match_keyword("AND", stop_keywords):
            node = BinaryExpression(node, "AND", self._parse_comparison(stop_keywords))
        return node

    def _parse_comparison(self, stop_keywords: set[str] | None = None):
        node = self._parse_additive(stop_keywords)
        while self._peek() in {">", ">=", "<", "<=", "=", "==", "!="}:
            operator = self._advance()
            node = BinaryExpression(node, operator, self._parse_additive(stop_keywords))
        return node

    def _parse_additive(self, stop_keywords: set[str] | None = None):
        node = self._parse_multiplicative(stop_keywords)
        while self._peek() in {"+", "-"}:
            operator = self._advance()
            node = BinaryExpression(node, operator, self._parse_multiplicative(stop_keywords))
        return node

    def _parse_multiplicative(self, stop_keywords: set[str] | None = None):
        node = self._parse_unary(stop_keywords)
        while self._peek() in {"*", "/"}:
            operator = self._advance()
            node = BinaryExpression(node, operator, self._parse_unary(stop_keywords))
        return node

    def _parse_unary(self, stop_keywords: set[str] | None = None):
        if self._peek() == "!":
            self._advance()
            return UnaryExpression("!", self._parse_unary(stop_keywords))
        return self._parse_primary(stop_keywords)

    def _parse_primary(self, stop_keywords: set[str] | None = None):
        token = self._peek()
        if token is None:
            raise UnsupportedExpressionError("Unexpected end of expression")
        if stop_keywords and token.upper() in stop_keywords:
            raise UnsupportedExpressionError(f"Unexpected expression terminator: {token}")
        if token == "(":
            self._advance()
            node = self._parse_or()
            self._expect(")")
            return node
        if token.startswith("[") and token.endswith("]"):
            self._advance()
            return FieldReference(token[1:-1])
        if (token.startswith('"') and token.endswith('"')) or (token.startswith("'") and token.endswith("'")):
            self._advance()
            return LiteralExpression(token[1:-1].replace('\\"', '"'))
        if token.upper() in {'TRUE', 'FALSE'} and not self._looks_like_function():
            self._advance()
            return LiteralExpression(token.upper() == 'TRUE')
        if _is_number(token):
            self._advance()
            return LiteralExpression(float(token) if "." in token else int(token))
        if self._looks_like_function():
            return self._parse_function()
        if _is_identifier(token):
            self._advance()
            return FieldReference(token)
        raise UnsupportedExpressionError(f"Unsupported expression token: {token}")

    def _parse_function(self):
        name = self._advance()
        normalized_name = name.upper()
        if normalized_name not in SUPPORTED_FUNCTIONS:
            raise UnsupportedExpressionError(f"Unsupported expression function: {name}")
        self._expect("(")
        args = []
        if self._peek() != ")":
            while True:
                args.append(self._parse_or())
                if self._peek() != ",":
                    break
                self._advance()
        self._expect(")")
        return FunctionExpression(name=name, args=args)

    def _looks_like_function(self) -> bool:
        return self.position + 1 < len(self.tokens) and self.tokens[self.position + 1] == "("

    def _peek(self) -> str | None:
        if self.position >= len(self.tokens):
            return None
        return self.tokens[self.position]

    def _advance(self) -> str:
        token = self._peek()
        if token is None:
            raise UnsupportedExpressionError("Unexpected end of expression")
        self.position += 1
        return token

    def _expect(self, expected: str) -> None:
        token = self._advance()
        if token != expected:
            raise UnsupportedExpressionError(f"Expected {expected}, got {token}")

    def _expect_keyword(self, keyword: str) -> None:
        token = self._advance()
        if token.upper() != keyword:
            raise UnsupportedExpressionError(f"Expected {keyword}, got {token}")

    def _match_keyword(self, keyword: str, stop_keywords: set[str] | None = None) -> bool:
        token = self._peek()
        if token is None:
            return False
        if stop_keywords and token.upper() in stop_keywords:
            return False
        if token.upper() != keyword:
            return False
        self.position += 1
        return True


def _is_number(token: str) -> bool:
    try:
        float(token)
    except ValueError:
        return False
    return True


def _is_identifier(token: str) -> bool:
    return token.replace("_", "").isalnum() and not token[0].isdigit()


def parse_expression(expression: str):
    stripped = expression.strip()
    if not stripped:
        raise UnsupportedExpressionError("Empty expressions are not supported")
    return _ExpressionParser(tokenize(stripped)).parse()
