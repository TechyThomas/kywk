"""Dispatch Kywk task groups to their optional executables."""

import argparse
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="kywk",
        description="Run a Kywk task group (install kywk-php or kywk-git as needed).",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--php", action="store_true", help="run kywk-php")
    group.add_argument("--git", action="store_true", help="run kywk-git")
    args, remainder = parser.parse_known_args()

    executable = "kywk-php" if args.php else "kywk-git"
    path = shutil.which(executable)
    if path is None:
        print("kywk: required executable {!r} was not found on PATH".format(executable), file=sys.stderr)
        return 127
    return subprocess.call([path] + remainder)


if __name__ == "__main__":
    sys.exit(main())
