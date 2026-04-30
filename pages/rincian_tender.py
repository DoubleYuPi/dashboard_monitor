import streamlit as st
import pandas as pd
from dotenv import load_dotenv
import os
import requests

load_dotenv()

# --- Config ---
DEFAULT_COLUMNS = [
    "nama_satker", "nama_paket", "pagu", "hps",
    "mtd_pemilihan", "jenis_pengadaan",
    "tgl_pengumuman_tender", "status_tender"
]
PAGE_SIZE_OPTIONS = [10, 25, 50, 100]

st.set_page_config(page_title="Rincian Tender", layout="wide")

JWT_TOKEN = os.getenv("INAPROC_JWT_TOKEN")

# --- API Client ---
class InaprocAPIClient:
    def __init__(self, jwt_token: str):
        self.base_url = "https://data.inaproc.id/api"
        self.headers = {
            "Authorization": f"Bearer {jwt_token}",
            "User-Agent": "PostmanRuntime/7.51.1",
            "Connection": "keep-alive"
        }

    def get_tender(self, kode_klpd: str, tahun: int):
        response = requests.get(
            f"{self.base_url}/legacy/tender/pengumuman",
            headers=self.headers,
            params={"kode_klpd": kode_klpd, "tahun": tahun},
            timeout=30
        )
        response.raise_for_status()
        return response.json()

# --- Helpers ---
def parse_response(raw):
    if isinstance(raw, list):
        return pd.DataFrame(raw)
    elif isinstance(raw, dict):
        key = next((k for k in ["data", "result", "results", "items"] if k in raw), None)
        return pd.DataFrame(raw[key]) if key else pd.DataFrame([raw])
    return pd.DataFrame()

@st.cache_data(ttl=60)
def fetch_data(kode_klpd, tahun, token):
    return InaprocAPIClient(token).get_tender(kode_klpd, tahun)

# --- Sidebar ---
st.sidebar.title("📋 INAPROC Monitor")
st.sidebar.markdown("---")
st.sidebar.header("🔧 Filter")
kode_klpd = st.sidebar.text_input("Kode KLPD", value="D199")
tahun = st.sidebar.number_input("Tahun", value=2026, min_value=2000, max_value=2100, step=1)

if st.sidebar.button("🔄 Fetch Data"):
    st.cache_data.clear()

