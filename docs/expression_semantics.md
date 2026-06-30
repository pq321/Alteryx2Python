# Expression Semantics

Status: initial controlled subset for Formula and Filter tools.

Supported expression forms:

- field references: `[FieldName]`
- string and numeric literals
- arithmetic: `+`, `-`, `*`, `/`
- comparisons: `>`, `>=`, `<`, `<=`, `==`, `!=`
- boolean operators: `AND`, `OR`, `!`
- conditional formula expressions: `IF ... THEN ... ELSE ... ENDIF`
- functions: `IsNull`, `StartsWith`, `REGEX_Match`, `REGEX_Replace`, `ROUND`, `Titlecase`, `UPPERCASE`

Known semantic boundaries:

- Unsupported functions fail explicitly with `UnsupportedExpressionError`.
- Null handling currently treats pandas null-like values as Alteryx nulls for `IsNull`.
- Date/time expressions are not implemented yet.
- Type and size coercion for Formula output fields is documented but not enforced.
- Regex support delegates to Python `re`, so any Alteryx-specific regex differences require future certification tests.
