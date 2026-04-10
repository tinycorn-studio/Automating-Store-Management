# 🚀 Automating Store Management

A Python CLI tool to **automate store setup** on both **Google Play Console** and **Apple App Store Connect** from a **Google Sheet** — the single source of truth for your Product team.

> **No more manual store setup.** Your team edits a Google Sheet → runs one command → both stores are updated.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **IAP Sync** | Batch create/update In-App Purchases on both stores |
| **Store Listing** | Sync app name, description, keywords across locales |
| **Screenshot Upload** | Upload screenshots by locale and device type |
| **Google Sheets** | Product team edits data online, no file sharing needed |
| **Dual-platform** | Google Play + App Store Connect in one command |
| **Dry-run mode** | Preview all changes before making real API calls |
| **Multi-language** | Built-in support for English (en-US) and Vietnamese (vi) |
| **Offline fallback** | Also supports local `.xlsx` files when not using Sheets |

---

## 🔄 How It Works

```
Google Sheet                        MainController
  ├── Tab: IAP Data      ──────▶     ├── DataParser        ──▶  IAP Products
  ├── Tab: Store Listing  ─────▶     ├── ListingParser     ──▶  App Metadata
  └── Tab: Screenshots    ─────▶     └── ScreenshotParser  ──▶  Images
                                           │
                               ┌───────────┼───────────┐
                               ▼                       ▼
                     GooglePlayClient          AppStoreClient
                     (Edits API v3)           (REST API v2 / JWT)
```

**Workflow for Product Team:**
1. ✏️ Edit data in the shared Google Sheet
2. 🔍 Run `python main.py iap --dry-run` to preview changes
3. 🚀 Run `python main.py iap --live` to push to stores

---

## 📁 Project Structure

```
AutoStoreSetup/
├── main.py                          # CLI entry point (subcommands)
├── dashboard.py                     # 🌐 Streamlit web dashboard
├── generate_sample_data.py          # Generate sample iap_data.xlsx
├── requirements.txt                 # Python dependencies
├── .env.example                     # Environment config template
├── docs/
│   └── ROADMAP.md                   # Expansion roadmap
├── credentials/                     # (gitignored) API keys go here
│   ├── service_account.json         # Google Cloud Service Account
│   └── AuthKey_XXXXXXXXXX.p8        # Apple API private key
└── auto_store_setup/
    ├── __init__.py
    ├── config.py                    # Config loader from .env
    ├── data_parser.py               # IAP data parser + IAPProduct model
    ├── listing_parser.py            # Store Listing parser + StoreListingData
    ├── screenshot_parser.py         # Screenshot manifest parser
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

This single service account is used for **Google Play API + Google Sheets API**.

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

Create a Google Sheet with **3 tabs** (worksheets):

#### Tab 1: `Sheet1` (IAP Data)

| product_id | iap_type | base_price_usd | name_en | desc_en | name_vi | desc_vi |
|---|---|---|---|---|---|---|
| com.studio.game.gem_pack_1 | consumable | 0.99 | Gem Pack – Small | 100 gems | Gói Kim Cương – Nhỏ | 100 kim cương |
| com.studio.game.no_ads | non-consumable | 2.99 | Remove Ads | Remove all ads | Xóa Quảng Cáo | Xóa quảng cáo |

#### Tab 2: `Store Listing`

| field | en-US | vi |
|-------|-------|-----|
| app_name | Water Go Puzzle | Water Go - Xếp Hình |
| short_description | Fun water puzzle game! | Trò chơi xếp hình nước! |
| full_description | (long text...) | (text dài...) |
| keywords | puzzle,water,game | xếp hình,nước,game |
| promo_text | New levels available! | Có màn mới! |
| support_url | https://support.example.com | https://support.example.com |
| marketing_url | https://www.example.com | https://www.example.com |

#### Tab 3: `Screenshots`

| locale | device_type | display_order | file_path |
|--------|-------------|---------------|-----------|
| en-US | phone_6.5 | 1 | ./screenshots/en/phone_01.png |
| en-US | phone_6.5 | 2 | ./screenshots/en/phone_02.png |
| vi | phone_6.5 | 1 | ./screenshots/vi/phone_01.png |
| en-US | tablet_12.9 | 1 | ./screenshots/en/tablet_01.png |

**Supported device types:** `phone`, `phone_5.5`, `phone_6.5`, `phone_6.7`, `tablet`, `tablet_7`, `tablet_10`, `tablet_12.9`, `tv`, `wear`

**Important:** Share the Google Sheet with your service account email:
```
your-sa-name@your-project.iam.gserviceaccount.com
```

> 💡 Find your service account email in `credentials/service_account.json` → `"client_email"` field.

### 4. Configure `.env`

```bash
cp .env.example .env
```

Edit `.env` with your actual values:

```env
# --- Data Source ---
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

### 5. Run!

```bash
# IAP: preview first
python main.py iap --dry-run

# IAP: push to stores
python main.py iap --live

# Store Listing: update metadata
python main.py listing --dry-run

# Screenshots: upload images
python main.py screenshots --dry-run
```

---

## 🔧 CLI Reference

