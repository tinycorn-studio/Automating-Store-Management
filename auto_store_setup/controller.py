"""
MainController - Orchestrates the full IAP sync pipeline.

Coordinates DataParser, GooglePlayClient, and AppStoreClient
to execute a batch sync from the Excel spreadsheet to both stores.
"""

import logging
from enum import Enum, auto

from .config import Config
from .data_parser import DataParser, IAPProduct
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
    Orchestrator for the IAP synchronisation pipeline.

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

        self._parser = DataParser(config.iap_data_file)

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

    # --------------------------------------------------------------------- #
    #  Public API                                                            #
    # --------------------------------------------------------------------- #

    def run(self) -> None:
        """Execute the full pipeline: parse → connect → sync → report."""
        self._print_banner()

        # 1. Parse
        products = self._parser.parse()
        self._print_product_summary(products)

        # 2. Connect
        self._connect_clients()

        # 3. Sync
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

        # 4. Report
        self._print_report(products, google_results, apple_results)

    # --------------------------------------------------------------------- #
    #  Internal helpers                                                      #
    # --------------------------------------------------------------------- #

    def _connect_clients(self) -> None:
        """Authenticate with each target platform."""
        if self._google:
            self._google.connect()
        if self._apple:
            self._apple.connect()

    def _print_banner(self) -> None:
        mode = "🟡 DRY-RUN" if self.config.dry_run else "🟢 LIVE"
        logger.info("")
        logger.info("╔══════════════════════════════════════════════════════════╗")
        logger.info("║         AutoStoreSetup — IAP Batch Sync Tool            ║")
        logger.info("╠══════════════════════════════════════════════════════════╣")
        logger.info("║  Mode     : %-44s ║", mode)
        logger.info("║  Platform : %-44s ║", self.platform.name)
        logger.info("║  Source   : %-44s ║", self.config.iap_data_file.name)
        logger.info("╚══════════════════════════════════════════════════════════╝")
        logger.info("")

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
    def _print_report(
        products: list[IAPProduct],
        google_results: dict[str, bool],
        apple_results: dict[str, bool],
    ) -> None:
        """Print a final summary report."""
        logger.info("")
        logger.info("╔══════════════════════════════════════════════════════════╗")
        logger.info("║                     SYNC REPORT                         ║")
        logger.info("╠══════════════════════════════════════════════════════════╣")

        for p in products:
            gp = google_results.get(p.product_id)
            ap = apple_results.get(p.product_id)

            gp_icon = "✅" if gp else ("❌" if gp is False else "⏭️")
            ap_icon = "✅" if ap else ("❌" if ap is False else "⏭️")

            logger.info(
                "║  %s  Google  |  %s  Apple   %-35s ║",
                gp_icon, ap_icon, p.product_id[:35],
            )

        total = len(products)
        gp_ok = sum(1 for v in google_results.values() if v)
        ap_ok = sum(1 for v in apple_results.values() if v)

        logger.info("╠══════════════════════════════════════════════════════════╣")
        if google_results:
            logger.info("║  Google Play : %d / %d succeeded                         ║", gp_ok, total)
        if apple_results:
            logger.info("║  App Store   : %d / %d succeeded                         ║", ap_ok, total)
        logger.info("╚══════════════════════════════════════════════════════════╝")
        logger.info("")
