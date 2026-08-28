import argparse
import json
from pathlib import Path

from aug9.discovery.food_ranking_evaluation import evaluate_food_ranking


DEFAULT_EVALUATION_PATH = Path("data/food_ranking_evaluation_v1.json")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate the offline food-ranking policy"
    )
    parser.add_argument("--file", type=Path, default=DEFAULT_EVALUATION_PATH)
    args = parser.parse_args()
    report = evaluate_food_ranking(args.file)
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
