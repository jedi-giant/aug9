import argparse
from pathlib import Path

from aug9.discovery.google_takeout_food import convert_google_takeout_food


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare a privacy-minimised food-domain file from Google Takeout"
    )
    parser.add_argument("--input", action="append", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    received, skipped = convert_google_takeout_food(
        args.input, output_path=args.output
    )
    print(
        "Google Takeout food preparation complete: "
        f"prepared={received}, skipped={skipped}, output={args.output}"
    )


if __name__ == "__main__":
    main()
