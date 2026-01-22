import argparse
import pathlib
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--key-path",
        default="~/.tauri/syntropy.key",
        help="Private key output path (will also create .pub next to it)",
    )
    parser.add_argument(
        "--cwd",
        default=None,
        help="Project root directory (defaults to this script's repo root)",
    )
    parser.add_argument(
        "--print-pubkey",
        action="store_true",
        default=True,
        help="Print pubkey content to stdout",
    )
    args = parser.parse_args()

    key_path = pathlib.Path(args.key_path).expanduser().resolve()
    key_path.parent.mkdir(parents=True, exist_ok=True)

    if args.cwd:
        cwd = pathlib.Path(args.cwd).expanduser().resolve()
    else:
        cwd = pathlib.Path(__file__).resolve().parents[2]

    cmd = [
        "npm",
        "run",
        "tauri",
        "--",
        "signer",
        "generate",
        "-w",
        str(key_path),
    ]
    proc = subprocess.run(cmd, cwd=str(cwd))
    if proc.returncode != 0:
        return proc.returncode

    pub_path = pathlib.Path(str(key_path) + ".pub")
    if not pub_path.exists():
        print(f"Expected pubkey file not found: {pub_path}", file=sys.stderr)
        return 2

    if args.print_pubkey:
        pubkey = pub_path.read_text(encoding="utf-8").strip()
        print(pubkey)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
