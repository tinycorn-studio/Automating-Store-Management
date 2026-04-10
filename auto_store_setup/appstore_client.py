"""
AppStoreClient - Manages In-App Purchases on Apple App Store Connect.

Uses the App Store Connect REST API v2 with JWT (ES256) authentication.
Implements the full Apple IAP creation flow:
  1. Create the In-App Purchase resource
  2. Create Localizations (en-US, vi)
  3. Create / set Price Schedule
"""

import logging
import time
from pathlib import Path

import jwt
import requests

from .data_parser import IAPProduct

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.appstoreconnect.apple.com/v2"
_BASE_URL_V1 = "https://api.appstoreconnect.apple.com/v1"

# Apple reference name max length
_REFERENCE_NAME_MAX = 64

# Apple price tier map (subset – USD values).
# In production you'd query /v1/appPricePoints for the full catalogue.
# This covers the most common tiers.
_USD_TO_PRICE_TIER: dict[str, str] = {
    "0": "0",
    "0.99": "1",
    "1.99": "2",
    "2.99": "3",
    "3.99": "4",
    "4.99": "5",
    "5.99": "6",
    "6.99": "7",
    "7.99": "8",
    "8.99": "9",
    "9.99": "10",
    "10.99": "11",
    "11.99": "12",
    "12.99": "13",
    "13.99": "14",
    "14.99": "15",
    "15.99": "16",
    "16.99": "17",
    "17.99": "18",
    "18.99": "19",
    "19.99": "20",
    "20.99": "21",
    "21.99": "22",
    "22.99": "23",
    "23.99": "24",
    "24.99": "25",
    "29.99": "30",
    "34.99": "35",
    "39.99": "40",
    "44.99": "45",
    "49.99": "50",
    "54.99": "55",
    "59.99": "60",
    "64.99": "65",
    "69.99": "70",
    "74.99": "75",
    "79.99": "80",
    "84.99": "85",
    "89.99": "90",
    "94.99": "95",
    "99.99": "100",
    "109.99": "110",
    "119.99": "120",
    "124.99": "125",
    "129.99": "130",
    "139.99": "140",
    "149.99": "150",
    "159.99": "160",
    "169.99": "170",
    "174.99": "175",
    "179.99": "180",
    "189.99": "190",
    "199.99": "200",
    "249.99": "250",
    "299.99": "300",
    "349.99": "350",
    "399.99": "400",
    "449.99": "450",
    "499.99": "500",
}


