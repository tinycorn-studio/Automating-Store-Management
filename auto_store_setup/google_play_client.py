"""
GooglePlayClient - Manages In-App Products on Google Play Console.

Uses the Android Publisher API (v3) via google-api-python-client.
Authenticates with a GCP Service Account.
"""

import logging
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .data_parser import IAPProduct

logger = logging.getLogger(__name__)

# OAuth2 scope required for the Android Publisher API
_SCOPES = ["https://www.googleapis.com/auth/androidpublisher"]


class GooglePlayClient:
    """
    Client for creating / updating managed In-App Products on Google Play.

    Parameters
    ----------
    package_name : str
        The Android application ID (e.g. ``com.studio.game``).
    service_account_json : Path
        Path to the GCP service account key file.
    dry_run : bool
        If True, log the intended actions without making real API calls.
    """

    def __init__(
        self,
        package_name: str,
        service_account_json: Path,
        dry_run: bool = True,
    ) -> None:
        self.package_name = package_name
        self.dry_run = dry_run
        self._service_account_json = service_account_json
        self._service = None

    # --------------------------------------------------------------------- #
    #  Connection                                                            #
    # --------------------------------------------------------------------- #

    def connect(self) -> None:
        """Authenticate and build the API service object."""
        logger.info("🔗 Connecting to Google Play Developer API …")

        if self.dry_run:
            logger.info("   [DRY-RUN] Skipping actual authentication.")
            return

        credentials = service_account.Credentials.from_service_account_file(
            str(self._service_account_json),
            scopes=_SCOPES,
        )
        self._service = build(
            "androidpublisher", "v3", credentials=credentials, cache_discovery=False
        )
        logger.info("✅ Connected to Google Play API for package: %s", self.package_name)

    # --------------------------------------------------------------------- #
    #  Public API                                                            #
    # --------------------------------------------------------------------- #

    def sync_product(self, product: IAPProduct) -> bool:
        """
        Create or update a single IAP product on Google Play.

        Returns True on success, False on failure.
        """
        body = self._build_body(product)

        if self.dry_run:
            self._log_dry_run(product, body)
            return True

        # Try update first; if 404 → insert instead
        try:
            return self._update(product.product_id, body)
        except HttpError as exc:
            if exc.resp.status == 404:
                logger.info(
                    "   Product '%s' not found on Google Play – creating it …",
                    product.product_id,
                )
                return self._insert(body)
            raise

    def sync_all(self, products: list[IAPProduct]) -> dict[str, bool]:
        """
        Sync a list of products. Returns a mapping product_id → success.
        """
        results: dict[str, bool] = {}
        for product in products:
            try:
                results[product.product_id] = self.sync_product(product)
            except Exception as exc:
                logger.error(
                    "❌ [Google Play] Failed to sync '%s': %s",
                    product.product_id,
                    exc,
                )
                results[product.product_id] = False
        return results

    # --------------------------------------------------------------------- #
    #  Internal helpers                                                      #
    # --------------------------------------------------------------------- #

    def _build_body(self, product: IAPProduct) -> dict:
        """
        Build the request body for the androidpublisher inappproducts API.

        Reference
        ---------
        https://developers.google.com/android-publisher/api-ref/rest/v3/inappproducts
        """
        # Google uses "managedUser" for both consumable & non-consumable
        # managed products. Subscriptions are a separate API.
        purchase_type = "managedUser"

        body = {
            "packageName": self.package_name,
            "sku": product.product_id,
            "status": "active",
            "purchaseType": purchase_type,
            "defaultPrice": {
                "priceMicros": str(product.price_micros),
                "currency": "USD",
            },
            "listings": {
                "en-US": {
                    "title": product.name_en,
                    "description": product.desc_en or product.name_en,
                },
            },
            "defaultLanguage": "en-US",
        }

        # Add Vietnamese localisation if provided
        if product.name_vi:
            body["listings"]["vi"] = {
                "title": product.name_vi,
                "description": product.desc_vi or product.name_vi,
            }

        return body

    def _insert(self, body: dict) -> bool:
        """Insert a new in-app product."""
        try:
            self._service.inappproducts().insert(
                packageName=self.package_name,
                body=body,
            ).execute()
            logger.info("   ✅ Created on Google Play: %s", body["sku"])
            return True
        except HttpError as exc:
            logger.error("   ❌ Insert failed for %s: %s", body["sku"], exc)
            return False

    def _update(self, sku: str, body: dict) -> bool:
        """Update an existing in-app product."""
        try:
            self._service.inappproducts().update(
                packageName=self.package_name,
                sku=sku,
                body=body,
            ).execute()
            logger.info("   ✅ Updated on Google Play: %s", sku)
            return True
        except HttpError as exc:
            logger.error("   ❌ Update failed for %s: %s", sku, exc)
            raise  # re-raise so caller can check for 404

    def _log_dry_run(self, product: IAPProduct, body: dict) -> None:
        """Pretty-print what would be sent to the API."""
        logger.info(
            "   [DRY-RUN] Google Play → %s\n"
            "      Type        : %s\n"
            "      Price       : $%s (micros: %s)\n"
            "      Listings    : %s\n"
            "      Status      : %s",
            product.product_id,
            body["purchaseType"],
            product.base_price_usd,
            body["defaultPrice"]["priceMicros"],
            ", ".join(body["listings"].keys()),
            body["status"],
        )
