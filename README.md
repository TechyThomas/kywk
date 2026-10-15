# PHP Docblocker for Zed + Ollama

Generate PHPDoc comments for named PHP functions and methods, or request code reviews, using an Ollama model. Zed exposes the current file, selected text, and project root through its task system, so this project provides these tasks:

- **PHP Docblocker: Current File** adds docblocks to named functions and methods in the saved PHP file.
- **PHP Docblocker: Selection** adds docblocks to named functions and methods in the selected code.
- **PHP Code Review (Ollama): Current File** asks for a review of the saved PHP file and writes a findings report without changing it.
- **PHP Code Review (Ollama): Selection** reviews selected PHP code and writes a findings report without changing it.
- **PHP Code Review (Ollama): Whole Project** reviews source and configuration files across the project in batches and writes one report.

The runner uses only Python's standard library. It sends function code or reviewable project files to Ollama's `/api/chat` endpoint. Docblock tasks insert the returned comment into the file; review tasks write a Markdown report and leave source files unchanged. Existing adjacent PHPDoc comments are skipped.

## Configure Ollama

Create `~/.config/php-docblocker/config.json`:

```json
{
  "api_url": "http://localhost:11434",
  "model": "qwen2.5-coder:7b",
  "timeout_seconds": 120
}
```

Set `api_url` to the Ollama server base URL, including a port if needed. This supports local and remote Ollama servers. If the remote server requires authentication through a proxy, configure that proxy outside this tool; this runner does not currently add custom headers or credentials.

Environment variables override the config file:

- `OLLAMA_API_URL`
- `OLLAMA_MODEL`
- `OLLAMA_TIMEOUT_SECONDS`

## Install the task runner

Install the project as a user command:

```sh
python3 -m pip install --user .
```

Ensure the install location for user scripts is on `PATH` in Zed's environment. Then copy the task definitions from [`.zed/tasks.json`](.zed/tasks.json) into your PHP project's `.zed/tasks.json`.

Alternatively, use the script directly by pointing the task command to the Python interpreter and the full path to `scripts/php_docblocker.py`.

## Run in Zed

Open the Command Palette, choose **task: spawn**, then select a PHP Docblocker or PHP Code Review task. Selection tasks only appear when text is selected. Tasks save the current buffer before running. Docblock selection mode requires a unique match in the saved file after normalizing whitespace.

Review tasks create a `.reports` folder in the project root when needed and write each report to a uniquely timestamped Markdown file there. The task terminal prints the report path. The source files are not modified by review tasks. Whole-project review includes common source and configuration formats; it skips dependency, build, cache, report, and credential directories, lockfiles, symlinks, credential-like files, and files larger than 1 MiB. Files are sent to the configured Ollama endpoint in bounded batches, so review findings may not capture issues that depend on relationships between files in different batches. Only use a trusted endpoint.

Tasks reveal the integrated terminal while running. The runner shows a live spinner during each Ollama request, and whole-project reviews also report the current batch number.

These are Zed Tasks rather than a traditional installable editor extension. Zed's extension API does not currently let extensions register arbitrary source-editor commands that can edit the active buffer. Tasks are the supported mechanism that provides access to `$ZED_FILE` and `$ZED_SELECTED_TEXT`.

## Behavior and limits

- Only named `function` declarations and methods are targeted. Anonymous closures are not independently documented.
- The runner skips a function when a PHPDoc block immediately precedes it.
- For functions returning associative arrays, the prompt asks the model to document returned keys and value types using PHPDoc array-shape syntax in `@return`, including optional keys when appropriate, to support IDE completion.
- Code review tasks write findings to a Markdown report and do not modify the PHP file.
- Selection mode requires a unique match in the saved file after normalizing whitespace. Ambiguous or stale selections produce an error and leave the file untouched.
- Generated comments are inserted into the file on disk. Save first so the saved source matches the editor buffer.
- The model receives each function's source, which may include implementation details. Use a trusted Ollama endpoint.

## AI disclaimer

This project was developed with assistance from OpenAI Codex. Generated docblocks are produced by an AI model through Ollama and may be inaccurate, incomplete, or misleading. Review every generated comment against the code before relying on it. Source code is sent to the Ollama server configured for this tool; only use an endpoint you trust.
