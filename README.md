# Kywk - Dev tools for Zed + Ollama

## What does “Kywk” mean?

“Kywk” is a fun spelling of “Quick.” The project is about getting mundane development tasks done quicker, so you can spend more time on the work that matters.

Kywk provides three commands: `kywk` dispatches to `kywk-php` or `kywk-git`, `kywk-php` provides PHP docblock and review tasks, and `kywk-git` provides Git summary and commit tasks. Use either task executable independently; both task groups use an Ollama model, and Zed exposes the current file, selected text, and project root through its task system.

The PHP tasks are:

- **PHP Docblocker: Current File** adds docblocks to named functions and methods in the saved PHP file.
- **PHP Docblocker: Selection** adds docblocks to named functions and methods in the selected code.
- **PHP Code Review (Ollama): Current File** asks for a review of the saved PHP file and writes a findings report without changing it.
- **PHP Code Review (Ollama): Selection** reviews selected PHP code and writes a findings report without changing it.
- **PHP Code Review (Ollama): Whole Project** reviews source and configuration files across the project in batches and writes one report.
- **PHP Code Review (Ollama): Select Directory** prompts for a project-relative directory, reviews its source/configuration files, and writes one report.

The Git tasks are:

- **Git Summary (Ollama): Today's Commits** summarizes commits authored today in the project and writes a Markdown report.
- **Git Summary (Ollama): Commits on Date** prompts for a date in `YYYY-MM-DD` format and summarizes commits authored on that date.
- **Git Commit (Ollama): Review Message & Confirm** generates a message from current project changes and creates a commit only after confirmation.

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

Download the archive for your operating system and CPU architecture from the project's [GitHub Releases](https://github.com/TechyThomas/kywk/releases) page, then extract it. Each archive contains the three ready-to-run executables: `kywk` (the dispatcher), `kywk-php`, and `kywk-git`. Put the extracted directory on `PATH` so Zed can find all three commands. Copy the task definitions from [`.zed/tasks.json`](.zed/tasks.json) into any project's `.zed/tasks.json`.

Release archives are built separately for Windows, macOS, and Linux, each with x86_64 and ARM64 (AArch64) binaries. Choose the archive matching both your operating system and CPU architecture; binaries are not interchangeable between operating systems or architectures. Linux binaries are built on Ubuntu and may require a reasonably current glibc. The releases bundle the Python runtime and Kywk scripts, so Python and pip do not need to be installed.

To update an installed release, run `kywk --update`. It downloads the latest release for the current operating system and architecture and updates all three Kywk executables in the same directory. Keep the three executables together and make sure that directory is writable. On Windows, the replacement finishes shortly after the running `kywk` process exits. Binaries that predate the updater must first be replaced manually with the latest archive from GitHub Releases. The updater verifies GitHub's HTTPS certificates using system roots and a bundled public CA bundle. On managed networks, set `SSL_CERT_FILE` to a PEM file containing your organization's trusted CA certificate if needed.

Kywk sends requests to an Ollama server. Install Ollama separately and make sure the configured server is running and reachable; the default is `http://localhost:11434`. A PHP interpreter is not required to use the PHP source editing and review tasks. Git must be installed for the Git tasks. Release binaries are currently unsigned and may trigger a security warning on first run.

### macOS first run

The macOS binaries are not signed or notarized, so Gatekeeper may block them. If you trust the downloaded release, try running the blocked executable once, then open **System Settings → Privacy & Security**, scroll to **Security**, and select **Open Anyway** for Kywk. Confirm the prompt and run it again. Repeat for `kywk-php` or `kywk-git` if macOS blocks either executable separately. See [Apple's instructions for opening an app by overriding security settings](https://support.apple.com/en-gb/guide/mac-help/mh40617/27/mac/27).

To use a release from a source checkout instead, install Python 3.9 or newer and run `python -m pip install --user .` from the repository root. This project has no third-party Python runtime dependencies.

The dispatcher forwards every argument after `--php` or `--git` to the selected executable:

```sh
kywk --php --file ./src/example.php
kywk --git --summarize-daily-commits --project-root .
```

You can also call `kywk-php` or `kywk-git` directly. The dispatcher reports an error if its selected executable is not installed.

## Run in Zed

Open the Command Palette, choose **task: spawn**, then select a PHP Docblocker or PHP Code Review task. Selection tasks only appear when text is selected. Tasks save the current buffer before running. Docblock selection mode requires a unique match in the saved file after normalizing whitespace.

Review tasks create a `.reports` folder in the project root when needed and write each report to a uniquely timestamped Markdown file there. The task terminal prints the report path. The source files are not modified by review tasks. Whole-project review includes common source and configuration formats; it skips dependency, build, cache, report, and credential directories, lockfiles, symlinks, credential-like files, and files larger than 1 MiB. Files are sent to the configured Ollama endpoint in bounded batches, so review findings may not capture issues that depend on relationships between files in different batches. Only use a trusted endpoint.

The daily commit summary uses the machine's local date and the repository's configured Git author email (or name when no email is configured) to identify your commits. It searches commits reachable from Git refs, includes their messages and diffs in the Ollama request, and writes a timestamped `.reports/daily-commit-summary-*.md` file. It creates a report even when no matching commits are found. Large diffs are truncated before sending; large days are summarized in separate batches.

The **Commits on Date** task uses the same author matching and report format, after prompting for a valid calendar date in `YYYY-MM-DD` format. It writes a timestamped Markdown report under `.reports`.

The Git commit task sends the current tracked changes and untracked, non-ignored files to Ollama to propose a commit title and description. It displays both and waits for `y` to confirm, `e` to replace the title and description, or `n` to cancel. After confirmation, it stages all current project changes and runs `git commit`. It checks that the change set stayed the same while awaiting confirmation; if it changed, the task stops without committing. The model receives project diffs, so use a trusted Ollama endpoint.

The **Select Directory** task lists project subdirectories in the task terminal and accepts either a listed number or a project-relative path. It only scans the chosen directory, while saving the timestamped report under the project root's `.reports` folder.

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
