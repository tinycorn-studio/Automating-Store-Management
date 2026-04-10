# 🚀 Automating Store Management

A Python CLI tool to **batch create and update In-App Purchases (IAP)** on both **Google Play Console** and **Apple App Store Connect** from a **Google Sheet** — the single source of truth for your Product team.

> **No more manual IAP setup.** Your team edits a Google Sheet → runs one command → both stores are updated.

---

## ✨ Features

- **Google Sheets as source of truth** — Product team edits data online, no file sharing needed
- **Fallback to local Excel** — Also supports `.xlsx` files when offline
- **Dual-platform sync** — Google Play + App Store Connect in one command
- **Dry-run mode** — Preview all changes before making real API calls
- **Multi-language** — Built-in support for English (en-US) and Vietnamese (vi) localizations
- **Smart conflict handling** — Automatically detects existing products and updates them
- **Structured logging** — Clear, timestamped console output for easy tracking
- **OOP architecture** — Clean separation: `DataParser`, `GooglePlayClient`, `AppStoreClient`, `MainController`

---

## 🔄 How It Works

```
┌──────────────┐       ┌──────────────────┐       ┌─────────────────┐
│              │       │                  │       │  Google Play    │
│ Google Sheet │──────▶│  AutoStoreSetup  │──────▶│  Console API    │
│ (IAP Data)   │       │  (Python CLI)    │       │                 │
│              │       │                  │       ├─────────────────┤
└──────────────┘       │  1. Parse data   │       │  App Store      │
                       │  2. Validate     │──────▶│  Connect API    │
                       │  3. Sync to APIs │       │                 │
                       └──────────────────┘       └─────────────────┘
```

**Workflow for Product Team:**
1. ✏️ Edit IAP data in the shared Google Sheet
2. 🔍 Run `python main.py --dry-run` to preview changes
3. 🚀 Run `python main.py --live` to push to stores

---

## 📁 Project Structure

```
AutoStoreSetup/
├── main.py                          # CLI entry point
├── generate_sample_data.py          # Generate sample iap_data.xlsx
├── requirements.txt                 # Python dependencies
├── .env.example                     # Environment config template
├── .gitignore
├── credentials/                     # (gitignored) API keys go here
│   ├── service_account.json         # Google Cloud Service Account
│   └── AuthKey_XXXXXXXXXX.p8        # Apple API private key
└── auto_store_setup/
    ├── __init__.py
    ├── config.py                    # Config loader from .env
    ├── data_parser.py               # Google Sheets / Excel parser + IAPProduct model
    ├── google_play_client.py        # Google Play Android Publisher API v3
    ├── appstore_client.py           # App Store Connect REST API v2 (JWT)
    └── controller.py                # Pipeline orchestrator
```

---

## ⚡ Quick Start

### 1. Install dependencies

```bash
cd AutoStoreSetup
python -m venv venv

# Windows
.\venv\Scripts\Activate.ps1

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Set up credentials

#### Google Cloud Service Account

This single service account is used for **both** Google Play API and Google Sheets API.

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials
2. Create a **Service Account** → Download the JSON key file
3. Enable these APIs in your GCP project:
   - ✅ **Google Play Android Developer API**
   - ✅ **Google Sheets API**
4. In [Google Play Console](https://play.google.com/console) → Settings → API Access → Link the service account
5. Save the JSON key to `credentials/service_account.json`

#### Apple App Store Connect

1. Go to [App Store Connect](https://appstoreconnect.apple.com/) → Users and Access → Integrations → Keys
2. Create an API Key with **Admin** or **App Manager** role
3. Note the **Key ID** and **Issuer ID**
4. Download the `.p8` file (only available once!) → Save to `credentials/`

### 3. Prepare your Google Sheet

Create a Google Sheet with these exact column headers in Row 1:

| product_id | iap_type | base_price_usd | name_en | desc_en | name_vi | desc_vi |
|---|---|---|---|---|---|---|
| `com.studio.game.gem_pack_1` | `consumable` | `0.99` | Gem Pack – Small | 100 gems to boost progress | Gói Kim Cương – Nhỏ | 100 kim cương |
| `com.studio.game.no_ads` | `non-consumable` | `2.99` | Remove Ads | Remove all ads permanently | Xóa Quảng Cáo | Xóa vĩnh viễn quảng cáo |

**Column Reference:**

| Column | Type | Description |
|--------|------|-------------|
| `product_id` | string | Unique IAP ID (e.g. `com.studio.game.gem_pack_1`) |
| `iap_type` | string | `consumable` or `non-consumable` |
| `base_price_usd` | decimal | Base price in USD (e.g. `0.99`, `4.99`) |
| `name_en` | string | Display name in English |
| `desc_en` | string | Description in English |
| `name_vi` | string | Display name in Vietnamese |
| `desc_vi` | string | Description in Vietnamese |

**Important:** Share the Google Sheet with your service account email:
```
your-sa-name@your-project.iam.gserviceaccount.com
```
Grant **Viewer** permission (read-only is sufficient).

> 💡 Find your service account email in `credentials/service_account.json` → `"client_email"` field.

### 4. Configure `.env`

```bash
cp .env.example .env
```

Edit `.env` with your actual values:

```env
# --- Data Source (Google Sheets) ---
DATA_SOURCE=gsheet
GOOGLE_SHEET_ID=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms
GOOGLE_SHEET_WORKSHEET=Sheet1

