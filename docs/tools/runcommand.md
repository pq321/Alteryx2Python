# RunCommand

Baseline support records command configuration without executing external programs.

- Input anchor: `Input`
- Output anchor: `Output`
- Current behavior: passes input data through when present, otherwise emits an empty output frame, and records `external_command_executed=false`.
