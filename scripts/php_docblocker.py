#!/usr/bin/env python3
"""Add PHP function docblocks using an Ollama chat model."""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_CONFIG = Path.home() / ".config" / "php-docblocker" / "config.json"
FUNCTION_RE = re.compile(
    r"\bfunction\s*&?\s*([A-Za-z_][A-Za-z0-9_]*)\s*\([^;{}]*\)\s*(?::\s*[^\s{;]+(?:\s*\|\s*[^\s{;]+)*)?\s*(?:\{|;)",
    re.MULTILINE,
)


def load_config(config_path):
    config = {"api_url": "http://localhost:11434", "model": "qwen2.5-coder:7b", "timeout_seconds": 120}
    if config_path.exists():
        try:
            loaded = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("Could not read config file {}: {}".format(config_path, exc))
        if not isinstance(loaded, dict):
            raise RuntimeError("Config file must contain a JSON object: {}".format(config_path))
        config.update(loaded)
    config["api_url"] = os.environ.get("OLLAMA_API_URL", config["api_url"]).rstrip("/")
    config["model"] = os.environ.get("OLLAMA_MODEL", config["model"])
    if "OLLAMA_TIMEOUT_SECONDS" in os.environ:
        config["timeout_seconds"] = int(os.environ["OLLAMA_TIMEOUT_SECONDS"])
    if not config.get("api_url") or not config.get("model"):
        raise RuntimeError("Both api_url and model must be configured")
    return config


