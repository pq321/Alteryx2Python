"""Handwritten transaction report driven by seven Analytic App input types."""

import csv
import ntpath
from pathlib import Path


REPORT_COLUMNS = ("trade_id", "region", "report_date", "label", "display_amount", "report_path")


def run_report(answers, output_dir):
    """Apply the selected region, archive policy, and level of detail."""
    with Path(answers["input_file"]).open(encoding="utf-8", newline="") as stream:
        trades = list(csv.DictReader(stream))

    show_amounts = answers["detail"] and not answers["summary"]
    output_dir.mkdir(parents=True)
    with (output_dir / "report.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, REPORT_COLUMNS)
        writer.writeheader()
        for trade in trades:
            if trade["region"] != answers["region"]:
                continue
            if trade["status"] != "posted" and not answers["include_archived"]:
                continue
            writer.writerow({
                "trade_id": trade["trade_id"],
                "region": trade["region"],
                "report_date": answers["report_date"],
                "label": trade["trade_id"] + " " + answers["suffix"],
                "display_amount": int(trade["amount"]) if show_amounts else 0,
                "report_path": ntpath.join(answers["report_folder"], "summary.csv"),
            })
