# TextToColumns

Status: `L2_BASIC_IMPLEMENTATION`

Supported anchors:

- Input: `Input`
- Output: `Output`

Implemented semantics:

- split configured field using Alteryx delimiter strings
- column output mode with `RootName` and `NumFields`
- row output mode when the row-splitting flag is set
- `Last` overflow handling for column mode

Deferred semantics:

- quote-aware splitting flags
- exact error-row behavior for every overflow mode
