"""Preserve known local resource references when relocating a native document."""

from pathlib import Path
import re


def resolve_file_references(root, source):
    rewrites = []
    for element in root.iter():
        candidates = []
        if element.tag in {"File", "Directory", "RootFileName"} and element.text:
            candidates.append(("text", element.text))
        if element.tag == "EngineSettings" and element.get("Macro"):
            candidates.append(("Macro", element.get("Macro")))
        for key, value in candidates:
            path_part, separator, suffix = value.partition("|||")
            if not path_part or "://" in path_part or re.search(r"[%;<>\n]", path_part):
                continue
            if re.match(r"^[A-Za-z][A-Za-z0-9_ ]*[:=]", path_part) and not re.match(
                r"^[A-Za-z]:[\\/]", path_part
            ):
                continue
            path = Path(path_part)
            if path.is_absolute():
                continue
            resolved = Path(source).parent / path
            if key == "Macro" and not resolved.exists():
                continue
            replacement = str(resolved.resolve()) + separator + suffix
            if key == "text":
                element.text = replacement
            else:
                element.set(key, replacement)
            rewrites.append(
                {"tag": element.tag, "original": value, "resolved": replacement}
            )
    return rewrites
