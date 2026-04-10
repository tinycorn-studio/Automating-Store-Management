#!/usr/bin/env python3
"""
AutoStoreSetup — CLI Entry Point
=================================

Usage examples:

    # Dry-run (default, reads DRY_RUN from .env)
    python main.py

    # Sync only Google Play
    python main.py --platform google

    # Sync only Apple App Store
    python main.py --platform apple

    # Force dry-run regardless of .env
    python main.py --dry-run

    # Force live mode (override .env)
    python main.py --live

    # Specify custom data file
    python main.py --data ./custom_iap_data.xlsx

    # Specify custom .env file
    python main.py --env ./config/.env.production
"""

import logging
import sys
from pathlib import Path

import click

from auto_store_setup.config import load_config
from auto_store_setup.controller import MainController, Platform


def _setup_logging(verbose: bool) -> None:
    """Configure structured logging with timestamps and colours."""
    level = logging.DEBUG if verbose else logging.INFO

    fmt = "%(asctime)s │ %(levelname)-7s │ %(message)s"
    datefmt = "%H:%M:%S"

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt, datefmt=datefmt))

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)

    # Suppress noisy third-party loggers
    logging.getLogger("googleapiclient").setLevel(logging.WARNING)
    logging.getLogger("google.auth").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--platform", "-p",
    type=click.Choice(["google", "apple", "both"], case_sensitive=False),
    default="both",
    show_default=True,
    help="Target platform(s) to sync.",
)
@click.option(
    "--dry-run", "-d",
    is_flag=True,
    default=False,
    help="Force dry-run mode (no API calls). Overrides .env.",
)
@click.option(
    "--live", "-l",
    is_flag=True,
    default=False,
    help="Force live mode (actual API calls). Overrides .env.",
)
@click.option(
    "--data",
    type=click.Path(exists=False),
    default=None,
    help="Path to the IAP data spreadsheet (.xlsx). Overrides .env.",
)
@click.option(
    "--env",
    "env_path",
    type=click.Path(exists=True),
    default=None,
    help="Path to the .env configuration file.",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    default=False,
    help="Enable verbose/debug logging.",
)
def main(
    platform: str,
    dry_run: bool,
    live: bool,
    data: str | None,
    env_path: str | None,
    verbose: bool,
) -> None:
    """
    AutoStoreSetup -- Batch IAP Sync Tool

    Reads IAP definitions from an Excel spreadsheet and creates/updates
    them on Google Play Console and/or Apple App Store Connect.
    """
    _setup_logging(verbose)
    logger = logging.getLogger("auto_store_setup")

    # --- Load config ---
    try:
        config = load_config(env_path)
    except Exception as exc:
        logger.error("❌ Failed to load configuration: %s", exc)
        sys.exit(1)

    # --- Apply CLI overrides ---
    overrides: dict = {}

    if dry_run and live:
        logger.error("❌ Cannot specify both --dry-run and --live.")
        sys.exit(1)

    if dry_run:
        overrides["dry_run"] = True
    elif live:
        overrides["dry_run"] = False

    if data:
        overrides["iap_data_file"] = Path(data).resolve()

    if overrides:
        # Rebuild config with overrides (frozen dataclass requires replacement)
        from dataclasses import asdict
        merged = {**asdict(config), **overrides}
        from auto_store_setup.config import Config
        config = Config(**merged)

    # --- Validate ---
    errors = config.validate()
    if errors:
        logger.error("❌ Configuration errors:")
        for err in errors:
            logger.error("   • %s", err)
        sys.exit(1)

    # --- Map platform ---
    platform_map = {
        "google": Platform.GOOGLE,
        "apple": Platform.APPLE,
        "both": Platform.BOTH,
    }
    target = platform_map[platform.lower()]

    # --- Run ---
    try:
        controller = MainController(config, platform=target)
        controller.run()
    except KeyboardInterrupt:
        logger.info("\n⏹️  Interrupted by user.")
        sys.exit(130)
    except Exception as exc:
        logger.exception("❌ Unexpected error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