```
Usage: main.py [OPTIONS] COMMAND [ARGS]...

Global Options:
  -s, --source [excel|gsheet]    Data source type (overrides .env)
  --env PATH                     Custom .env file path
  -v, --verbose                  Debug logging
  -h, --help                     Show help

Commands:
  iap           Sync In-App Purchases
  listing       Sync Store Listing metadata
  screenshots   Upload app screenshots

Subcommand Options (shared):
  -p, --platform [google|apple|both]   Target platform(s)    [default: both]
  -d, --dry-run                        Force dry-run mode
  -l, --live                           Force live mode
```

### Common commands

```bash
# ── IAP ──────────────────────────────────────
python main.py iap                          # Dry-run, both platforms
python main.py iap --platform google        # Google Play only
python main.py iap --platform apple --live  # Apple only, live mode
python main.py iap --data ./custom.xlsx     # Use local Excel file

# ── Store Listing ────────────────────────────
python main.py listing                      # Preview listing changes
python main.py listing --live               # Push to both stores

# ── Screenshots ──────────────────────────────
python main.py screenshots                  # Preview screenshot upload
python main.py screenshots --live           # Upload to both stores

# ── Global options ───────────────────────────
python main.py --source excel iap           # Force Excel mode
python main.py -v listing                   # Verbose logging
```

---

## 🔄 API Flow

### IAP Sync
| Google Play | Apple App Store |
|-------------|-----------------|
| Service Account auth | JWT ES256 auth |
| Try `update()` → if 404 → `insert()` | Create IAP → Localizations → Price Schedule |
| `edits().inappproducts()` API | `/v2/inAppPurchases` + `/v1/inAppPurchaseLocalizations` |

### Store Listing
| Google Play | Apple App Store |
|-------------|-----------------|
| Create Edit session | Get editable `appStoreVersion` |
| `edits().listings().update()` per locale | `PATCH /v1/appStoreVersionLocalizations` |
| Commit Edit | Auto-saved |

### Screenshots
| Google Play | Apple App Store |
|-------------|-----------------|
| Create Edit session | Find `appStoreVersionLocalization` |
| `edits().images().upload()` | Create `appScreenshotSet` → Reserve → Upload binary → Commit |
| Commit Edit | Auto-processed |

---

## 🛡️ Error Handling

| Scenario | Behavior |
|----------|----------|
| Product already exists | Auto-update (Google) / Find & reuse ID (Apple 409) |
| Google Sheet not shared | Clear error: "Share with service account email" |
| Worksheet not found | Error with worksheet name |
| Screenshot file missing | Warning, skip file, continue with rest |
| No editable version (Apple) | Error message: "Create a new version first" |
| Network error | Log error, continue with next item |
| JWT expired | Auto-refresh token (Apple) |
| Missing columns | `ValueError` with list of missing column names |

---

## 📊 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATA_SOURCE` | Yes | `gsheet` (recommended) or `excel` |
| `GOOGLE_SHEET_ID` | If gsheet | Spreadsheet ID from the Google Sheets URL |
| `GOOGLE_SHEET_WORKSHEET` | No | IAP worksheet name (default: first sheet) |
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
    ├── DataParser ──────────▶ List[IAPProduct]
    │     ├── Google Sheets (gspread)
    │     └── Local Excel (pandas)
    │
    ├── ListingParser ───────▶ StoreListingData
    │     └── (same dual source)
    │
    ├── ScreenshotParser ────▶ ScreenshotManifest
    │     └── (same dual source)
    │
    ├── GooglePlayClient
    │     └── Android Publisher API v3 (Edits API)
    │
    └── AppStoreClient
          └── App Store Connect REST API v2 (JWT/ES256)
```

| Class | Responsibility |
|-------|---------------|
| `Config` | Load & validate `.env` settings |
| `DataParser` | Read IAP data → `List[IAPProduct]` |
| `ListingParser` | Read Store Listing → `StoreListingData` |
| `ScreenshotParser` | Read manifest → `ScreenshotManifest` |
| `GooglePlayClient` | IAP + Listing + Screenshot sync to Google Play |
| `AppStoreClient` | IAP + Listing + Screenshot sync to App Store |
| `MainController` | Orchestrate: parse → connect → sync → report |

---

## 🌐 Web Dashboard (Streamlit)

Ngoài CLI, bạn có thể dùng **giao diện web** để quản lý store trực quan hơn:

```bash
# Windows
.\venv\Scripts\streamlit.exe run dashboard.py

# macOS / Linux
streamlit run dashboard.py
```

→ Trình duyệt tự mở tại `http://localhost:8501`

### Dashboard gồm:

| Tab | Chức năng |
|-----|----------|
| 🛒 **IAP Sync** | Preview bảng data, metrics (Consumable/Non-Consumable), nút Dry Run / Push |
| 📝 **Store Listing** | Bảng mẫu format, sync app name/description/keywords |
| 📸 **Screenshots** | Danh sách device types, upload screenshots bulk |
| ❓ **Help** | Hướng dẫn setup step-by-step |

### So sánh CLI vs Dashboard

| | CLI | Dashboard |
|---|---|---|
| Cài đặt | `.env` file | Điền trực tiếp trên sidebar |
| Chạy lệnh | Terminal | Bấm nút |
| Xem data | Log text | Bảng preview + metrics |
| Kết quả | Log text | Log có màu + summary |
| Upload file | Chỉ đường dẫn | Kéo thả file |
| Phù hợp | Developer, CI/CD | Product Team, non-tech |

---

## 📄 License

MIT License — feel free to use and modify.