# --- Reusable Table ---
def show_table(df, page_key):
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
            default=[],
            key=f"extra_cols_{page_key}"
        )

    visible_columns = default_visible + extra_selected
    df_display = df[visible_columns].copy()

    if "pagu" in df_display.columns:
        df_display["pagu"] = df_display["pagu"].apply(
            lambda x: f"Rp {float(x):,.0f}".replace(",", ".") if pd.notna(x) else "-"
        )
    if "hps" in df_display.columns:
        df_display["hps"] = df_display["hps"].apply(
            lambda x: f"Rp {float(x):,.0f}".replace(",", ".") if pd.notna(x) else "-"
        )

    # --- Filter Row ---
    col_satker, col_size, col_metode, col_jenis, col_status, _ = st.columns([2, 1, 1, 1, 1, 1])

    with col_satker:
        if "nama_satker" in df_display.columns:
            satker_list = ["Semua"] + sorted(df["nama_satker"].dropna().unique().tolist())
            selected_satker = st.selectbox("🏢 Nama Satker", satker_list, key=f"satker_{page_key}")
        else:
            selected_satker = "Semua"

    with col_metode:
        if "metode_pengadaan" in df_display.columns:
            metode_list = ["Semua"] + sorted(df["metode_pengadaan"].dropna().unique().tolist())
            selected_metode = st.selectbox("Metode Pengadaan", metode_list, key=f"metode_{page_key}")
        else:
            selected_metode = "Semua"

    with col_jenis:
        if "jenis_pengadaan" in df_display.columns:
            jenis_list = ["Semua"] + sorted(df["jenis_pengadaan"].dropna().unique().tolist())
            selected_jenis = st.selectbox("Jenis Pengadaan", jenis_list, key=f"jenis_{page_key}")
        else:
            selected_jenis = "Semua"

    with col_status:
        if "status_tender" in df_display.columns:
            status_list = ["Semua"] + sorted(df["status_tender"].dropna().unique().tolist())
            selected_status = st.selectbox("Status Tender", status_list, key=f"status_{page_key}")
        else:
            selected_status = "Semua"

    with col_size:
        page_size = st.selectbox("Baris per halaman", PAGE_SIZE_OPTIONS, index=1, key=f"pagesize_{page_key}")

    if selected_satker != "Semua":
        df_display = df_display[df_display["nama_satker"] == selected_satker]
    if selected_metode != "Semua":
        df_display = df_display[df_display["metode_pengadaan"] == selected_metode]
    if selected_jenis != "Semua":
        df_display = df_display[df_display["jenis_pengadaan"] == selected_jenis]
    if selected_status != "Semua":
        df_display = df_display[df_display["status_tender"] == selected_status]

    total_rows = len(df_display)
    total_pages = max(1, -(-total_rows // page_size))

    page_state_key = f"current_page_{page_key}"
    if page_state_key not in st.session_state:
        st.session_state[page_state_key] = 1
    if st.session_state[page_state_key] > total_pages:
        st.session_state[page_state_key] = 1

    start_idx = (st.session_state[page_state_key] - 1) * page_size
    end_idx = min(start_idx + page_size, total_rows)

    st.caption(f"Menampilkan baris {start_idx + 1}–{end_idx} dari {total_rows} total")
    st.dataframe(df_display.iloc[start_idx:end_idx], use_container_width=True)

    # --- Pagination ---
    MAX_BUTTONS = 7
    half = MAX_BUTTONS // 2
    start_page = max(1, st.session_state[page_state_key] - half)
    end_page = min(total_pages, start_page + MAX_BUTTONS - 1)
    if end_page - start_page < MAX_BUTTONS - 1:
        start_page = max(1, end_page - MAX_BUTTONS + 1)

    btn_cols = st.columns(MAX_BUTTONS + 2)

    with btn_cols[0]:
        if st.button("‹", key=f"prev_{page_key}", disabled=st.session_state[page_state_key] == 1):
            st.session_state[page_state_key] -= 1
            st.rerun()

    for i, page_num in enumerate(range(start_page, end_page + 1)):
        with btn_cols[i + 1]:
            is_current = page_num == st.session_state[page_state_key]
            label = f"**{page_num}**" if is_current else str(page_num)
            if st.button(label, key=f"page_{page_key}_{page_num}", disabled=is_current):
                st.session_state[page_state_key] = page_num
                st.rerun()

    with btn_cols[MAX_BUTTONS + 1]:
        if st.button("›", key=f"next_{page_key}", disabled=st.session_state[page_state_key] == total_pages):
            st.session_state[page_state_key] += 1
            st.rerun()

    # --- Download ---
    csv = df.to_csv(index=False)
    st.download_button(
        "⬇️ Download CSV (semua kolom)",
        csv, f"tender_{kode_klpd}_{tahun}.csv", "text/csv",
        key=f"download_{page_key}"
    )

# --- Token Check ---
if not JWT_TOKEN:
    st.error("❌ Token tidak ditemukan! Pastikan INAPROC_JWT_TOKEN ada di file .env")
    st.stop()

# --- Main Page ---
st.title("📄 Rincian Paket Tender")
st.caption(f"KLPD: **{kode_klpd}** | Tahun: **{tahun}**")

if st.button("← Kembali ke Dashboard"):
    st.switch_page("home.py")

try:
    raw = fetch_data(kode_klpd, tahun, JWT_TOKEN)
    df = parse_response(raw)

    # 👇 Uncomment to inspect columns returned by API
    # st.write("Kolom tersedia:", df.columns.tolist())

    st.success(f"✅ {len(df)} paket tender ditemukan untuk KLPD {kode_klpd} tahun {tahun}")
    show_table(df, page_key="tender")

except requests.exceptions.HTTPError as e:
    st.error(f"❌ API Error {e.response.status_code}: {e.response.text}")
except Exception as e:
    st.error(f"❌ Error: {e}")