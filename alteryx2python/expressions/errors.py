class ExpressionError(Exception):
    """Base expression error."""


class UnsupportedExpressionError(ExpressionError):
    """Raised when an Alteryx expression cannot be safely mapped yet."""