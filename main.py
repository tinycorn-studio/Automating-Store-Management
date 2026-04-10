#!/usr/bin/env python3
"""
AutoStoreSetup — CLI Entry Point
=================================

Usage examples:

    # IAP sync (dry-run by default)
    python main.py iap
    python main.py iap --platform google
    python main.py iap --live

    # Store Listing sync
    python main.py listing
    python main.py listing --platform apple

    # Screenshot upload
    python main.py screenshots
    python main.py screenshots --live

    # Global options
    python main.py --source gsheet iap
    python main.py --env ./config/.env.production listing
    python main.py --verbose screenshots
"""

import logging
import sys
from dataclasses import replace
from pathlib import Path

import click

from auto_store_setup.config import load_config
from auto_store_setup.controller import MainController, Platform

# ──────────────────────────────────────────────────────────────────────── #
#  Logging Setup                                                          #
# ──────────────────────────────────────────────────────────────────────── #

def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    fmt = "%(asctime)s | %(levelname)-7s | %(message)s"
    handler.setFormatter(logging.Formatter(fmt, datefmt="%H:%M:%S"))

    root = logging.getLogger("auto_store_setup")
    root.setLevel(level)
    if not root.handlers:
        root.addHandler(handler)


# ──────────────────────────────────────────────────────────────────────── #
#  CLI Group                                                              #
# ──────────────────────────────────────────────────────────────────────── #

@click.group(context_settings={"help_option_names": ["-h", "--help"]}, invoke_without_command=True)
@click.option(
    "--source", "-s",
    type=click.Choice(["excel", "gsheet"], case_sensitive=False),
    default=None,
    help="Data source type. Overrides DATA_SOURCE in .env.",
)
@click.option(
    "--env", "env_path",
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
@click.pass_context
def cli(ctx: click.Context, source: str | None, env_path: str | None, verbose: bool) -> None:
    """
    AutoStoreSetup -- Batch Store Management Tool

    Manages IAP, Store Listings, and Screenshots on both
    Google Play Console and Apple App Store Connect.
    """
    _setup_logging(verbose)
    ctx.ensure_object(dict)
    ctx.obj["source"] = source
    ctx.obj["env_path"] = env_path
    ctx.obj["verbose"] = verbose

    # If no subcommand given, show help
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# ──────────────────────────────────────────────────────────────────────── #
#  Shared option decorators                                               #
# ──────────────────────────────────────────────────────────────────────── #

def _platform_options(func):
    """Common options for all subcommands."""
    func = click.option(
        "--platform", "-p",
        type=click.Choice(["google", "apple", "both"], case_sensitive=False),
        default="both",
        help="Target platform(s) to sync.",
    )(func)
    func = click.option(
        "--dry-run", "-d",
        is_flag=True,
        default=False,
        help="Force dry-run mode (no API calls). Overrides .env.",
    )(func)
    func = click.option(
        "--live", "-l",
        is_flag=True,
        default=False,
        help="Force live mode (actual API calls). Overrides .env.",
    )(func)
    return func


def _build_controller(ctx: click.Context, platform: str, dry_run: bool, live: bool) -> MainController:
    """Load config, apply overrides, build controller."""
    logger = logging.getLogger("auto_store_setup")

    env_path = ctx.obj.get("env_path")
    source = ctx.obj.get("source")

    config = load_config(env_path)

    # Apply overrides
    overrides: dict = {}
    if dry_run:
        overrides["dry_run"] = True
    elif live:
        overrides["dry_run"] = False

    if source:
        overrides["data_source"] = source.lower()

    if overrides:
        config = replace(config, **overrides)

    # Validate
    errors = config.validate()
    if errors:
        for e in errors:
            logger.error("  Config error: %s", e)
        raise click.Abort()

    platform_map = {"google": Platform.GOOGLE, "apple": Platform.APPLE, "both": Platform.BOTH}
    return MainController(config=config, platform=platform_map[platform.lower()])


# ──────────────────────────────────────────────────────────────────────── #
#  Subcommands                                                            #
# ──────────────────────────────────────────────────────────────────────── #

@cli.command()
@_platform_options
@click.option("--data", type=click.Path(exists=False), default=None, help="Custom .xlsx file path.")
@click.pass_context
def iap(ctx: click.Context, platform: str, dry_run: bool, live: bool, data: str | None) -> None:
    """Sync In-App Purchases from the spreadsheet to stores."""
    if data:
        config = load_config(ctx.obj.get("env_path"))
        from dataclasses import replace as _replace
        config = _replace(config, iap_data_file=Path(data).resolve(), data_source="excel")

    controller = _build_controller(ctx, platform, dry_run, live)
    controller.run_iap()


@cli.command()
@_platform_options
@click.pass_context
def listing(ctx: click.Context, platform: str, dry_run: bool, live: bool) -> None:
    """Sync Store Listing metadata (name, description, keywords)."""
    controller = _build_controller(ctx, platform, dry_run, live)
    controller.run_listing()


@cli.command()
@_platform_options
@click.pass_context
def screenshots(ctx: click.Context, platform: str, dry_run: bool, live: bool) -> None:
    """Upload app screenshots to both stores."""
    controller = _build_controller(ctx, platform, dry_run, live)
    controller.run_screenshots()


# ──────────────────────────────────────────────────────────────────────── #
#  Entry Point                                                            #
# ──────────────────────────────────────────────────────────────────────── #

if __name__ == "__main__":
    cli()