class AppStoreClient:
    """
    Client for creating / updating In-App Purchases on App Store Connect.

    Parameters
    ----------
    key_id : str
        Your API Key ID (10-character identifier).
    issuer_id : str
        Your Issuer ID (UUID from App Store Connect → Keys).
    private_key_path : Path
        Path to the downloaded .p8 AuthKey file.
    app_id : str
        Numeric Apple App ID.
    dry_run : bool
        If True, log the intended actions without making real API calls.
    """

    def __init__(
        self,
        key_id: str,
        issuer_id: str,
        private_key_path: Path,
        app_id: str,
        dry_run: bool = True,
    ) -> None:
        self.key_id = key_id
        self.issuer_id = issuer_id
        self.app_id = app_id
        self.dry_run = dry_run
        self._private_key_path = private_key_path
        self._private_key: str | None = None
        self._token: str | None = None
        self._token_expiry: float = 0
        self._session = requests.Session()

    # --------------------------------------------------------------------- #
    #  Connection                                                            #
    # --------------------------------------------------------------------- #

    def connect(self) -> None:
        """Load the private key and generate an initial JWT."""
        logger.info("🔗 Connecting to App Store Connect API …")

        if self.dry_run:
            logger.info("   [DRY-RUN] Skipping actual authentication.")
            return

        self._private_key = self._private_key_path.read_text()
        self._refresh_token()
        logger.info("✅ Connected to App Store Connect for App ID: %s", self.app_id)

    # --------------------------------------------------------------------- #
    #  Public API                                                            #
    # --------------------------------------------------------------------- #

    def sync_product(self, product: IAPProduct) -> bool:
        """
        Create (or detect existing) IAP, then set localizations & price.

        Returns True on success, False on failure.
        """
        if self.dry_run:
            self._log_dry_run(product)
            return True

        # Step 1: Create the IAP
        iap_id = self._create_iap(product)
        if not iap_id:
            return False

        # Step 2: Localizations
        ok_en = self._create_localization(iap_id, "en-US", product.name_en, product.desc_en)
        ok_vi = True
        if product.name_vi:
            ok_vi = self._create_localization(iap_id, "vi", product.name_vi, product.desc_vi)

        # Step 3: Price schedule
        ok_price = self._set_price_schedule(iap_id, product)

        return ok_en and ok_vi and ok_price

    def sync_all(self, products: list[IAPProduct]) -> dict[str, bool]:
        """Sync a list of products. Returns mapping product_id → success."""
        results: dict[str, bool] = {}
        for product in products:
            try:
                results[product.product_id] = self.sync_product(product)
            except Exception as exc:
                logger.error(
                    "❌ [App Store] Failed to sync '%s': %s",
                    product.product_id,
                    exc,
                )
                results[product.product_id] = False
        return results

    # --------------------------------------------------------------------- #
    #  JWT Token Management                                                  #
    # --------------------------------------------------------------------- #

    def _refresh_token(self) -> None:
        """Generate a new ES256 JWT valid for 20 minutes."""
        now = time.time()
        expiry = now + 20 * 60  # Apple allows max 20 min

        payload = {
            "iss": self.issuer_id,
            "iat": int(now),
            "exp": int(expiry),
            "aud": "appstoreconnect-v1",
        }
        headers_jwt = {
            "alg": "ES256",
            "kid": self.key_id,
            "typ": "JWT",
        }

        self._token = jwt.encode(
            payload, self._private_key, algorithm="ES256", headers=headers_jwt
        )
        self._token_expiry = expiry
        logger.debug("   JWT token generated, expires at %s", expiry)

    def _ensure_token(self) -> None:
        """Refresh the JWT if it is about to expire (< 2 min remaining)."""
        if time.time() > self._token_expiry - 120:
            self._refresh_token()

    def _headers(self) -> dict[str, str]:
        """Return authorization headers."""
        self._ensure_token()
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    # --------------------------------------------------------------------- #
    #  Step 1: Create In-App Purchase                                        #
    # --------------------------------------------------------------------- #

    def _create_iap(self, product: IAPProduct) -> str | None:
        """
        Create an In-App Purchase record under the app.

        Returns the IAP resource ID on success, or None on failure.
        If the product already exists (409), attempts to find it and return
        the existing ID.
        """
        iap_type = (
            "CONSUMABLE" if product.is_consumable else "NON_CONSUMABLE"
        )

        ref_name = product.product_id[:_REFERENCE_NAME_MAX]

        body = {
            "data": {
                "type": "inAppPurchases",
                "attributes": {
                    "name": ref_name,
                    "productId": product.product_id,
                    "inAppPurchaseType": iap_type,
                    "reviewNote": "",
                },
                "relationships": {
                    "app": {
                        "data": {
                            "type": "apps",
                            "id": self.app_id,
                        }
                    }
                },
            }
        }

        url = f"{_BASE_URL}/inAppPurchases"
        resp = self._session.post(url, json=body, headers=self._headers())

        if resp.status_code == 201:
            iap_id = resp.json()["data"]["id"]
            logger.info("   ✅ Created IAP on App Store: %s (id=%s)", product.product_id, iap_id)
            return iap_id

        if resp.status_code == 409:
            logger.info(
                "   ⚠️  IAP '%s' already exists – looking up existing ID …",
                product.product_id,
            )
            return self._find_existing_iap(product.product_id)

        logger.error(
            "   ❌ Failed to create IAP '%s': %s %s",
            product.product_id,
            resp.status_code,
            resp.text,
        )
        return None

    def _find_existing_iap(self, product_id: str) -> str | None:
        """Look up an existing IAP by productId under the app."""
        url = (
            f"{_BASE_URL_V1}/apps/{self.app_id}/inAppPurchasesV2"
            f"?filter[productId]={product_id}"
            f"&limit=1"
        )
        resp = self._session.get(url, headers=self._headers())

        if resp.status_code == 200:
            data = resp.json().get("data", [])
            if data:
                iap_id = data[0]["id"]
                logger.info("   Found existing IAP id=%s for '%s'", iap_id, product_id)
                return iap_id

        logger.error("   ❌ Could not find existing IAP for '%s'", product_id)
        return None

    # --------------------------------------------------------------------- #
    #  Step 2: Localizations                                                 #
    # --------------------------------------------------------------------- #

    def _create_localization(
        self, iap_id: str, locale: str, name: str, description: str
    ) -> bool:
        """Create a localization for a given IAP."""
        body = {
            "data": {
                "type": "inAppPurchaseLocalizations",
                "attributes": {
                    "name": name,
                    "description": description or name,
                    "locale": locale,
                },
                "relationships": {
                    "inAppPurchaseV2": {
                        "data": {
                            "type": "inAppPurchases",
                            "id": iap_id,
                        }
                    }
                },
            }
        }

        url = f"{_BASE_URL_V1}/inAppPurchaseLocalizations"
        resp = self._session.post(url, json=body, headers=self._headers())

        if resp.status_code in (201, 200):
            logger.info("      ✅ Localization [%s] created for IAP %s", locale, iap_id)
            return True

        if resp.status_code == 409:
            logger.info(
                "      ⚠️  Localization [%s] already exists for IAP %s – updating …",
                locale, iap_id,
            )
            return self._update_localization(iap_id, locale, name, description)

        logger.error(
            "      ❌ Localization [%s] failed for IAP %s: %s %s",
            locale, iap_id, resp.status_code, resp.text,
        )
        return False

    def _update_localization(
        self, iap_id: str, locale: str, name: str, description: str
    ) -> bool:
        """Find and update an existing localization."""
        # Find the localization ID first
        url = (
            f"{_BASE_URL}/inAppPurchases/{iap_id}/inAppPurchaseLocalizations"
            f"?filter[locale]={locale}&limit=1"
        )
        resp = self._session.get(url, headers=self._headers())

        if resp.status_code != 200 or not resp.json().get("data"):
            logger.error("      ❌ Could not find localization [%s] for IAP %s", locale, iap_id)
            return False

        loc_id = resp.json()["data"][0]["id"]

        patch_body = {
            "data": {
                "type": "inAppPurchaseLocalizations",
                "id": loc_id,
                "attributes": {
                    "name": name,
                    "description": description or name,
                },
            }
        }

        patch_resp = self._session.patch(
            f"{_BASE_URL_V1}/inAppPurchaseLocalizations/{loc_id}",
            json=patch_body,
            headers=self._headers(),
        )

        if patch_resp.status_code in (200, 204):
            logger.info("      ✅ Localization [%s] updated for IAP %s", locale, iap_id)
            return True

        logger.error(
            "      ❌ Localization [%s] update failed: %s %s",
            locale, patch_resp.status_code, patch_resp.text,
        )
        return False

    # --------------------------------------------------------------------- #
    #  Step 3: Price Schedule                                                #
    # --------------------------------------------------------------------- #

    def _set_price_schedule(self, iap_id: str, product: IAPProduct) -> bool:
        """
        Set the base price schedule for an IAP.

        Apple uses a price-point-based system. We look up the price point
        ID that matches the USD price.
        """
        price_str = str(product.base_price_usd)
        tier = _USD_TO_PRICE_TIER.get(price_str)

        if tier is None:
            logger.warning(
                "      ⚠️  No known Apple price tier for $%s – "
                "you may need to set the price manually in App Store Connect.",
                price_str,
            )
            return True  # Non-fatal

        # Look up the actual pricePoint ID from Apple
        price_point_id = self._find_price_point(iap_id, price_str)
        if not price_point_id:
            logger.warning(
                "      ⚠️  Could not resolve Apple price point for $%s. "
                "Price must be set manually.",
                price_str,
            )
            return True

        body = {
            "data": {
                "type": "inAppPurchasePriceSchedules",
                "relationships": {
                    "inAppPurchase": {
                        "data": {"type": "inAppPurchases", "id": iap_id}
                    },
                    "baseTerritory": {
                        "data": {"type": "territories", "id": "USA"}
                    },
                    "manualPrices": {
                        "data": [
                            {
                                "type": "inAppPurchasePrices",
                                "id": "${price-1}",
                            }
                        ]
                    },
                },
            },
            "included": [
                {
                    "type": "inAppPurchasePrices",
                    "id": "${price-1}",
                    "relationships": {
                        "inAppPurchasePricePoint": {
                            "data": {
                                "type": "inAppPurchasePricePoints",
                                "id": price_point_id,
                            }
                        }
                    },
                }
            ],
        }

        url = f"{_BASE_URL_V1}/inAppPurchasePriceSchedules"
        resp = self._session.post(url, json=body, headers=self._headers())

        if resp.status_code in (201, 200):
            logger.info("      ✅ Price schedule set ($%s) for IAP %s", price_str, iap_id)
            return True

        if resp.status_code == 409:
            logger.info(
                "      ⚠️  Price schedule already exists for IAP %s – skipping.",
                iap_id,
            )
            return True

        logger.error(
            "      ❌ Price schedule failed for IAP %s: %s %s",
            iap_id, resp.status_code, resp.text,
        )
        return False

    def _find_price_point(self, iap_id: str, usd_price: str) -> str | None:
        """
        Query the App Store Connect API to find the pricePoint ID
        for the given USD amount.
        """
        url = (
            f"{_BASE_URL}/inAppPurchases/{iap_id}/pricePoints"
            f"?filter[territory]=USA"
            f"&limit=200"
        )
        resp = self._session.get(url, headers=self._headers())

        if resp.status_code != 200:
            logger.debug("   Could not fetch price points: %s", resp.text)
            return None

        for pp in resp.json().get("data", []):
            attrs = pp.get("attributes", {})
            customer_price = attrs.get("customerPrice")
            if customer_price and str(customer_price) == usd_price:
                return pp["id"]

        return None

    # --------------------------------------------------------------------- #
    #  Dry-run logging                                                       #
    # --------------------------------------------------------------------- #

    def _log_dry_run(self, product: IAPProduct) -> None:
        """Pretty-print what would be sent to the API."""
        iap_type = "CONSUMABLE" if product.is_consumable else "NON_CONSUMABLE"
        locales = ["en-US"]
        if product.name_vi:
            locales.append("vi")

        tier = _USD_TO_PRICE_TIER.get(str(product.base_price_usd), "?")

        logger.info(
            "   [DRY-RUN] App Store → %s\n"
            "      Type        : %s\n"
            "      Price       : $%s (tier %s)\n"
            "      Localizations : %s\n"
            "      Flow        : Create IAP → Localizations → Price Schedule",
            product.product_id,
            iap_type,
            product.base_price_usd,
            tier,
            ", ".join(locales),
        )
