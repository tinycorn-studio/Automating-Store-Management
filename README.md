# 🚀 Automating Store Management

A Python CLI tool to **batch create and update In-App Purchases (IAP)** on both **Google Play Console** and **Apple App Store Connect** from a single Excel spreadsheet.

Built for Product teams to eliminate manual IAP setup across platforms.

---

## ✨ Features

- **Single source of truth** — Define all IAPs in one `iap_data.xlsx` file
- **Dual-platform sync** — Google Play + App Store Connect in one command
- **Dry-run mode** — Preview all changes before making real API calls
- **Multi-language** — Built-in support for English (en-US) and Vietnamese (vi) localizations
- **Smart conflict handling** — Automatically detects existing products and updates them
- **Structured logging** — Clear, timestamped console output for easy tracking
- **OOP architecture** — Clean separation: `DataParser`, `GooglePlayClient`, `AppStoreClient`, `MainController`

---

## 📁 Project Structure

```
AutoStoreSetup/
├── main.py                          # CLI entry point
├── generate_sample_data.py          # Generate sample iap_data.xlsx
├── requirements.txt                 # Python dependencies
├── .env.example                     # Environment config template
├── .gitignore
├── iap_data.xlsx                    # Sample IAP data (10 products)
├── credentials/                     # (gitignored) API keys go here
│   ├── service_account.json         # Google Cloud Service Account
│   └── AuthKey_XXXXXXXXXX.p8        # Apple API private key
└── auto_store_setup/
    ├── __init__.py
    ├── config.py                    # Config loader from .env
    ├── data_parser.py               # Excel parser + IAPProduct model
    ├── google_play_client.py        # Google Play Android Publisher API v3
    ├── appstore_client.py           # App Store Connect REST API v2 (JWT)
    └── controller.py                # Pipeline orchestrator
```

---

## ⚡ Quick Start

### 1. Install

```bash
python -m venv venv

# Windows
.\venv\Scripts\Activate.ps1

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your credentials
```

| Variable | Description |
|----------|-------------|
| `GOOGLE_PLAY_PACKAGE_NAME` | Android package name (e.g. `com.studio.game`) |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Path to GCP service account JSON key |
| `APPLE_KEY_ID` | App Store Connect API Key ID |
| `APPLE_ISSUER_ID` | App Store Connect Issuer ID (UUID) |
| `APPLE_PRIVATE_KEY_PATH` | Path to `.p8` private key file |
| `APPLE_APP_ID` | Numeric Apple App ID |
| `DRY_RUN` | `true` = simulate only, `false` = call real APIs |

### 3. Prepare Data

Edit `iap_data.xlsx` or generate sample data:

```bash
python generate_sample_data.py
```

**Spreadsheet columns:**

| Column | Type | Example |
|--------|------|---------|
| `product_id` | string | `com.studio.game.gem_pack_1` |
| `iap_type` | string | `consumable` or `non-consumable` |
| `base_price_usd` | decimal | `0.99` |
| `name_en` | string | `Gem Pack – Small` |
| `desc_en` | string | `A small pack of 100 gems` |
| `name_vi` | string | `Gói Kim Cương – Nhỏ` |
| `desc_vi` | string | `Gói nhỏ gồm 100 kim cương` |

### 4. Run

```bash
# Dry-run (safe preview)
python main.py

# Sync only Google Play
python main.py --platform google

# Sync only Apple
python main.py --platform apple

# Live mode (actual API calls)
python main.py --live

# All options
python main.py --help
```

---

## 🔧 CLI Options

```
Options:
  -p, --platform [google|apple|both]   Target platform(s)  [default: both]
  -d, --dry-run                        Force dry-run mode
  -l, --live                           Force live mode
  --data PATH                          Custom spreadsheet path
  --env PATH                           Custom .env file path
  -v, --verbose                        Debug logging
  -h, --help                           Show help
```

---

## 🔄 API Flow

### Google Play
1. Authenticate with Service Account
2. For each product: try `update()` → if 404 → `insert()`
3. Maps locales to `listings` (`en-US`, `vi`)

### Apple App Store Connect
1. Generate JWT (ES256) from `.p8` key
2. Create IAP resource (`/v2/inAppPurchases`)
3. Create Localizations for each language
4. Set Price Schedule with matching price tier

---

## 🛡️ Error Handling

| Scenario | Behavior |
|----------|----------|
| Product already exists | Auto-update (Google) / Find & reuse ID (Apple) |
| Network error | Log error, continue with next product |
| Invalid price | Warning, skip pricing step |
| JWT expired | Auto-refresh token |
| Missing Excel columns | Raise `ValueError` with details |

---

## 📋 Setting Up Credentials

### Google Play
1. Go to [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials
2. Create a **Service Account** → Download JSON key
3. Enable **Google Play Android Developer API**
4. In Google Play Console → Settings → API Access → Link the service account

### Apple App Store Connect
1. Go to [App Store Connect](https://appstoreconnect.apple.com/) → Users and Access → Integrations → Keys
2. Create an API Key with **Admin** or **App Manager** role
3. Note the **Key ID** and **Issuer ID**
4. Download the `.p8` file (only available once!)

---

## 📄 License

MIT License — feel free to use and modify.
