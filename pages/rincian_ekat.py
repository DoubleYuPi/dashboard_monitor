import streamlit as st
import pandas as pd
from dotenv import load_dotenv
import os
import requests

load_dotenv()

# --- Config ---
DEFAULT_COLUMNS = [
    "nama_satker", "rup_desc", "total", "total_qty",
    "status", "order_date"
]
PAGE_SIZE_OPTIONS = [10, 25, 50, 100]

JWT_TOKEN = os.getenv("INAPROC_JWT_TOKEN")

# --- API Client ---
class InaprocAPIClient:
    def __init__(self, jwt_token: str):
        self.base_url = "https://data.inaproc.id/api"
        self.headers = {
            "Authorization": f"Bearer inprc52aaf394f25f40fa8394b9e105393df3",
            "User-Agent": "PostmanRuntime/7.51.1",
            "Connection": "keep-alive"
        }

    def get_epurchasing(self, kode_klpd: str, tahun: int):
        response = requests.get(
            f"{self.base_url}/legacy/ekatalog/paket-e-purchasing",
            headers=self.headers,
            params={"kode_klpd": kode_klpd, "tahun": tahun},
            timeout=30
        )
        response.raise_for_status()
        return response.json()

def parse_response(raw):
    if isinstance(raw, list):
        return pd.DataFrame(raw)
    elif isinstance(raw, dict):
        key = next((k for k in ["data", "result", "results", "items"] if k in raw), None)
        return pd.DataFrame(raw[key]) if key else pd.DataFrame([raw])
    return pd.DataFrame()

@st.cache_data(ttl=60)
def fetch_data(kode_klpd, tahun, token):
    return InaprocAPIClient(token).get_epurchasing(kode_klpd, tahun)

# --- Reusable Table ---
def show_table(df):
    if df.empty:
        st.warning("Tidak ada data.")
        return

    all_columns = df.columns.tolist()
    default_visible = [c for c in DEFAULT_COLUMNS if c in all_columns]
    extra_columns = [c for c in all_columns if c not in DEFAULT_COLUMNS]

    with st.expander("🔽 Tampilkan Kolom Tambahan", expanded=False):
        extra_selected = st.multiselect(
            "Pilih kolom tambahan yang ingin ditampilkan:",
            options=extra_columns,
            default=[]
        )

    visible_columns = default_visible + extra_selected
    df_display = df[visible_columns].copy()

    # Format any money columns as Rupiah — update column names as needed
    for money_col in ["pagu", "nilai_kontrak", "harga_satuan"]:
        if money_col in df_display.columns:
            df_display[money_col] = df_display[money_col].apply(
                lambda x: f"Rp {float(x):,.0f}".replace(",", ".") if pd.notna(x) else "-"
            )

    # --- Filter & Page Size Row ---
    col_satker, col_size, _ = st.columns([2, 1, 2])

    with col_satker:
        if "nama_satker" in df_display.columns:
            satker_list = ["Semua"] + sorted(df["nama_satker"].dropna().unique().tolist())
            selected_satker = st.selectbox("🏢 Nama Satker", satker_list)
        else:
            selected_satker = "Semua"

    with col_size:
        page_size = st.selectbox("Baris per halaman", PAGE_SIZE_OPTIONS, index=1)

    if selected_satker != "Semua":
        df_display = df_display[df_display["nama_satker"] == selected_satker]

    total_rows = len(df_display)
    total_pages = max(1, -(-total_rows // page_size))

    if "ep_current_page" not in st.session_state:
        st.session_state.ep_current_page = 1
    if st.session_state.ep_current_page > total_pages:
        st.session_state.ep_current_page = 1

    start_idx = (st.session_state.ep_current_page - 1) * page_size
    end_idx = min(start_idx + page_size, total_rows)

    st.caption(f"Menampilkan baris {start_idx + 1}–{end_idx} dari {total_rows} total")
    st.dataframe(df_display.iloc[start_idx:end_idx], use_container_width=True)

    # --- Pagination Buttons ---
    MAX_BUTTONS = 7
    half = MAX_BUTTONS // 2
    start_page = max(1, st.session_state.ep_current_page - half)
    end_page = min(total_pages, start_page + MAX_BUTTONS - 1)
    if end_page - start_page < MAX_BUTTONS - 1:
        start_page = max(1, end_page - MAX_BUTTONS + 1)

    btn_cols = st.columns(MAX_BUTTONS + 2)

    with btn_cols[0]:
        if st.button("‹", disabled=st.session_state.ep_current_page == 1):
            st.session_state.ep_current_page -= 1
            st.rerun()

    for i, page_num in enumerate(range(start_page, end_page + 1)):
        with btn_cols[i + 1]:
            is_current = page_num == st.session_state.ep_current_page
            label = f"**{page_num}**" if is_current else str(page_num)
            if st.button(label, key=f"ep_page_{page_num}", disabled=is_current):
                st.session_state.ep_current_page = page_num
                st.rerun()

    with btn_cols[MAX_BUTTONS + 1]:
        if st.button("›", disabled=st.session_state.ep_current_page == total_pages):
            st.session_state.ep_current_page += 1
            st.rerun()

    # --- Download ---
    csv = df.to_csv(index=False)
    st.download_button("⬇️ Download CSV (semua kolom)", csv, "ekat_epurchasing.csv", "text/csv")

# --- Page ---
st.title("🛒 Rincian Paket E-Purchasing")

if st.button("← Kembali ke Dashboard"):
    st.switch_page("home.py")

if not JWT_TOKEN:
    st.error("❌ Token tidak ditemukan! Pastikan INAPROC_JWT_TOKEN ada di file .env")
    st.stop()

st.sidebar.header("🔧 Filter")
kode_klpd = st.sidebar.text_input("Kode KLPD", value="D199")
tahun = st.sidebar.number_input("Tahun", value=2026, min_value=2000, max_value=2100, step=1)

if st.sidebar.button("🔄 Fetch Data"):
    st.cache_data.clear()

try:
    raw = fetch_data(kode_klpd, tahun, JWT_TOKEN)
    df = parse_response(raw)

    # 👇 Uncomment this to inspect column names returned by the API
    # st.write("Kolom tersedia:", df.columns.tolist())

    st.success(f"✅ {len(df)} paket e-purchasing ditemukan untuk KLPD {kode_klpd} tahun {tahun}")
    show_table(df)

except requests.exceptions.HTTPError as e:
    st.error(f"❌ API Error {e.response.status_code}: {e.response.text}")
except Exception as e:
    st.error(f"❌ Error: {e}")