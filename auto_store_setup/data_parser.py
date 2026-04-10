"""
DataParser - Reads & validates the IAP spreadsheet.

Supports .xlsx files via pandas + openpyxl.
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
    Parses the IAP data spreadsheet and returns validated IAPProduct objects.

    Parameters
    ----------
    file_path : Path
        Path to the .xlsx file.
    """

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path

    # --------------------------------------------------------------------- #
    #  Public API                                                            #
    # --------------------------------------------------------------------- #

    def parse(self) -> list[IAPProduct]:
        """
        Read the spreadsheet and return a list of validated IAPProduct items.

        Raises
        ------
        FileNotFoundError
            If the spreadsheet does not exist.
        ValueError
            If required columns are missing or data validation fails.
        """
        logger.info("📄 Reading spreadsheet: %s", self.file_path)

        if not self.file_path.exists():
            raise FileNotFoundError(f"Spreadsheet not found: {self.file_path}")

        df = pd.read_excel(self.file_path, engine="openpyxl")
        logger.info("   Found %d rows in the spreadsheet.", len(df))

        self._validate_columns(df)
        products = self._build_products(df)

        logger.info("✅ Successfully parsed %d IAP products.", len(products))
        return products

    # --------------------------------------------------------------------- #
    #  Internal helpers                                                      #
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