def request_docblock(config, function_source, function_name):
    prompt = (
        "Write a PHPDoc block for this PHP function or method. Return only the complete PHPDoc comment, "
        "starting with /** and ending with */. Include useful @param tags with accurate PHP types, "
        "@return when appropriate, and a concise description. When the function returns an associative "
        "array, use a PHPDoc array shape in @return (for example, array{{success: bool, data: User}}); "
        "document every returned key with its inferred value type, and mark keys optional with ? when "
        "they are absent on some return paths (for example, array{{data?: User}}). Do not describe a "
        "plain list as an array shape. Do not repeat the function code. Do not invent behavior, keys, "
        "or types unsupported by the code.\n\n"
        "Function name: {}\n\n{}"
    ).format(function_name, function_source)
    body = json.dumps({
        "model": config["model"],
        "stream": False,
        "messages": [
            {"role": "system", "content": "You write accurate, concise PHPDoc for PHP code."},
            {"role": "user", "content": prompt},
        ],
        "options": {"temperature": 0.1},
    }).encode("utf-8")
    req = urllib.request.Request(
        config["api_url"] + "/api/chat", data=body,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=int(config.get("timeout_seconds", 120))) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError("Ollama returned HTTP {}: {}".format(exc.code, detail))
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError("Could not reach Ollama at {}: {}".format(config["api_url"], exc))
    try:
        text = payload["message"]["content"].strip()
    except (KeyError, TypeError):
        raise RuntimeError("Ollama response did not contain message.content")
    text = re.sub(r"^```(?:php|PHP)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    match = re.search(r"/\*\*.*?\*/", text, flags=re.DOTALL)
    if not match:
        raise RuntimeError("Ollama did not return a PHPDoc comment")
    return match.group(0)


def function_end(source, match):
    """Return the end of a function declaration, balancing braces while ignoring strings/comments."""
    opening = source.find("{", match.start(), match.end())
    if opening < 0:
        return match.end()
    depth = 0
    quote = None
    line_comment = False
    block_comment = False
    i = opening
    while i < len(source):
        char = source[i]
        nxt = source[i + 1] if i + 1 < len(source) else ""
        if line_comment:
            if char == "\n":
                line_comment = False
        elif block_comment:
            if char == "*" and nxt == "/":
                block_comment = False
                i += 1
        elif quote:
            if char == "\\":
                i += 1
            elif char == quote:
                quote = None
        elif char in ("'", '"', "`"):
            quote = char
        elif char == "/" and nxt == "*":
            block_comment = True
            i += 1
        elif char == "/" and nxt == "/":
            line_comment = True
            i += 1
        elif char == "#":
            line_comment = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise RuntimeError("Unbalanced braces while reading function {}".format(match.group(1)))


def preceding_docblock(source, function_start):
    prefix = source[:function_start]
    return re.search(r"/\*\*.*?\*/\s*$", prefix, flags=re.DOTALL) is not None


def indent_at(source, position):
    line_start = source.rfind("\n", 0, position) + 1
    prefix = source[line_start:position]
    indentation = re.match(r"[ \t]*", prefix)
    return indentation.group(0)


def declaration_start(source, function_start):
    line_start = source.rfind("\n", 0, function_start) + 1
    before = source[line_start:function_start]
    if before.strip() and re.fullmatch(
        r"\s*(?:(?:public|protected|private|static|final|abstract|readonly)\s+)+", before
    ):
        return line_start
    if not before.strip():
        return line_start
    return function_start


def format_docblock(docblock, indent):
    lines = docblock.splitlines()
    return "\n".join((indent + line if line else indent) for line in lines)


def process_source(source, config):
    matches = list(FUNCTION_RE.finditer(source))
    if not matches:
        raise RuntimeError("No named PHP functions or methods found")
    edits = []
    skipped = 0
    for match in matches:
        start = declaration_start(source, match.start())
        if preceding_docblock(source, start):
            skipped += 1
            continue
        end = function_end(source, match)
        function_source = source[start:end]
        docblock = request_docblock(config, function_source, match.group(1))
        indent = indent_at(source, match.start())
        insertion = format_docblock(docblock, indent) + "\n"
        edits.append((start, insertion))
    for position, insertion in reversed(edits):
        source = source[:position] + insertion + source[position:]
    return source, len(edits), skipped


def process_selection(source, selection, config):
    if not selection:
        raise RuntimeError("Select PHP code in the editor first")
    # Zed task interpolation can normalize line breaks or indentation in selected text.
    # Match the same non-whitespace tokens while allowing the saved file's whitespace.
    tokens = selection.split()
    if not tokens:
        raise RuntimeError("Select PHP code in the editor first")
    pattern = r"\s+".join(re.escape(token) for token in tokens)
    matches = list(re.finditer(pattern, source))
    if len(matches) != 1:
        raise RuntimeError(
            "The selection must match uniquely in the saved file (found {} matches). Save the file and retry."
            .format(len(matches))
        )
    match = matches[0]
    start, end = match.span()
    # Include the declaration line's original indentation when the selection begins
    # after it, so generated PHPDoc uses the exact indentation from the saved source.
    line_start = source.rfind("\n", 0, start) + 1
    if source[line_start:start].strip() == "":
        start = line_start
    selected_source = source[start:end]
    updated, added, skipped = process_source(selected_source, config)
    if added == 0:
        return source, added, skipped
    return source[:start] + updated + source[end:], added, skipped


def _run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, help="PHP file to update")
    parser.add_argument("--selection", help="Exact selected source from Zed")
    parser.add_argument(
        "--selection-stdin", action="store_true",
        help="Read selected source from standard input"
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    if args.selection is not None and args.selection_stdin:
        raise RuntimeError("Use either --selection or --selection-stdin, not both")
    path = Path(args.file)
    if path.suffix.lower() != ".php":
        raise RuntimeError("The active file must have a .php extension")
    source = path.read_text(encoding="utf-8")
    config = load_config(args.config)
    selection = sys.stdin.read() if args.selection_stdin else args.selection
    if selection is None:
        updated, added, skipped = process_source(source, config)
    else:
        updated, added, skipped = process_selection(source, selection, config)
    if updated != source:
        path.write_text(updated, encoding="utf-8")
    print("Added {} docblock(s); skipped {} function(s) with an existing docblock.".format(added, skipped))
    print("Updated {}".format(path))


def main():
    try:
        _run()
    except (OSError, RuntimeError, ValueError) as error:
        print("php-docblocker: {}".format(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
