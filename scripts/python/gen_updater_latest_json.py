import argparse
import json
import pathlib
import sys
from datetime import datetime, timezone


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--notes", default="")
    parser.add_argument("--pub-date", default=None)
    parser.add_argument("--out", default="latest.json")
    parser.add_argument(
        "--add",
        action="append",
        nargs=4,
        metavar=("PLATFORM", "ARTIFACT_PATH", "SIG_PATH", "URL"),
        default=[],
    )
    args = parser.parse_args()

    out_path = pathlib.Path(args.out).expanduser().resolve()
    pub_date = args.pub_date or iso_now()

    if not args.add:
        print("At least one --add entry is required", file=sys.stderr)
        return 2

    if out_path.exists():
        try:
            existing = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Failed to parse existing JSON: {out_path}: {e}", file=sys.stderr)
            return 2
    else:
        existing = {}

    platforms = existing.get("platforms")
    if not isinstance(platforms, dict):
        platforms = {}

    for platform_key, artifact_path, sig_path, url in args.add:
        artifact_file = pathlib.Path(artifact_path).expanduser().resolve()
        sig_file = pathlib.Path(sig_path).expanduser().resolve()
        if not sig_file.exists():
            print(f"Signature file not found: {sig_file}", file=sys.stderr)
            return 2
        if not artifact_file.exists():
            print(f"Artifact file not found: {artifact_file}", file=sys.stderr)
            return 2
        signature = sig_file.read_text(encoding="utf-8").strip()
        platforms[platform_key] = {
            "signature": signature,
            "url": url,
        }

    payload = {
        "version": args.version,
        "notes": args.notes,
        "pub_date": pub_date,
        "platforms": platforms,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
