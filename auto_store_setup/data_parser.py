"""
DataParser - Reads & validates IAP data from Excel or Google Sheets.

Supports:
  - Local .xlsx files via pandas + openpyxl
  - Google Sheets via gspread + service account
Returns a list of strongly-typed IAPProduct dataclass instances.
"""

import logging
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Required columns in the spreadsheet
REQUIRED_COLUMNS = [
    "product_id",
    "iap_type",
    "base_price_usd",
    "name_en",
    "desc_en",
    "name_vi",
    "desc_vi",
]

VALID_IAP_TYPES = {"consumable", "non-consumable"}


@dataclass
class IAPProduct:
    """Represents a single In-App Purchase item."""

    product_id: str
    iap_type: str          # "consumable" or "non-consumable"
    base_price_usd: Decimal
    name_en: str
    desc_en: str
    name_vi: str
    desc_vi: str

    @property
    def is_consumable(self) -> bool:
        return self.iap_type == "consumable"

    @property
    def price_micros(self) -> int:
        """Price in micros (1 USD = 1_000_000 micros) used by Google Play."""
        return int(self.base_price_usd * 1_000_000)

    def __str__(self) -> str:
        return (
            f"[{self.iap_type.upper():16s}] "
            f"{self.product_id:45s} "
            f"${self.base_price_usd:>8s}  "
            f"EN: {self.name_en}"
        )


