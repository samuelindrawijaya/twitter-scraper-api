import csv
import re
from pathlib import Path
from typing import Any

from app.config.settings import settings
from app.services.tweet_normalizer_service import CSV_COLUMNS


class CsvExportService:
    def __init__(self, output_dir: str | Path | None = None) -> None:
        self.output_dir = Path(output_dir or settings.OUTPUT_DIR)

    def save(self, rows: list[dict[str, Any]], output_name: str | None) -> str:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        safe_name = self._sanitize_filename(output_name or "twitter_dataset.csv")
        path = self.output_dir / safe_name

        with path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

        return str(path)

    def _sanitize_filename(self, name: str) -> str:
        basename = Path(name).name
        basename = re.sub(r"[^A-Za-z0-9._-]", "_", basename).strip("._")
        if not basename:
            basename = "twitter_dataset.csv"
        if not basename.lower().endswith(".csv"):
            basename = f"{basename}.csv"
        return basename
