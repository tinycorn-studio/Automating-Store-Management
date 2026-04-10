"""
ScreenshotParser - Reads screenshot manifest from Google Sheets or Excel.

Worksheet format:

    | locale | device_type | display_order | file_path                         |
    |--------|-------------|---------------|-----------------------------------|
    | en-US  | phone_6.5   | 1             | ./screenshots/en/phone_01.png     |
    | en-US  | phone_6.5   | 2             | ./screenshots/en/phone_02.png     |
    | vi     | phone_6.5   | 1             | ./screenshots/vi/phone_01.png     |
    | en-US  | tablet_12.9 | 1             | ./screenshots/en/tablet_01.png    |

file_path can be:
  - A local path (relative to project root)
  - A URL (https://...) — will be downloaded at sync time
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Google Play image types (maps to the API imageType parameter)
GOOGLE_PLAY_IMAGE_TYPES = {
    "phone":        "phoneScreenshots",
    "phone_6.5":    "phoneScreenshots",
    "phone_5.5":    "phoneScreenshots",
    "phone_6.7":    "phoneScreenshots",
    "tablet":       "sevenInchScreenshots",
    "tablet_7":     "sevenInchScreenshots",
    "tablet_10":    "tenInchScreenshots",
    "tablet_12.9":  "tenInchScreenshots",
    "tv":           "tvScreenshots",
    "wear":         "wearScreenshots",
}

# Apple screenshot display types (maps to App Store Connect screenshotDisplayType)
APPLE_DISPLAY_TYPES = {
    "phone":            "APP_IPHONE_67",
    "phone_6.7":        "APP_IPHONE_67",
    "phone_6.5":        "APP_IPHONE_65",
    "phone_5.5":        "APP_IPHONE_55",
    "tablet":           "APP_IPAD_PRO_129",
    "tablet_12.9":      "APP_IPAD_PRO_129",
    "tablet_11":        "APP_IPAD_PRO_3GEN_11",
    "tablet_10.5":      "APP_IPAD_105",
}

REQUIRED_COLUMNS = ["locale", "device_type", "display_order", "file_path"]


@dataclass
class ScreenshotEntry:
    """A single screenshot entry."""

    locale: str
    device_type: str
    display_order: int
    file_path: str       # local path or URL

    @property
    def is_url(self) -> bool:
        return self.file_path.startswith("http://") or self.file_path.startswith("https://")

    @property
    def resolved_path(self) -> Path:
        """Resolve relative local paths from CWD."""
        if self.is_url:
            raise ValueError("Cannot resolve path for a URL — download first.")
        return Path(self.file_path).resolve()

    @property
    def google_image_type(self) -> str:
        return GOOGLE_PLAY_IMAGE_TYPES.get(self.device_type, "phoneScreenshots")

    @property
    def apple_display_type(self) -> str:
        return APPLE_DISPLAY_TYPES.get(self.device_type, "APP_IPHONE_67")


@dataclass
class ScreenshotManifest:
    """All screenshot entries, with convenience grouping methods."""

    entries: list[ScreenshotEntry] = field(default_factory=list)

    @property
    def locales(self) -> list[str]:
        return sorted(set(e.locale for e in self.entries))

    def by_locale(self, locale: str) -> list[ScreenshotEntry]:
        return sorted(
            [e for e in self.entries if e.locale == locale],
            key=lambda e: (e.device_type, e.display_order),
        )

    def by_locale_and_device(self, locale: str, device_type: str) -> list[ScreenshotEntry]:
        return sorted(
            [e for e in self.entries if e.locale == locale and e.device_type == device_type],
            key=lambda e: e.display_order,
        )

    def device_types(self, locale: str) -> list[str]:
        return sorted(set(e.device_type for e in self.entries if e.locale == locale))


class ScreenshotParser:
    """
    Parses the "Screenshots" worksheet and returns a ScreenshotManifest.

    Parameters
    ----------
    source : str
        "excel" or "gsheet".
    file_path : Path or None
        Path to .xlsx file (Excel mode).
    google_sheet_id : str
        Google Sheet ID (gsheet mode).
    worksheet : str
        Worksheet name, defaults to "Screenshots".
    service_account_json : Path or None
        Path to GCP service account JSON key.
    """

    DEFAULT_WORKSHEET = "Screenshots"

    def __init__(
        self,
        source: str = "gsheet",
        file_path: Path | None = None,
        google_sheet_id: str = "",
        worksheet: str = "",
        service_account_json: Path | None = None,
    ) -> None:
        self.source = source
        self.file_path = file_path
        self.google_sheet_id = google_sheet_id
        self.worksheet = worksheet or self.DEFAULT_WORKSHEET
        self.service_account_json = service_account_json

    def parse(self) -> ScreenshotManifest:
        """Read the screenshots worksheet and return a ScreenshotManifest."""
        if self.source == "gsheet":
            df = self._read_google_sheet()
        else:
            df = self._read_excel()

        return self._build_manifest(df)

    # --------------------------------------------------------------------- #
    #  Readers                                                               #
    # --------------------------------------------------------------------- #

    def _read_excel(self) -> pd.DataFrame:
        logger.info("📄 Reading Screenshots from Excel: %s [%s]", self.file_path, self.worksheet)
        if not self.file_path or not self.file_path.exists():
            raise FileNotFoundError(f"Excel file not found: {self.file_path}")
        return pd.read_excel(self.file_path, sheet_name=self.worksheet, engine="openpyxl")

    def _read_google_sheet(self) -> pd.DataFrame:
        import gspread

        logger.info(
            "☁️  Reading Screenshots from Google Sheet: %s [%s]",
            self.google_sheet_id, self.worksheet,
        )
        if not self.service_account_json or not self.service_account_json.exists():
            raise FileNotFoundError(f"Service account JSON not found: {self.service_account_json}")

        try:
            gc = gspread.service_account(filename=str(self.service_account_json))
            spreadsheet = gc.open_by_key(self.google_sheet_id)
            ws = spreadsheet.worksheet(self.worksheet)
            records = ws.get_all_records()
        except gspread.exceptions.WorksheetNotFound:
            raise ValueError(
                f"Worksheet '{self.worksheet}' not found. "
                f"Create a tab named '{self.worksheet}' in your Google Sheet."
            )
        except gspread.exceptions.APIError as exc:
            raise ConnectionError(f"Google Sheets API error: {exc}")

        if not records:
            raise ValueError(f"Worksheet '{self.worksheet}' is empty.")
        return pd.DataFrame(records)

    # --------------------------------------------------------------------- #
    #  Build                                                                 #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _build_manifest(df: pd.DataFrame) -> ScreenshotManifest:
        """Validate and convert DataFrame rows into ScreenshotEntry objects."""
        if df.empty:
            raise ValueError("Screenshots worksheet is empty.")

        missing = set(REQUIRED_COLUMNS) - set(df.columns)
        if missing:
            raise ValueError(
                f"Screenshots worksheet missing columns: {', '.join(sorted(missing))}"
            )

        entries: list[ScreenshotEntry] = []
        errors: list[str] = []

        for idx, row in df.iterrows():
            row_num = idx + 2

            locale = str(row["locale"]).strip()
            device = str(row["device_type"]).strip().lower()
            path = str(row["file_path"]).strip()

            if not locale or locale == "nan":
                errors.append(f"Row {row_num}: locale is empty.")
                continue
            if not path or path == "nan":
                errors.append(f"Row {row_num}: file_path is empty.")
                continue

            try:
                order = int(row["display_order"])
            except (ValueError, TypeError):
                errors.append(f"Row {row_num}: invalid display_order '{row['display_order']}'.")
                continue

            # Validate local file exists (skip for URLs)
            is_url = path.startswith("http://") or path.startswith("https://")
            if not is_url:
                resolved = Path(path).resolve()
                if not resolved.exists():
                    errors.append(f"Row {row_num}: file not found: {resolved}")
                    continue

            entries.append(ScreenshotEntry(
                locale=locale,
                device_type=device,
                display_order=order,
                file_path=path,
            ))

        if errors:
            error_block = "\n  - ".join(errors)
            logger.warning("⚠️  Screenshot validation warnings (%d):\n  - %s", len(errors), error_block)

        if not entries:
            raise ValueError("No valid screenshot entries found.")

        logger.info(
            "✅ Parsed %d screenshots across %d locales.",
            len(entries),
            len(set(e.locale for e in entries)),
        )
        return ScreenshotManifest(entries=entries)