class DataParser:
    """
    Parses IAP data and returns validated IAPProduct objects.

    Supports two modes:
      - **Excel mode**: reads a local .xlsx file
      - **Google Sheets mode**: reads from a Google Sheet via gspread

    Parameters
    ----------
    file_path : Path or None
        Path to the .xlsx file. Required when source == "excel".
    source : str
        "excel" or "gsheet".
    google_sheet_id : str
        Google Spreadsheet ID. Required when source == "gsheet".
    google_sheet_worksheet : str
        Worksheet name. Empty string = first sheet.
    service_account_json : Path or None
        Path to the GCP service account JSON key.
        Required when source == "gsheet".
    """

    def __init__(
        self,
        file_path: Path | None = None,
        source: str = "excel",
        google_sheet_id: str = "",
        google_sheet_worksheet: str = "",
        service_account_json: Path | None = None,
    ) -> None:
        self.file_path = file_path
        self.source = source
        self.google_sheet_id = google_sheet_id
        self.google_sheet_worksheet = google_sheet_worksheet
        self.service_account_json = service_account_json

    # --------------------------------------------------------------------- #
    #  Public API                                                            #
    # --------------------------------------------------------------------- #

    def parse(self) -> list[IAPProduct]:
        """
        Read the data source and return a list of validated IAPProduct items.

        Raises
        ------
        FileNotFoundError
            If the local spreadsheet does not exist (Excel mode).
        ValueError
            If required columns are missing or data validation fails.
        ConnectionError
            If Google Sheets cannot be reached (GSheet mode).
        """
        if self.source == "gsheet":
            df = self._read_google_sheet()
        else:
            df = self._read_excel()

        self._validate_columns(df)
        products = self._build_products(df)

        logger.info("✅ Successfully parsed %d IAP products.", len(products))
        return products

    # --------------------------------------------------------------------- #
    #  Data source readers                                                   #
    # --------------------------------------------------------------------- #

    def _read_excel(self) -> pd.DataFrame:
        """Read from a local .xlsx file."""
        logger.info("📄 Reading local Excel file: %s", self.file_path)

        if not self.file_path or not self.file_path.exists():
            raise FileNotFoundError(f"Spreadsheet not found: {self.file_path}")

        df = pd.read_excel(self.file_path, engine="openpyxl")
        logger.info("   Found %d rows in the spreadsheet.", len(df))
        return df

    def _read_google_sheet(self) -> pd.DataFrame:
        """Read from a Google Sheet using gspread + service account."""
        import gspread

        logger.info(
            "☁️  Reading Google Sheet: %s (worksheet: %s)",
            self.google_sheet_id,
            self.google_sheet_worksheet or "(first sheet)",
        )

        if not self.service_account_json or not self.service_account_json.exists():
            raise FileNotFoundError(
                f"Service account JSON not found: {self.service_account_json}. "
                "This file is required for Google Sheets access."
            )

        try:
            gc = gspread.service_account(filename=str(self.service_account_json))
            spreadsheet = gc.open_by_key(self.google_sheet_id)

            if self.google_sheet_worksheet:
                worksheet = spreadsheet.worksheet(self.google_sheet_worksheet)
            else:
                worksheet = spreadsheet.sheet1

            records = worksheet.get_all_records()

        except gspread.exceptions.SpreadsheetNotFound:
            raise ConnectionError(
                f"Google Sheet not found: '{self.google_sheet_id}'. "
                "Make sure the spreadsheet is shared with the service account email."
            )
        except gspread.exceptions.WorksheetNotFound:
            raise ValueError(
                f"Worksheet '{self.google_sheet_worksheet}' not found "
                f"in spreadsheet '{self.google_sheet_id}'."
            )
        except gspread.exceptions.APIError as exc:
            raise ConnectionError(
                f"Google Sheets API error: {exc}. "
                "Check that the Google Sheets API is enabled in your GCP project."
            )

        if not records:
            raise ValueError("Google Sheet is empty — no rows found.")

        df = pd.DataFrame(records)
        logger.info("   Found %d rows in the Google Sheet.", len(df))
        return df

    # --------------------------------------------------------------------- #
    #  Validation & building                                                 #
    # --------------------------------------------------------------------- #

    @staticmethod
    def _validate_columns(df: pd.DataFrame) -> None:
        """Ensure all required columns are present."""
        missing = set(REQUIRED_COLUMNS) - set(df.columns)
        if missing:
            raise ValueError(
                f"Missing required columns in spreadsheet: {', '.join(sorted(missing))}"
            )

    @staticmethod
    def _build_products(df: pd.DataFrame) -> list[IAPProduct]:
        """Convert each DataFrame row into a validated IAPProduct."""
        products: list[IAPProduct] = []
        errors: list[str] = []

        for idx, row in df.iterrows():
            row_num = idx + 2  # Excel row (1-indexed header + data)

            # --- product_id ---
            product_id = str(row["product_id"]).strip()
            if not product_id or product_id == "nan":
                errors.append(f"Row {row_num}: product_id is empty.")
                continue

            # --- iap_type ---
            iap_type = str(row["iap_type"]).strip().lower()
            if iap_type not in VALID_IAP_TYPES:
                errors.append(
                    f"Row {row_num} ({product_id}): invalid iap_type '{iap_type}'. "
                    f"Must be one of: {VALID_IAP_TYPES}"
                )
                continue

            # --- base_price_usd ---
            try:
                base_price = Decimal(str(row["base_price_usd"]).strip())
                if base_price < 0:
                    raise ValueError("negative price")
            except (InvalidOperation, ValueError) as exc:
                errors.append(
                    f"Row {row_num} ({product_id}): invalid base_price_usd "
                    f"'{row['base_price_usd']}' – {exc}"
                )
                continue

            # --- localized text ---
            name_en = str(row["name_en"]).strip()
            desc_en = str(row["desc_en"]).strip()
            name_vi = str(row.get("name_vi", "")).strip()
            desc_vi = str(row.get("desc_vi", "")).strip()

            if not name_en or name_en == "nan":
                errors.append(f"Row {row_num} ({product_id}): name_en is empty.")
                continue

            products.append(
                IAPProduct(
                    product_id=product_id,
                    iap_type=iap_type,
                    base_price_usd=base_price,
                    name_en=name_en,
                    desc_en=desc_en if desc_en != "nan" else "",
                    name_vi=name_vi if name_vi != "nan" else "",
                    desc_vi=desc_vi if desc_vi != "nan" else "",
                )
            )

        if errors:
            error_block = "\n  • ".join(errors)
            logger.warning(
                "⚠️  Data validation warnings (%d):\n  • %s",
                len(errors),
                error_block,
            )

        if not products:
            raise ValueError("No valid IAP products found in the spreadsheet.")

        return products
