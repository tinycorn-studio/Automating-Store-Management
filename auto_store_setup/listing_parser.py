"""
ListingParser - Reads & validates Store Listing data from Google Sheets or Excel.

Supports a "field-per-row, locale-per-column" format:

    | field             | en-US               | vi                    |
    |-------------------|----------------------|-----------------------|
    | app_name          | Water Go Puzzle      | Water Go - Xếp Hình   |
    | short_description | Fun puzzle game!     | Trò chơi giải đố vui! |
    | full_description  | ...                  | ...                   |
    | keywords          | puzzle,water         | xếp hình,nước         |
    | promo_text        | New levels available | Có màn mới!           |
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Recognised field names (row labels in the "field" column)
KNOWN_FIELDS = {
    "app_name",
    "short_description",
    "full_description",
    "keywords",          # iOS only — comma-separated
    "promo_text",        # iOS only — shown above description
    "support_url",
    "marketing_url",
    "privacy_policy_url",
}


@dataclass
class LocalizedListing:
    """Listing metadata for a single locale."""

    locale: str
    app_name: str = ""
    short_description: str = ""
    full_description: str = ""
    keywords: str = ""
    promo_text: str = ""
    support_url: str = ""
    marketing_url: str = ""
    privacy_policy_url: str = ""


@dataclass
class StoreListingData:
    """Container holding listings for all locales."""

    listings: list[LocalizedListing] = field(default_factory=list)

    @property
    def locales(self) -> list[str]:
        return [l.locale for l in self.listings]

    def get(self, locale: str) -> LocalizedListing | None:
        for l in self.listings:
            if l.locale == locale:
                return l
        return None


class ListingParser:
    """
    Parses the "Store Listing" worksheet and returns StoreListingData.

    Parameters
    ----------
    source : str
        "excel" or "gsheet".
    file_path : Path or None
        Path to .xlsx file (Excel mode).
    google_sheet_id : str
        Google Sheet ID (gsheet mode).
    worksheet : str
        Worksheet name, defaults to "Store Listing".
    service_account_json : Path or None
        Path to GCP service account JSON key.
    """

    DEFAULT_WORKSHEET = "Store Listing"

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

    def parse(self) -> StoreListingData:
        """Read the listing worksheet and return structured StoreListingData."""
        if self.source == "gsheet":
            df = self._read_google_sheet()
        else:
            df = self._read_excel()

        return self._build_listing_data(df)

    # --------------------------------------------------------------------- #
    #  Readers                                                               #
    # --------------------------------------------------------------------- #

    def _read_excel(self) -> pd.DataFrame:
        logger.info("📄 Reading Store Listing from Excel: %s [%s]", self.file_path, self.worksheet)
        if not self.file_path or not self.file_path.exists():
            raise FileNotFoundError(f"Excel file not found: {self.file_path}")
        return pd.read_excel(self.file_path, sheet_name=self.worksheet, engine="openpyxl")

    def _read_google_sheet(self) -> pd.DataFrame:
        import gspread

        logger.info(
            "☁️  Reading Store Listing from Google Sheet: %s [%s]",
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
    def _build_listing_data(df: pd.DataFrame) -> StoreListingData:
        """
        Convert the field-per-row DataFrame into StoreListingData.

        Expected format:
            First column = "field" (row labels)
            Remaining columns = locale codes (e.g. "en-US", "vi")
        """
        if df.empty:
            raise ValueError("Store Listing worksheet is empty.")

        # Identify columns
        columns = list(df.columns)
        if "field" not in columns:
            raise ValueError(
                "Store Listing worksheet must have a 'field' column as the first column."
            )

        locale_columns = [c for c in columns if c != "field"]
        if not locale_columns:
            raise ValueError("Store Listing worksheet must have at least one locale column (e.g. 'en-US').")

        logger.info("   Found %d fields × %d locales: %s", len(df), len(locale_columns), locale_columns)

        # Build a dict: field_name → {locale → value}
        field_map: dict[str, dict[str, str]] = {}
        for _, row in df.iterrows():
            field_name = str(row["field"]).strip().lower()
            if not field_name or field_name == "nan":
                continue
            field_map[field_name] = {}
            for locale in locale_columns:
                val = str(row.get(locale, "")).strip()
                if val and val != "nan":
                    field_map[field_name][locale] = val

        # Build listings per locale
        listings: list[LocalizedListing] = []
        for locale in locale_columns:
            listing = LocalizedListing(locale=locale)
            for field_name, locale_vals in field_map.items():
                val = locale_vals.get(locale, "")
                if hasattr(listing, field_name):
                    setattr(listing, field_name, val)
                else:
                    logger.warning("   Unknown field '%s' in Store Listing — skipping.", field_name)
            listings.append(listing)

        logger.info("✅ Parsed Store Listing for %d locales.", len(listings))
        return StoreListingData(listings=listings)
