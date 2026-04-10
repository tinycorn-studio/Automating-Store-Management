"""
MainController - Orchestrates the full sync pipeline.

Coordinates parsers and API clients to execute batch operations
from the Google Sheet / Excel data source to both stores.
Supports: IAP sync, Store Listing, Screenshots.
"""

import logging
from enum import Enum, auto

from .config import Config
from .data_parser import DataParser, IAPProduct
from .listing_parser import ListingParser, StoreListingData
from .screenshot_parser import ScreenshotParser, ScreenshotManifest
from .google_play_client import GooglePlayClient
from .appstore_client import AppStoreClient

logger = logging.getLogger(__name__)


class Platform(Enum):
    """Target platforms to sync."""

    GOOGLE = auto()
    APPLE = auto()
    BOTH = auto()


class MainController:
    """
    Orchestrator for all sync operations.

    Parameters
    ----------
    config : Config
        Application configuration.
    platform : Platform
        Which platform(s) to target.
    """

    def __init__(self, config: Config, platform: Platform = Platform.BOTH) -> None:
        self.config = config
        self.platform = platform

        self._google: GooglePlayClient | None = None
        self._apple: AppStoreClient | None = None

        if platform in (Platform.GOOGLE, Platform.BOTH):
            self._google = GooglePlayClient(
                package_name=config.google_play_package_name,
                service_account_json=config.google_service_account_json,
                dry_run=config.dry_run,
            )

        if platform in (Platform.APPLE, Platform.BOTH):
            self._apple = AppStoreClient(
                key_id=config.apple_key_id,
                issuer_id=config.apple_issuer_id,
                private_key_path=config.apple_private_key_path,
                app_id=config.apple_app_id,
                dry_run=config.dry_run,
            )

    # ===================================================================== #
    #  Shared helpers                                                       #
    # ===================================================================== #

    def _connect_clients(self) -> None:
        """Authenticate with each target platform."""
        if self._google:
            self._google.connect()
        if self._apple:
            self._apple.connect()

    def _make_parser_kwargs(self, worksheet_override: str = "") -> dict:
        """Build kwargs shared by all parsers (data source config)."""
        return dict(
            source=self.config.data_source,
            file_path=self.config.iap_data_file,
            google_sheet_id=self.config.google_sheet_id,
            service_account_json=self.config.google_service_account_json,
        )

    def _print_banner(self, operation: str) -> None:
        mode = "🟡 DRY-RUN" if self.config.dry_run else "🟢 LIVE"
        logger.info("")
        logger.info("╔══════════════════════════════════════════════════════════╗")
        logger.info("║         AutoStoreSetup — %-32s║", operation)
        logger.info("╠══════════════════════════════════════════════════════════╣")
        logger.info("║  Mode     : %-44s ║", mode)
        logger.info("║  Platform : %-44s ║", self.platform.name)
        logger.info("║  Source   : %-44s ║", self.config.source_display_name)
        logger.info("╚══════════════════════════════════════════════════════════╝")
        logger.info("")

    # ===================================================================== #
    #  IAP Sync                                                             #
    # ===================================================================== #

    def run_iap(self) -> None:
        """Execute the IAP sync pipeline: parse → connect → sync → report."""
        self._print_banner("IAP Batch Sync")

        # Parse
        parser = DataParser(
            **self._make_parser_kwargs(),
            google_sheet_worksheet=self.config.google_sheet_worksheet,
        )
        products = parser.parse()
        self._print_product_summary(products)

        # Connect & sync
        self._connect_clients()

        google_results: dict[str, bool] = {}
        apple_results: dict[str, bool] = {}

        if self._google:
            logger.info("")
            logger.info("═" * 60)
            logger.info("  📱  GOOGLE PLAY CONSOLE  — Syncing %d products", len(products))
            logger.info("═" * 60)
            google_results = self._google.sync_all(products)

        if self._apple:
            logger.info("")
            logger.info("═" * 60)
            logger.info("  🍎  APPLE APP STORE CONNECT  — Syncing %d products", len(products))
            logger.info("═" * 60)
            apple_results = self._apple.sync_all(products)

        # Report
        self._print_dual_report(
            items=[(p.product_id, google_results.get(p.product_id), apple_results.get(p.product_id)) for p in products],
            google_active=bool(google_results),
            apple_active=bool(apple_results),
        )

    # ===================================================================== #
    #  Store Listing                                                        #
    # ===================================================================== #

    def run_listing(self) -> None:
        """Execute the Store Listing sync pipeline."""
        self._print_banner("Store Listing Sync")

        parser = ListingParser(
            **self._make_parser_kwargs(),
            worksheet="Store Listing",
        )
        listing_data = parser.parse()

        self._connect_clients()

        google_results: dict[str, bool] = {}
        apple_results: dict[str, bool] = {}

        if self._google:
            logger.info("")
            logger.info("═" * 60)
            logger.info("  📱  GOOGLE PLAY  — Updating Store Listing (%d locales)", len(listing_data.locales))
            logger.info("═" * 60)
            google_results = self._google.update_listing(listing_data)

        if self._apple:
            logger.info("")
            logger.info("═" * 60)
            logger.info("  🍎  APP STORE  — Updating Store Listing (%d locales)", len(listing_data.locales))
            logger.info("═" * 60)
            apple_results = self._apple.update_listing(listing_data)

        self._print_dual_report(
            items=[(loc, google_results.get(loc), apple_results.get(loc)) for loc in listing_data.locales],
            google_active=bool(google_results),
            apple_active=bool(apple_results),
        )

    # ===================================================================== #
    #  Screenshots                                                          #
    # ===================================================================== #

    def run_screenshots(self) -> None:
        """Execute the Screenshot upload pipeline."""
        self._print_banner("Screenshot Upload")

        parser = ScreenshotParser(
            **self._make_parser_kwargs(),
            worksheet="Screenshots",
        )
        manifest = parser.parse()

        self._connect_clients()

        google_results: dict[str, bool] = {}
        apple_results: dict[str, bool] = {}

        # Build keys list for reporting
        all_keys: list[str] = []
        for locale in manifest.locales:
            for device in manifest.device_types(locale):
                all_keys.append(f"{locale}/{device}")

        if self._google:
            logger.info("")
            logger.info("═" * 60)
            logger.info("  📱  GOOGLE PLAY  — Uploading %d screenshots", len(manifest.entries))
            logger.info("═" * 60)
            google_results = self._google.upload_screenshots(manifest)

        if self._apple:
            logger.info("")
            logger.info("═" * 60)
            logger.info("  🍎  APP STORE  — Uploading %d screenshots", len(manifest.entries))
            logger.info("═" * 60)
            apple_results = self._apple.upload_screenshots(manifest)

        self._print_dual_report(
            items=[(k, google_results.get(k), apple_results.get(k)) for k in all_keys],
            google_active=bool(google_results),
            apple_active=bool(apple_results),
        )

    # ===================================================================== #
    #  Legacy compatibility                                                 #
    # ===================================================================== #

    def run(self) -> None:
        """Legacy entry point — runs IAP sync."""
        self.run_iap()

    # ===================================================================== #
    #  Printing helpers                                                     #
    # ===================================================================== #

    @staticmethod
    def _print_product_summary(products: list[IAPProduct]) -> None:
        logger.info("📋 Products to sync:")
        logger.info("   %-45s %-16s %s", "PRODUCT ID", "TYPE", "PRICE")
        logger.info("   " + "─" * 75)
        for p in products:
            logger.info(
                "   %-45s %-16s $%s",
                p.product_id, p.iap_type, p.base_price_usd,
            )
        logger.info("")

    @staticmethod
    def _print_dual_report(
        items: list[tuple[str, bool | None, bool | None]],
        google_active: bool,
        apple_active: bool,
    ) -> None:
        """Print a summary report for any dual-platform operation."""
        logger.info("")
        logger.info("╔══════════════════════════════════════════════════════════╗")
        logger.info("║                     SYNC REPORT                         ║")
        logger.info("╠══════════════════════════════════════════════════════════╣")

        for name, gp, ap in items:
            gp_icon = "✅" if gp else ("❌" if gp is False else "⏭️")
            ap_icon = "✅" if ap else ("❌" if ap is False else "⏭️")
            logger.info(
                "║  %s  Google  |  %s  Apple   %-35s ║",
                gp_icon, ap_icon, name[:35],
            )

        total = len(items)
        gp_ok = sum(1 for _, g, _ in items if g)
        ap_ok = sum(1 for _, _, a in items if a)

        logger.info("╠══════════════════════════════════════════════════════════╣")
        if google_active:
            logger.info("║  Google Play : %d / %d succeeded                         ║", gp_ok, total)
        if apple_active:
            logger.info("║  App Store   : %d / %d succeeded                         ║", ap_ok, total)
        logger.info("╚══════════════════════════════════════════════════════════╝")
        logger.info("")
