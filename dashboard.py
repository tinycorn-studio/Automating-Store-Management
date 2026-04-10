"""
AutoStoreSetup — Streamlit Dashboard
=====================================

A visual web interface for the AutoStoreSetup CLI tool.
Run with: streamlit run dashboard.py
"""

import io
import logging
import sys
import time
from dataclasses import replace
from pathlib import Path

import pandas as pd
import streamlit as st

# ──────────────────────────────────────────────────────────────────────── #
#  Page Config                                                            #
# ──────────────────────────────────────────────────────────────────────── #

st.set_page_config(
    page_title="AutoStoreSetup",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────────────────────────────── #
#  Custom CSS                                                             #
# ──────────────────────────────────────────────────────────────────────── #

st.markdown("""
<style>
    /* Main container */
    .main .block-container {
        padding-top: 2rem;
        max-width: 1200px;
    }

    /* Header styling */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        color: white;
    }
    .main-header h1 {
        margin: 0;
        font-size: 1.8rem;
        font-weight: 700;
    }
    .main-header p {
        margin: 0.3rem 0 0 0;
        opacity: 0.85;
        font-size: 0.95rem;
    }

    /* Metric cards */
    .metric-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        border: 1px solid rgba(0,0,0,0.05);
    }
    .metric-card h3 { margin: 0; font-size: 2rem; color: #333; }
    .metric-card p { margin: 0; font-size: 0.85rem; color: #666; }

    /* Status badges */
    .badge-dryrun {
        background: #FFF3CD; color: #856404;
        padding: 0.25rem 0.75rem; border-radius: 20px;
        font-weight: 600; font-size: 0.85rem;
        display: inline-block;
    }
    .badge-live {
        background: #D4EDDA; color: #155724;
        padding: 0.25rem 0.75rem; border-radius: 20px;
        font-weight: 600; font-size: 0.85rem;
        display: inline-block;
    }

    /* Log container */
    .log-container {
        background: #1e1e2e;
        color: #cdd6f4;
        padding: 1rem;
        border-radius: 8px;
        font-family: 'Fira Code', 'Consolas', monospace;
        font-size: 0.8rem;
        max-height: 400px;
        overflow-y: auto;
        line-height: 1.5;
    }
    .log-success { color: #a6e3a1; }
    .log-warning { color: #f9e2af; }
    .log-error { color: #f38ba8; }
    .log-info { color: #89b4fa; }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        color: #e0e0e0;
    }
    [data-testid="stSidebar"] label {
        color: #ccc !important;
    }

    /* Hide Streamlit branding */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }

    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 8px 16px;
    }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────── #
#  Log Capture                                                            #
# ──────────────────────────────────────────────────────────────────────── #

class StreamlitLogHandler(logging.Handler):
    """Captures log messages into a list for display in the UI."""

    def __init__(self):
        super().__init__()
        self.logs: list[dict] = []

    def emit(self, record):
        self.logs.append({
            "time": time.strftime("%H:%M:%S"),
            "level": record.levelname,
            "message": record.getMessage(),
        })

    def get_html(self) -> str:
        lines = []
        for log in self.logs:
            css_class = {
                "INFO": "log-info",
                "WARNING": "log-warning",
                "ERROR": "log-error",
                "DEBUG": "log-info",
            }.get(log["level"], "")

            msg = log["message"].replace("<", "&lt;").replace(">", "&gt;")
            # Color special markers
            for marker, cls in [("✅", "log-success"), ("❌", "log-error"), ("⚠️", "log-warning"), ("DRY-RUN", "log-warning")]:
                if marker in msg:
                    css_class = cls
                    break

            lines.append(
                f'<span class="{css_class}">{log["time"]} | {msg}</span>'
            )
        return "<br>".join(lines)


def setup_log_capture() -> StreamlitLogHandler:
    """Set up log capture for the auto_store_setup module."""
    handler = StreamlitLogHandler()
    handler.setLevel(logging.DEBUG)

    logger = logging.getLogger("auto_store_setup")
    logger.setLevel(logging.INFO)
    # Remove previous handlers to avoid duplicates
    logger.handlers = [handler]

    return handler


# ──────────────────────────────────────────────────────────────────────── #
#  Data Loading Helpers                                                   #
# ──────────────────────────────────────────────────────────────────────── #

def load_iap_data(source: str, file=None, sheet_id: str = "", worksheet: str = "", sa_path: str = "") -> pd.DataFrame | None:
    """Load IAP data from Excel or Google Sheet for preview."""
    try:
        if source == "excel" and file is not None:
            return pd.read_excel(file, engine="openpyxl")
        elif source == "gsheet" and sheet_id:
            import gspread
            gc = gspread.service_account(filename=sa_path)
            spreadsheet = gc.open_by_key(sheet_id)
            ws = spreadsheet.worksheet(worksheet) if worksheet else spreadsheet.sheet1
            records = ws.get_all_records()
            if records:
                return pd.DataFrame(records)
    except Exception as e:
        st.error(f"Error loading data: {e}")
    return None


# ──────────────────────────────────────────────────────────────────────── #
#  Sidebar — Configuration                                                #
# ──────────────────────────────────────────────────────────────────────── #

with st.sidebar:
    st.markdown("## ⚙️ Configuration")
    st.markdown("---")

    # Data Source
    st.markdown("### 📊 Data Source")
    data_source = st.radio(
        "Source type",
        ["Google Sheet", "Excel File"],
        horizontal=True,
        label_visibility="collapsed",
    )

    uploaded_file = None
    sheet_id = ""
    sheet_worksheet = ""

    if data_source == "Google Sheet":
        sheet_id = st.text_input("Google Sheet ID", placeholder="1BxiMVs0XRA5n...")
        sheet_worksheet = st.text_input("Worksheet name", value="Sheet1")
    else:
        uploaded_file = st.file_uploader("Upload .xlsx file", type=["xlsx"])

    st.markdown("---")

    # Credentials
    st.markdown("### 🔑 Credentials")

    sa_json = st.text_input(
        "Service Account JSON",
        value="./credentials/service_account.json",
        help="Path to Google Cloud service account key",
    )

    st.markdown("---")
    st.markdown("#### 🍎 Apple")
    apple_key_id = st.text_input("Key ID", placeholder="XXXXXXXXXX")
    apple_issuer_id = st.text_input("Issuer ID", placeholder="xxxxxxxx-xxxx-...")
    apple_p8_path = st.text_input("Private Key (.p8)", value="./credentials/AuthKey.p8")
    apple_app_id = st.text_input("Apple App ID", placeholder="1234567890")

    st.markdown("---")
    st.markdown("#### 📱 Google Play")
    gp_package = st.text_input("Package Name", placeholder="com.studio.game")

    st.markdown("---")

    # Platform & Mode
    st.markdown("### 🎯 Platform")
    platform = st.radio(
        "Target",
        ["Both", "Apple Only", "Google Only"],
        horizontal=False,
    )

    st.markdown("---")

    # Status indicator
    config_valid = True
    issues = []

    if data_source == "Google Sheet" and not sheet_id:
        config_valid = False
        issues.append("Sheet ID missing")
    if data_source == "Excel File" and uploaded_file is None:
        config_valid = False
        issues.append("No file uploaded")

    if config_valid:
        st.success("✅ Config ready")
    else:
        for issue in issues:
            st.warning(f"⚠️ {issue}")


# ──────────────────────────────────────────────────────────────────────── #
#  Main Content                                                           #
# ──────────────────────────────────────────────────────────────────────── #

# Header
st.markdown("""
<div class="main-header">
    <h1>🚀 AutoStoreSetup Dashboard</h1>
    <p>Batch manage IAP, Store Listings & Screenshots on Google Play and App Store Connect</p>
</div>
""", unsafe_allow_html=True)

# Action Tabs
tab_iap, tab_listing, tab_screenshots, tab_help = st.tabs([
    "🛒 IAP Sync",
    "📝 Store Listing",
    "📸 Screenshots",
    "❓ Help",
])

# ──────────────────────────────────────────────────────────────────────── #
#  Tab 1: IAP Sync                                                        #
# ──────────────────────────────────────────────────────────────────────── #

with tab_iap:
    st.markdown("### In-App Purchase Sync")
    st.markdown("Read IAP definitions and create/update them on both stores.")

    # Preview data
    col_preview, col_actions = st.columns([3, 1])

    with col_preview:
        st.markdown("#### 📋 Data Preview")
        source_type = "excel" if data_source == "Excel File" else "gsheet"

        if data_source == "Excel File" and uploaded_file:
            df = load_iap_data("excel", file=uploaded_file)
        elif data_source == "Google Sheet" and sheet_id:
            df = load_iap_data("gsheet", sheet_id=sheet_id, worksheet=sheet_worksheet, sa_path=sa_json)
        else:
            df = None

        if df is not None:
            # Metrics
            m1, m2, m3 = st.columns(3)
            consumable_count = len(df[df["iap_type"] == "consumable"]) if "iap_type" in df.columns else 0
            non_consumable_count = len(df[df["iap_type"] == "non-consumable"]) if "iap_type" in df.columns else 0

            m1.metric("Total Products", len(df))
            m2.metric("Consumable", consumable_count)
            m3.metric("Non-Consumable", non_consumable_count)

            # Data table with styling
            st.dataframe(
                df,
                width="stretch",
                height=300,
                column_config={
                    "product_id": st.column_config.TextColumn("Product ID", width="large"),
                    "iap_type": st.column_config.TextColumn("Type", width="small"),
                    "base_price_usd": st.column_config.NumberColumn("Price ($)", format="$%.2f"),
                },
            )
        else:
            st.info("👆 Configure a data source in the sidebar to preview IAP data.")

    with col_actions:
        st.markdown("#### 🎮 Actions")

        platform_label = {
            "Both": "both", "Apple Only": "apple", "Google Only": "google"
        }[platform]

        st.markdown(f"**Platform:** `{platform}`")
        st.markdown(f"**Source:** `{data_source}`")

        st.markdown("---")

        # Dry Run button
        dry_run_clicked = st.button(
            "🔍 Dry Run",
            width="stretch",
            type="secondary",
            help="Preview what would happen without making API calls",
            disabled=not config_valid,
        )

        st.markdown("")

        # Live button with confirmation
        live_clicked = st.button(
            "🚀 Push to Stores",
            width="stretch",
            type="primary",
            help="Execute real API calls to create/update IAP",
            disabled=not config_valid,
        )

        if live_clicked:
            if "confirm_live" not in st.session_state:
                st.session_state.confirm_live = True
                st.rerun()

    # Execute
    if dry_run_clicked or (live_clicked and st.session_state.get("confirm_live")):
        is_dry_run = dry_run_clicked
        mode_label = "DRY-RUN" if is_dry_run else "LIVE"

        if not is_dry_run:
            st.warning("⚠️ **LIVE MODE** — This will make real API calls!")
            confirm = st.checkbox("I confirm I want to push to stores")
            if not confirm:
                st.stop()
            st.session_state.pop("confirm_live", None)

        st.markdown("---")
        st.markdown(f"### 📜 Execution Log — `{mode_label}`")

        log_handler = setup_log_capture()

        with st.spinner(f"Running IAP sync ({mode_label})..."):
            try:
                from auto_store_setup.config import Config
                from auto_store_setup.controller import MainController, Platform

                # Build config
                platform_map = {"both": Platform.BOTH, "apple": Platform.APPLE, "google": Platform.GOOGLE}

                config = Config(
                    google_play_package_name=gp_package or "com.studio.game",
                    google_service_account_json=Path(sa_json),
                    apple_key_id=apple_key_id or "",
                    apple_issuer_id=apple_issuer_id or "",
                    apple_private_key_path=Path(apple_p8_path),
                    apple_app_id=apple_app_id or "",
                    data_source="excel" if uploaded_file else "gsheet",
                    iap_data_file=Path("./iap_data.xlsx"),
                    google_sheet_id=sheet_id,
                    google_sheet_worksheet=sheet_worksheet,
                    dry_run=is_dry_run,
                )

                # Save uploaded file temporarily
                if uploaded_file:
                    temp_path = Path("./temp_iap_data.xlsx")
                    temp_path.write_bytes(uploaded_file.getvalue())
                    config = replace(config, iap_data_file=temp_path)

                controller = MainController(
                    config=config,
                    platform=platform_map[platform_label],
                )
                controller.run_iap()

                # Clean up
                if uploaded_file and Path("./temp_iap_data.xlsx").exists():
                    Path("./temp_iap_data.xlsx").unlink()

            except Exception as e:
                st.error(f"Error: {e}")

        # Display logs
        log_html = log_handler.get_html()
        if log_html:
            st.markdown(f'<div class="log-container">{log_html}</div>', unsafe_allow_html=True)

        # Results summary
        if log_handler.logs:
            success_count = sum(1 for l in log_handler.logs if "✅" in l["message"] and ("Google Play" in l["message"] or "App Store" in l["message"] or "Created" in l["message"] or "Updated" in l["message"]))
            error_count = sum(1 for l in log_handler.logs if "❌" in l["message"])

            r1, r2, r3 = st.columns(3)
            r1.metric("Total", len(df) if df is not None else 0)
            r2.metric("Succeeded", success_count, delta_color="normal")
            r3.metric("Failed", error_count, delta_color="inverse")


# ──────────────────────────────────────────────────────────────────────── #
#  Tab 2: Store Listing                                                   #
# ──────────────────────────────────────────────────────────────────────── #

with tab_listing:
    st.markdown("### Store Listing Sync")
    st.markdown("Update app name, description, keywords, and promo text across all locales.")

    st.markdown("#### Expected Google Sheet tab: `Store Listing`")

    example_df = pd.DataFrame({
        "field": ["app_name", "short_description", "full_description", "keywords", "promo_text"],
        "en-US": ["Water Go Puzzle", "Fun water puzzle game!", "Full description...", "puzzle,water,game", "New levels!"],
        "vi": ["Water Go - Xep Hinh", "Tro choi xep hinh nuoc!", "Mo ta day du...", "xep hinh,nuoc,game", "Co man moi!"],
    })
    st.dataframe(example_df, width="stretch", hide_index=True)

    col_l1, col_l2 = st.columns(2)
    with col_l1:
        listing_dry = st.button("🔍 Dry Run Listing", width="stretch", disabled=not config_valid)
    with col_l2:
        listing_live = st.button("🚀 Push Listing", width="stretch", type="primary", disabled=not config_valid)

    if listing_dry or listing_live:
        is_dry = listing_dry
        log_handler = setup_log_capture()

        with st.spinner(f"Running Store Listing sync ({'DRY-RUN' if is_dry else 'LIVE'})..."):
            try:
                from auto_store_setup.config import Config
                from auto_store_setup.controller import MainController, Platform

                platform_map = {"both": Platform.BOTH, "apple": Platform.APPLE, "google": Platform.GOOGLE}

                config = Config(
                    google_play_package_name=gp_package or "com.studio.game",
                    google_service_account_json=Path(sa_json),
                    apple_key_id=apple_key_id or "",
                    apple_issuer_id=apple_issuer_id or "",
                    apple_private_key_path=Path(apple_p8_path),
                    apple_app_id=apple_app_id or "",
                    data_source="excel" if uploaded_file else "gsheet",
                    iap_data_file=Path("./iap_data.xlsx"),
                    google_sheet_id=sheet_id,
                    google_sheet_worksheet=sheet_worksheet,
                    dry_run=is_dry,
                )

                controller = MainController(config=config, platform=platform_map[platform_label])
                controller.run_listing()
            except Exception as e:
                st.error(f"Error: {e}")

        log_html = log_handler.get_html()
        if log_html:
            st.markdown(f'<div class="log-container">{log_html}</div>', unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────── #
#  Tab 3: Screenshots                                                     #
# ──────────────────────────────────────────────────────────────────────── #

with tab_screenshots:
    st.markdown("### Screenshot Upload")
    st.markdown("Upload app screenshots organized by locale and device type.")

    st.markdown("#### Expected Google Sheet tab: `Screenshots`")

    example_ss = pd.DataFrame({
        "locale": ["en-US", "en-US", "vi", "en-US"],
        "device_type": ["phone_6.5", "phone_6.5", "phone_6.5", "tablet_12.9"],
        "display_order": [1, 2, 1, 1],
        "file_path": ["./screenshots/en/phone_01.png", "./screenshots/en/phone_02.png", "./screenshots/vi/phone_01.png", "./screenshots/en/tablet_01.png"],
    })
    st.dataframe(example_ss, width="stretch", hide_index=True)

    st.markdown("**Supported device types:**")
    device_cols = st.columns(5)
    devices = ["phone", "phone_5.5", "phone_6.5", "phone_6.7", "tablet", "tablet_7", "tablet_10", "tablet_12.9", "tv", "wear"]
    for i, dev in enumerate(devices):
        device_cols[i % 5].code(dev)

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        ss_dry = st.button("🔍 Dry Run Screenshots", width="stretch", disabled=not config_valid)
    with col_s2:
        ss_live = st.button("🚀 Upload Screenshots", width="stretch", type="primary", disabled=not config_valid)

    if ss_dry or ss_live:
        is_dry = ss_dry
        log_handler = setup_log_capture()

        with st.spinner(f"Running Screenshot upload ({'DRY-RUN' if is_dry else 'LIVE'})..."):
            try:
                from auto_store_setup.config import Config
                from auto_store_setup.controller import MainController, Platform

                platform_map = {"both": Platform.BOTH, "apple": Platform.APPLE, "google": Platform.GOOGLE}

                config = Config(
                    google_play_package_name=gp_package or "com.studio.game",
                    google_service_account_json=Path(sa_json),
                    apple_key_id=apple_key_id or "",
                    apple_issuer_id=apple_issuer_id or "",
                    apple_private_key_path=Path(apple_p8_path),
                    apple_app_id=apple_app_id or "",
                    data_source="excel" if uploaded_file else "gsheet",
                    iap_data_file=Path("./iap_data.xlsx"),
                    google_sheet_id=sheet_id,
                    google_sheet_worksheet=sheet_worksheet,
                    dry_run=is_dry,
                )

                controller = MainController(config=config, platform=platform_map[platform_label])
                controller.run_screenshots()
            except Exception as e:
                st.error(f"Error: {e}")

        log_html = log_handler.get_html()
        if log_html:
            st.markdown(f'<div class="log-container">{log_html}</div>', unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────── #
#  Tab 4: Help                                                            #
# ──────────────────────────────────────────────────────────────────────── #

with tab_help:
    st.markdown("### Getting Started")

    st.markdown("""
    #### 1. Prepare your Google Sheet

    Create a Google Sheet with **3 tabs**:

    | Tab Name | Purpose |
    |----------|---------|
    | `Sheet1` | IAP data (product_id, iap_type, price, names, descriptions) |
    | `Store Listing` | App metadata (name, description, keywords per locale) |
    | `Screenshots` | Screenshot manifest (locale, device, order, file path) |

    #### 2. Share with Service Account

    Share the Google Sheet with your service account email:
    ```
    your-sa-name@your-project.iam.gserviceaccount.com
    ```
    Find this email in `credentials/service_account.json` → `"client_email"` field.

    #### 3. Configure the sidebar

    Fill in:
    - **Google Sheet ID** from the URL
    - **Apple credentials** (Key ID, Issuer ID, .p8 path, App ID)
    - **Google Play package name**

    #### 4. Run!

    1. Click **🔍 Dry Run** first to preview changes
    2. When satisfied, click **🚀 Push to Stores**

    ---

    #### CLI Alternative

    You can also use the command line:
    ```bash
    python main.py iap --platform apple --dry-run
    python main.py listing --dry-run
    python main.py screenshots --dry-run
    ```

    #### Links

    - [GitHub Repository](https://github.com/tinycorn-studio/Automating-Store-Management)
    - [Google Cloud Console](https://console.cloud.google.com/)
    - [App Store Connect](https://appstoreconnect.apple.com/)
    - [Google Play Console](https://play.google.com/console)
    """)