# --- Google Play ---
GOOGLE_PLAY_PACKAGE_NAME=com.studio.game
GOOGLE_SERVICE_ACCOUNT_JSON=./credentials/service_account.json

# --- Apple App Store Connect ---
APPLE_KEY_ID=XXXXXXXXXX
APPLE_ISSUER_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
APPLE_PRIVATE_KEY_PATH=./credentials/AuthKey_XXXXXXXXXX.p8
APPLE_APP_ID=1234567890

# --- Mode ---
DRY_RUN=true
```

**How to get `GOOGLE_SHEET_ID`:**
```
https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms/edit
                                       └──────────── This is your SHEET ID ────────────┘
```

### 5. Run!

```bash
# Step 1: Always dry-run first to preview
python main.py

# Step 2: When ready, push to stores
python main.py --live
```

---

## 🔧 CLI Reference

```
Usage: main.py [OPTIONS]

Options:
  -p, --platform [google|apple|both]   Target platform(s)          [default: both]
  -s, --source [excel|gsheet]          Data source type             [from .env]
  -d, --dry-run                        Force dry-run mode
  -l, --live                           Force live mode (real API calls)
  --data PATH                          Custom .xlsx file path (Excel mode)
  --env PATH                           Custom .env file path
  -v, --verbose                        Debug logging
  -h, --help                           Show help
```

### Common commands

```bash
# Dry-run, both platforms, from Google Sheet (default)
python main.py

# Sync only Google Play
python main.py --platform google

# Sync only Apple App Store
python main.py --platform apple

# Use a local Excel file instead of Google Sheet
python main.py --source excel --data ./iap_data.xlsx

# Live mode — actually push to stores
python main.py --live

# Verbose/debug output
python main.py -v --dry-run
```

---

## 🔄 API Flow

### Google Play
1. Authenticate with Service Account
2. For each product: try `update()` → if 404 → `insert()` (create new)
3. Maps locales to `listings` structure (`en-US`, `vi`)

### Apple App Store Connect
1. Generate JWT token (ES256) from `.p8` key
2. **Step 1:** Create IAP resource via `/v2/inAppPurchases`
3. **Step 2:** Create Localizations for each language (en-US, vi)
4. **Step 3:** Set Price Schedule with matching Apple price tier

---

## 🛡️ Error Handling

| Scenario | Behavior |
|----------|----------|
| Product already exists | Auto-update (Google) / Find & reuse ID (Apple 409) |
| Google Sheet not shared | Clear error: "Share with service account email" |
| Worksheet not found | Error with worksheet name |
| Network error | Log error, continue with next product |
| Invalid price | Warning, skip pricing step |
| JWT expired | Auto-refresh token (Apple) |
| Missing columns | `ValueError` with list of missing column names |

---

## 📊 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATA_SOURCE` | Yes | `gsheet` (recommended) or `excel` |
| `GOOGLE_SHEET_ID` | If gsheet | Spreadsheet ID from the Google Sheets URL |
| `GOOGLE_SHEET_WORKSHEET` | No | Worksheet/tab name (default: first sheet) |
| `IAP_DATA_FILE` | If excel | Path to local `.xlsx` file |
| `GOOGLE_PLAY_PACKAGE_NAME` | Yes | Android package name |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Yes | Path to GCP service account JSON key |
| `APPLE_KEY_ID` | Yes | App Store Connect API Key ID |
| `APPLE_ISSUER_ID` | Yes | App Store Connect Issuer ID (UUID) |
| `APPLE_PRIVATE_KEY_PATH` | Yes | Path to `.p8` private key file |
| `APPLE_APP_ID` | Yes | Numeric Apple App ID |
| `DRY_RUN` | No | `true` = simulate, `false` = real API calls (default: `true`) |

---

## 🧩 Architecture

```
Config (.env)
    │
    ▼
MainController
    ├── DataParser
    │     ├── Google Sheets (gspread + service account)
    │     └── Local Excel (pandas + openpyxl)
    │           ▼
    │     List[IAPProduct]
    │
    ├── GooglePlayClient
    │     └── Android Publisher API v3
    │
    └── AppStoreClient
          └── App Store Connect REST API v2 (JWT/ES256)
```

| Class | Responsibility |
|-------|---------------|
| `Config` | Load & validate `.env` settings |
| `DataParser` | Read Google Sheet or Excel → `List[IAPProduct]` |
| `IAPProduct` | Typed data model for a single IAP |
| `GooglePlayClient` | Authenticate & sync to Google Play |
| `AppStoreClient` | JWT auth & 3-step sync to App Store |
| `MainController` | Orchestrate: parse → connect → sync → report |

---

## 📄 License

MIT License — feel free to use and modify.
