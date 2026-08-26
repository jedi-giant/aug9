import json

from aug9.sg_services.catalog_report import build_service_catalog_report


def main() -> None:
    report = build_service_catalog_report()
    print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
