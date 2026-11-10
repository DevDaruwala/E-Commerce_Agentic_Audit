import json
from pathlib import Path

# data/knowledge.jsonl, found relative to this file (boxes/ -> project root -> data/).
KNOWLEDGE_PATH = Path(__file__).resolve().parent.parent / "data" / "knowledge.jsonl"


def load_alerts(path: Path) -> list[dict]:
    """Read a .jsonl file: one JSON alert per line."""
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


# Fields to drop: model_type, standard_codes and the bookkeeping fields.
# risk_types, risk_description and law_names are KEPT in the cleaned rows (for
# analysis and for the answer/evaluation side). They must never be put into the
# text that is embedded: they give away the danger.
DESCRIPTION_FIELDS_TO_REMOVE = {
    "model_type",
    "standard_codes",
    "case_number",
    "alert_url",
    "report_date",
    "notifying_country",
    "barcode",
    "batch_number",
    "group_id",
}


def clean_row (alerts: list[dict]) -> list[dict]:
    """Return copies of the alerts without the bookkeeping fields.

    Keeps: index, category, product, name, brand, description,
    country_of_origin, risk_types, risk_description, law_names.
    The input alerts are not changed.
    """
    return [
        {key: value for key, value in alert.items() if key not in DESCRIPTION_FIELDS_TO_REMOVE}
        for alert in alerts
    ]


def name_and_description(good_alerts: list[dict]) -> list[dict]:
    """Take the output of clean_row and keep only name and description.

    Each row keeps the "index" stored in data/knowledge.jsonl (1 to 12211), so
    a row can be tracked back even after filtering or sorting. If an alert has
    no "index", its position in the list (from 1) is used instead.
    The input alerts are not changed.
    """
    return [
        {
            "index": alert.get("index", number),
            "name": alert["name"],
            "description": alert["description"],
        }
        for number, alert in enumerate(good_alerts, start=1)
    ]


if __name__ == "__main__":
    cleaned_rows = clean_row(load_alerts(KNOWLEDGE_PATH))
    short = name_and_description(cleaned_rows)
    # Match check on ALL rows: each short row must point back to the same alert.
    for row in short:
        full = cleaned_rows[row["index"] - 1]
        assert full["name"] == row["name"] and full["description"] == row["description"]
    print(f"{len(short)} alerts, all matched. First 5:")
    # Print only the first 5, the file has thousands of alerts.
    for row in short[:5]:
        print(row["index"], json.dumps(row, ensure_ascii=False))
