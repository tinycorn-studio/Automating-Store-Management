"""
Configuration loader.

Reads settings from .env file and exposes them as a typed dataclass
for safe, validated access throughout the application.
"""

import os
import logging
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Valid data source types
VALID_DATA_SOURCES = {"excel", "gsheet"}


@dataclass(frozen=True)
class Config:
    """Immutable application configuration."""

    # Google Play
    google_play_package_name: str
    google_service_account_json: Path

    # Apple App Store Connect
    apple_key_id: str
    apple_issuer_id: str
    apple_private_key_path: Path
    apple_app_id: str

    # Data source
    data_source: str               # "excel" or "gsheet"
    iap_data_file: Path            # Used when data_source == "excel"
    google_sheet_id: str           # Used when data_source == "gsheet"
    google_sheet_worksheet: str    # Worksheet name (default: first sheet)

    # Operation mode
    dry_run: bool = True

    @property
    def is_gsheet(self) -> bool:
        return self.data_source == "gsheet"

    @property
    def source_display_name(self) -> str:
        """Human-readable name for the current data source."""
        if self.is_gsheet:
            ws = self.google_sheet_worksheet or "(first sheet)"
            return f"Google Sheet [{self.google_sheet_id[:16]}...] / {ws}"
        return self.iap_data_file.name

    def validate(self) -> list[str]:
        """Return a list of validation errors (empty = OK)."""
        errors: list[str] = []

        if not self.google_play_package_name:
            errors.append("GOOGLE_PLAY_PACKAGE_NAME is not set.")

        if not self.google_service_account_json.exists():
            errors.append(
                f"Google service account file not found: {self.google_service_account_json}"
            )

        if not self.apple_key_id:
            errors.append("APPLE_KEY_ID is not set.")
        if not self.apple_issuer_id:
            errors.append("APPLE_ISSUER_ID is not set.")
        if not self.apple_private_key_path.exists():
            errors.append(
                f"Apple private key file not found: {self.apple_private_key_path}"
            )
        if not self.apple_app_id:
            errors.append("APPLE_APP_ID is not set.")

        # Data source validation
        if self.data_source not in VALID_DATA_SOURCES:
            errors.append(
                f"DATA_SOURCE must be one of {VALID_DATA_SOURCES}, got '{self.data_source}'."
            )
        elif self.is_gsheet:
            if not self.google_sheet_id or self.google_sheet_id == "your-spreadsheet-id-here":
                errors.append("GOOGLE_SHEET_ID is not set (required when DATA_SOURCE=gsheet).")
        else:
            if not self.iap_data_file.exists():
                errors.append(
                    f"IAP data file not found: {self.iap_data_file}"
                )

        return errors


def load_config(env_path: str | Path | None = None) -> Config:
    """
    Load configuration from the .env file.

    Parameters
    ----------
    env_path : str or Path, optional
        Explicit path to the .env file. If None, searches CWD upward.

    Returns
    -------
    Config
        Validated configuration object.
    """
    if env_path:
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()

    base_dir = Path(env_path).parent if env_path else Path.cwd()

    def _resolve(raw: str) -> Path:
        p = Path(raw)
        if not p.is_absolute():
            p = (base_dir / p).resolve()
        return p

    config = Config(
        google_play_package_name=os.getenv("GOOGLE_PLAY_PACKAGE_NAME", ""),
        google_service_account_json=_resolve(
            os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "./credentials/service_account.json")
        ),
        apple_key_id=os.getenv("APPLE_KEY_ID", ""),
        apple_issuer_id=os.getenv("APPLE_ISSUER_ID", ""),
        apple_private_key_path=_resolve(
            os.getenv("APPLE_PRIVATE_KEY_PATH", "./credentials/AuthKey.p8")
        ),
        apple_app_id=os.getenv("APPLE_APP_ID", ""),
        data_source=os.getenv("DATA_SOURCE", "excel").lower().strip(),
        iap_data_file=_resolve(
            os.getenv("IAP_DATA_FILE", "./iap_data.xlsx")
        ),
        google_sheet_id=os.getenv("GOOGLE_SHEET_ID", ""),
        google_sheet_worksheet=os.getenv("GOOGLE_SHEET_WORKSHEET", ""),
        dry_run=os.getenv("DRY_RUN", "true").lower() in ("true", "1", "yes"),
    )

    logger.debug("Configuration loaded: %s", config)
    return config
