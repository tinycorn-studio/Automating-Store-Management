"""
GooglePlayClient - Manages IAP, Store Listings, and Screenshots on Google Play.

Uses the Android Publisher API (v3) via google-api-python-client.
Authenticates with a GCP Service Account.
"""

import logging
import mimetypes
from io import BytesIO
from pathlib import Path

import requests as http_requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload

from .data_parser import IAPProduct
from .listing_parser import LocalizedListing, StoreListingData
from .screenshot_parser import ScreenshotEntry, ScreenshotManifest

logger = logging.getLogger(__name__)

# OAuth2 scope required for the Android Publisher API
_SCOPES = ["https://www.googleapis.com/auth/androidpublisher"]


class GooglePlayClient:
    """
    Client for managing IAP, Store Listings, and Screenshots on Google Play.

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

    # ===================================================================== #
    #  IAP (In-App Products)                                                #
    # ===================================================================== #

    def sync_product(self, product: IAPProduct) -> bool:
        """Create or update a single IAP product. Returns True on success."""
        body = self._build_iap_body(product)

        if self.dry_run:
            self._log_dry_run_iap(product, body)
            return True

        try:
            return self._update_iap(product.product_id, body)
        except HttpError as exc:
            if exc.resp.status == 404:
                logger.info("   Product '%s' not found – creating …", product.product_id)
                return self._insert_iap(body)
            raise

    def sync_all(self, products: list[IAPProduct]) -> dict[str, bool]:
        """Sync a list of IAP products. Returns product_id → success."""
        results: dict[str, bool] = {}
        for product in products:
            try:
                results[product.product_id] = self.sync_product(product)
            except Exception as exc:
                logger.error("❌ [Google Play] Failed to sync '%s': %s", product.product_id, exc)
                results[product.product_id] = False
        return results

    # ===================================================================== #
    #  Store Listing                                                        #
    # ===================================================================== #

    def update_listing(self, listing_data: StoreListingData) -> dict[str, bool]:
        """
        Update store listing for all locales using the Edits API.

        Flow: create edit → update listings → commit edit.
        Returns locale → success mapping.
        """
        results: dict[str, bool] = {}

        if self.dry_run:
            for listing in listing_data.listings:
                self._log_dry_run_listing(listing)
                results[listing.locale] = True
            return results

        # Create an edit session
        edit_id = self._create_edit()
        if not edit_id:
            return {l.locale: False for l in listing_data.listings}

        for listing in listing_data.listings:
            try:
                results[listing.locale] = self._update_listing_locale(edit_id, listing)
            except Exception as exc:
                logger.error("❌ Listing [%s] failed: %s", listing.locale, exc)
                results[listing.locale] = False

        # Commit the edit if any succeeded
        if any(results.values()):
            self._commit_edit(edit_id)
        else:
            self._delete_edit(edit_id)

        return results

    # ===================================================================== #
    #  Screenshots                                                          #
    # ===================================================================== #

    def upload_screenshots(self, manifest: ScreenshotManifest) -> dict[str, bool]:
        """
        Upload screenshots using the Edits API.

        Flow: create edit → upload images per locale/device → commit edit.
        Returns "locale/device" → success mapping.
        """
        results: dict[str, bool] = {}

        if self.dry_run:
            for locale in manifest.locales:
                for device in manifest.device_types(locale):
                    entries = manifest.by_locale_and_device(locale, device)
                    key = f"{locale}/{device}"
                    self._log_dry_run_screenshots(locale, device, entries)
                    results[key] = True
            return results

        edit_id = self._create_edit()
        if not edit_id:
            return {}

        for locale in manifest.locales:
            for device in manifest.device_types(locale):
                entries = manifest.by_locale_and_device(locale, device)
                key = f"{locale}/{device}"
                try:
                    image_type = entries[0].google_image_type
                    ok = self._upload_images_for_type(edit_id, locale, image_type, entries)
                    results[key] = ok
                except Exception as exc:
                    logger.error("❌ Screenshot upload [%s] failed: %s", key, exc)
                    results[key] = False

        if any(results.values()):
            self._commit_edit(edit_id)
        else:
            self._delete_edit(edit_id)

        return results

    # ===================================================================== #
    #  Edits API helpers                                                    #
    # ===================================================================== #

    def _create_edit(self) -> str | None:
        """Create a new edit session."""
        try:
            edit = self._service.edits().insert(
                packageName=self.package_name, body={}
            ).execute()
            edit_id = edit["id"]
            logger.debug("   Created edit session: %s", edit_id)
            return edit_id
        except HttpError as exc:
            logger.error("❌ Failed to create edit session: %s", exc)
            return None

    def _commit_edit(self, edit_id: str) -> bool:
        """Commit an edit session."""
        try:
            self._service.edits().commit(
                packageName=self.package_name, editId=edit_id
            ).execute()
            logger.info("   ✅ Edit committed successfully.")
            return True
        except HttpError as exc:
            logger.error("❌ Failed to commit edit: %s", exc)
            return False

    def _delete_edit(self, edit_id: str) -> None:
        """Delete (cancel) an edit session."""
        try:
            self._service.edits().delete(
                packageName=self.package_name, editId=edit_id
            ).execute()
            logger.debug("   Edit %s cancelled.", edit_id)
        except HttpError:
            pass  # Best-effort

    def _update_listing_locale(self, edit_id: str, listing: LocalizedListing) -> bool:
        """Update the store listing for a single locale within an edit."""
        body = {
            "language": listing.locale,
            "title": listing.app_name,
            "shortDescription": listing.short_description,
            "fullDescription": listing.full_description,
        }
        # Remove empty fields
        body = {k: v for k, v in body.items() if v}

        try:
            self._service.edits().listings().update(
                packageName=self.package_name,
                editId=edit_id,
                language=listing.locale,
                body=body,
            ).execute()
            logger.info("   ✅ Listing [%s] updated.", listing.locale)
            return True
        except HttpError as exc:
            logger.error("   ❌ Listing [%s] failed: %s", listing.locale, exc)
            return False

    def _upload_images_for_type(
        self,
        edit_id: str,
        locale: str,
        image_type: str,
        entries: list[ScreenshotEntry],
    ) -> bool:
        """Upload screenshot images for a specific locale + image type."""
        all_ok = True
        for entry in entries:
            try:
                if entry.is_url:
                    media = self._download_to_media(entry.file_path)
                else:
                    file_path = str(entry.resolved_path)
                    mime, _ = mimetypes.guess_type(file_path)
                    media = MediaFileUpload(file_path, mimetype=mime or "image/png")

                self._service.edits().images().upload(
                    packageName=self.package_name,
                    editId=edit_id,
                    language=locale,
                    imageType=image_type,
                    media_body=media,
                ).execute()
                logger.info(
                    "      ✅ Uploaded [%s/%s] #%d: %s",
                    locale, image_type, entry.display_order, entry.file_path[:60],
                )
            except Exception as exc:
                logger.error(
                    "      ❌ Upload failed [%s/%s] #%d: %s",
                    locale, image_type, entry.display_order, exc,
                )
                all_ok = False
        return all_ok

    @staticmethod
    def _download_to_media(url: str) -> MediaIoBaseUpload:
        """Download a URL into a MediaIoBaseUpload for the Google API."""
        resp = http_requests.get(url, timeout=30)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "image/png")
        return MediaIoBaseUpload(BytesIO(resp.content), mimetype=content_type)

    # ===================================================================== #
    #  IAP internal helpers                                                 #
    # ===================================================================== #

    def _build_iap_body(self, product: IAPProduct) -> dict:
        """Build request body for androidpublisher inappproducts API."""
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

        if product.name_vi:
            body["listings"]["vi"] = {
                "title": product.name_vi,
                "description": product.desc_vi or product.name_vi,
            }

        return body

    def _insert_iap(self, body: dict) -> bool:
        """Insert a new in-app product."""
        try:
            self._service.inappproducts().insert(
                packageName=self.package_name, body=body,
            ).execute()
            logger.info("   ✅ Created on Google Play: %s", body["sku"])
            return True
        except HttpError as exc:
            logger.error("   ❌ Insert failed for %s: %s", body["sku"], exc)
            return False

    def _update_iap(self, sku: str, body: dict) -> bool:
        """Update an existing in-app product."""
        try:
            self._service.inappproducts().update(
                packageName=self.package_name, sku=sku, body=body,
            ).execute()
            logger.info("   ✅ Updated on Google Play: %s", sku)
            return True
        except HttpError as exc:
            logger.error("   ❌ Update failed for %s: %s", sku, exc)
            raise

    # ===================================================================== #
    #  Dry-run logging                                                      #
    # ===================================================================== #

    def _log_dry_run_iap(self, product: IAPProduct, body: dict) -> None:
        logger.info(
            "   [DRY-RUN] Google Play → %s\n"
            "      Type        : %s\n"
            "      Price       : $%s (micros: %s)\n"
            "      Listings    : %s\n"
            "      Status      : %s",
            product.product_id, body["purchaseType"],
            product.base_price_usd, body["defaultPrice"]["priceMicros"],
            ", ".join(body["listings"].keys()), body["status"],
        )

    @staticmethod
    def _log_dry_run_listing(listing: LocalizedListing) -> None:
        logger.info(
            "   [DRY-RUN] Google Play Listing [%s]\n"
            "      App Name          : %s\n"
            "      Short Description : %s\n"
            "      Full Description  : %s chars",
            listing.locale,
            listing.app_name or "(empty)",
            listing.short_description[:60] or "(empty)",
            len(listing.full_description),
        )

    @staticmethod
    def _log_dry_run_screenshots(
        locale: str, device: str, entries: list[ScreenshotEntry],
    ) -> None:
        paths = "\n".join(f"         #{e.display_order}: {e.file_path[:60]}" for e in entries)
        logger.info(
            "   [DRY-RUN] Google Play Screenshots [%s / %s] — %d images\n%s",
            locale, device, len(entries), paths,
        )

