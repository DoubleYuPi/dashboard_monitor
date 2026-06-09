import streamlit as st
import pandas as pd
from dotenv import load_dotenv
import os
import requests

load_dotenv()

# --- Config ---
st.set_page_config(page_title="Monitoring Status Paket", layout="wide")
JWT_TOKEN = os.getenv("INAPROC_JWT_TOKEN")

PAGE_SIZE_OPTIONS = [10, 25, 50, 100]

# Status normalization maps
STATUS_SELESAI   = {"selesai", "completed", "payment_outside_system", "finish", "done"}
STATUS_BERLANGSUNG = {"berlangsung", "on_process", "on_addendum", "proses", "aktif", "running"}

# --- Styling ---
st.markdown("""
    <style>
        .metric-card {
            border-radius: 12px; padding: 16px 20px;
            color: white; margin-bottom: 8px;
        }
        .metric-card.blue   { background: linear-gradient(135deg, #1e3a5f, #2d6a9f); }
        .metric-card.green  { background: linear-gradient(135deg, #1a4a2e, #2d9f5f); }
        .metric-card.yellow { background: linear-gradient(135deg, #5f4a1a, #b8860b); }
        .metric-card.gray   { background: linear-gradient(135deg, #3a3a3a, #6b6b6b); }
        .metric-card.red    { background: linear-gradient(135deg, #5f1e1e, #9f2d2d); }
        .metric-label { font-size: 12px; opacity: 0.75; text-transform: uppercase; letter-spacing: 1px; }
        .metric-value { font-size: 24px; font-weight: 700; margin-top: 4px; }
        .metric-sub   { font-size: 11px; opacity: 0.6; margin-top: 2px; }
        .section-title {
            font-size: 17px; font-weight: 600; color: #1e3a5f;
            border-left: 4px solid #2d6a9f;
            padding-left: 10px; margin: 20px 0 10px 0;
        }
        .legend-box {
            display: flex; gap: 16px; flex-wrap: wrap;
            padding: 10px 14px; background: #f8f9fa;
            border-radius: 8px; margin-bottom: 12px;
            font-size: 13px;
        }
        .legend-item { display: flex; align-items: center; gap: 6px; }
        .legend-dot  { width: 12px; height: 12px; border-radius: 50%; display: inline-block; }
    </style>
""", unsafe_allow_html=True)

# --- API Client ---
class InaprocAPIClient:
    def __init__(self, jwt_token: str):
        self.base_url = "https://data.inaproc.id/api"
        self.headers = {
            "Authorization": f"Bearer {jwt_token}",
            "User-Agent": "PostmanRuntime/7.51.1",
            "Connection": "keep-alive"
        }

    def _fetch(self, endpoint, params):
        r = requests.get(f"{self.base_url}{endpoint}", headers=self.headers, params=params, timeout=30)
        r.raise_for_status()
        raw = r.json()
        if isinstance(raw, list):
            return pd.DataFrame(raw)
        elif isinstance(raw, dict):
            key = next((k for k in ["data", "result", "results", "items"] if k in raw), None)
            return pd.DataFrame(raw[key]) if key else pd.DataFrame([raw])
        return pd.DataFrame()

    def get_penyedia(self, kode_klpd, tahun):
        return self._fetch("/legacy/rup/paket-penyedia-terumumkan", {"kode_klpd": kode_klpd, "tahun": tahun})

    def get_tender_selesai(self, kode_klpd, tahun):
        return self._fetch("/legacy/tender/tender-selesai", {"kode_klpd": kode_klpd, "tahun": tahun})

    def get_nontender_selesai(self, kode_klpd, tahun):
        return self._fetch("/legacy/tender/non-tender-selesai", {"kode_klpd": kode_klpd, "tahun": tahun})

    def get_epurchasing(self, kode_klpd, tahun):
        return self._fetch("/legacy/ekatalog/paket-e-purchasing", {"kode_klpd": kode_klpd, "tahun": tahun})

# --- Helpers ---
def fmt_rupiah(val):
    try:
        v = float(val)
        return f"Rp {v:,.0f}".replace(",", ".")
    except:
        return "-"

def normalize_status(status_raw):
    """Normalize raw status string to: selesai / berlangsung / unknown"""
    if pd.isna(status_raw) or str(status_raw).strip() == "":
        return "unknown"
    s = str(status_raw).strip().lower()
    if s in STATUS_SELESAI:
        return "selesai"
    if s in STATUS_BERLANGSUNG:
        return "berlangsung"
    return s  # keep original if doesn't match known patterns

def classify_row(row):
    """
    Returns (display_status, color_class, sumber) for a penyedia row.
    Priority: Tender > Non-Tender > E-Katalog > Belum Ada Data
    """
    # --- Tender ---
    if pd.notna(row.get("status_tender")):
        norm = normalize_status(row["status_tender"])
        sumber = "Tender"
        if norm == "selesai":
            return row["status_tender"], "selesai", sumber
        if norm == "berlangsung":
            return row["status_tender"], "berlangsung", sumber
        return row["status_tender"], "other", sumber

    # --- Non-Tender ---
    if pd.notna(row.get("status_nontender")):
        norm = normalize_status(row["status_nontender"])
        sumber = "Non-Tender"
        has_kontrak = pd.notna(row.get("nilai_kontrak_nt")) and float(row.get("nilai_kontrak_nt") or 0) > 0
        if norm in ("selesai") and not has_kontrak:
            return row["status_nontender"], "warning", sumber   # yellow: no nilai_kontrak
        if norm == "selesai":
            return row["status_nontender"], "selesai", sumber
        if norm == "berlangsung":
            return row["status_nontender"], "berlangsung", sumber
        return row["status_nontender"], "other", sumber

    # --- E-Katalog ---
    if pd.notna(row.get("status_ekatalog")):
        norm = normalize_status(row["status_ekatalog"])
        sumber = "E-Katalog"
        if norm == "selesai":
            return row["status_ekatalog"], "selesai", sumber
        if norm == "berlangsung":
            return row["status_ekatalog"], "berlangsung", sumber
        return row["status_ekatalog"], "other", sumber

    return "Belum Ada Data", "none", "-"

def row_color(color_class):
    color_map = {
        "selesai":     "background-color: #d4edda; color: #155724;",   # green
        "berlangsung": "background-color: #cce5ff; color: #004085;",   # blue
        "warning":     "background-color: #fff3cd; color: #856404;",   # yellow
        "other":       "background-color: #f0f0f0; color: #333;",      # light gray
        "none":        "",
    }
    return color_map.get(color_class, "")

@st.cache_data(ttl=120)
def load_data(kode_klpd, tahun, token):
    client = InaprocAPIClient(token)
    df_p   = client.get_penyedia(kode_klpd, tahun)
    df_t   = client.get_tender_selesai(kode_klpd, tahun)
    df_nt  = client.get_nontender_selesai(kode_klpd, tahun)
    df_ep  = client.get_epurchasing(kode_klpd, tahun)
    return df_p, df_t, df_nt, df_ep

def normalize_kd_rup(df, col="kd_rup"):
    """Cast kd_rup to string and explode semicolon-separated values into multiple rows."""
    if col not in df.columns:
        return df
    df = df.copy()
    df[col] = df[col].astype(str).str.strip()
    # Explode rows where kd_rup contains "63142237;65741481" → two separate rows
    df[col] = df[col].str.split(";")
    df = df.explode(col)
    df[col] = df[col].str.strip()
    return df

def merge_status(df_p, df_t, df_nt, df_ep):
    df = df_p.copy()
    df["kd_rup"] = df["kd_rup"].astype(str).str.strip()  # normalize base table

    # ── Merge Tender ──────────────────────────────────────────────────────
    if not df_t.empty and "kd_rup" in df_t.columns:
        tender_filter = df_t.copy()
        if "status_tender" in tender_filter.columns:
            tender_filter = tender_filter[
                tender_filter["status_tender"].apply(
                    lambda x: normalize_status(x) in ("selesai", "berlangsung")
                )
            ]
        tender_filter = normalize_kd_rup(tender_filter)
        cols_t = ["kd_rup", "status_tender"] + (
            ["nilai_kontrak"] if "nilai_kontrak" in tender_filter.columns else []
        )
        tender_sub = tender_filter[cols_t].drop_duplicates("kd_rup")
        tender_sub = tender_sub.rename(columns={"nilai_kontrak": "nilai_kontrak_t"})
        df = df.merge(tender_sub, on="kd_rup", how="left")

    # ── Merge Non-Tender ──────────────────────────────────────────────────
    if not df_nt.empty and "kd_rup" in df_nt.columns:
        nt_filter = df_nt.copy()
        if "status_nontender" in nt_filter.columns:
            nt_filter = nt_filter[
                nt_filter["status_nontender"].apply(
                    lambda x: normalize_status(x) in ("selesai", "berlangsung")
                )
            ]
        nt_filter = normalize_kd_rup(nt_filter)
        cols_nt = ["kd_rup", "status_nontender"] + (
            ["nilai_kontrak"] if "nilai_kontrak" in nt_filter.columns else []
        )
        nt_sub = nt_filter[cols_nt].drop_duplicates("kd_rup")
        nt_sub = nt_sub.rename(columns={"nilai_kontrak": "nilai_kontrak_nt"})
        df = df.merge(nt_sub, on="kd_rup", how="left")

    # ── Merge E-Katalog ───────────────────────────────────────────────────
    if not df_ep.empty:
        rup_col = next((c for c in ["rup_code", "kd_rup"] if c in df_ep.columns), None)
        if rup_col and "status" in df_ep.columns:
            ep_filter = normalize_kd_rup(df_ep.copy(), col=rup_col)
            ep_sub = ep_filter[[rup_col, "status"]].drop_duplicates(rup_col)
            ep_sub = ep_sub.rename(columns={rup_col: "kd_rup", "status": "status_ekatalog"})
            ep_sub["kd_rup"] = ep_sub["kd_rup"].astype(str).str.strip()
            df = df.merge(ep_sub, on="kd_rup", how="left")

    return df

# --- Sidebar ---
st.sidebar.title("🔍 Monitoring Status")
st.sidebar.markdown("---")
st.sidebar.header("🔧 Filter")
kode_klpd = st.sidebar.text_input("Kode KLPD", value="D199")
tahun     = st.sidebar.number_input("Tahun", value=2026, min_value=2000, max_value=2100, step=1)

if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()

if st.sidebar.button("🏠 Kembali ke Dashboard", use_container_width=True):
    st.switch_page("🏠_Home.py")

# --- Main ---
st.title("🔍 Monitoring Status Paket Penyedia")
st.caption(f"KLPD: **{kode_klpd}** | Tahun: **{tahun}**")

if not JWT_TOKEN:
    st.error("❌ Token tidak ditemukan!")
    st.stop()

try:
    with st.spinner("Mengambil dan menggabungkan data..."):
        df_p, df_t, df_nt, df_ep = load_data(kode_klpd, tahun, JWT_TOKEN)

    if df_p.empty:
        st.warning("Tidak ada data paket penyedia.")
        st.stop()

    df = merge_status(df_p, df_t, df_nt, df_ep)

    # --- Classify each row ---
    classifications = df.apply(classify_row, axis=1)
    df["Status Paket"]  = classifications.apply(lambda x: x[0])
    df["_color_class"]  = classifications.apply(lambda x: x[1])
    df["Sumber Status"] = classifications.apply(lambda x: x[2])

    # ── KPI Cards ─────────────────────────────────────────────────────────
    total       = len(df)
    n_selesai   = (df["_color_class"] == "selesai").sum()
    n_berlangsung = (df["_color_class"] == "berlangsung").sum()
    n_warning   = (df["_color_class"] == "warning").sum()
    n_other     = (df["_color_class"] == "other").sum()
    n_none      = (df["_color_class"] == "none").sum()

    pct = lambda n: f"{n/total*100:.1f}%" if total > 0 else "0%"

    c1, c2, c3, c4, c5 = st.columns(5)
    cards = [
        (c1, "blue",   "Total Paket",              total,         "100%"),
        (c2, "green",  "✅ Selesai",               n_selesai,     pct(n_selesai)),
        (c3, "blue",   "🔄 Berlangsung",           n_berlangsung, pct(n_berlangsung)),
        (c4, "yellow", "⚠️ Tanpa Nilai Kontrak",   n_warning,     pct(n_warning)),
        (c5, "gray",   "❌ Belum Ada Data",        n_none,        pct(n_none)),
    ]
    for col, cls, label, val, sub in cards:
        with col:
            st.markdown(f"""<div class="metric-card {cls}">
                <div class="metric-label">{label}</div>
                <div class="metric-value">{val:,}</div>
                <div class="metric-sub">{sub} dari total paket</div>
            </div>""", unsafe_allow_html=True)

    # ── Progress Bar ──────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="section-title">📈 Progress Realisasi</div>', unsafe_allow_html=True)

    col_prog, col_info = st.columns([3, 1])
    with col_prog:
        pct_selesai     = n_selesai / total if total > 0 else 0
        pct_berlangsung = n_berlangsung / total if total > 0 else 0
        pct_warning_v   = n_warning / total if total > 0 else 0

        st.markdown(f"**Selesai:** {pct(n_selesai)}")
        st.progress(pct_selesai)
        st.markdown(f"**Berlangsung:** {pct(n_berlangsung)}")
        st.progress(pct_berlangsung)
        st.markdown(f"**Tanpa Nilai Kontrak:** {pct(n_warning)}")
        st.progress(pct_warning_v)

    with col_info:
        sumber_counts = df[df["Sumber Status"] != "-"]["Sumber Status"].value_counts()
        st.markdown("**Paket Teridentifikasi per Sumber:**")
        for sumber, count in sumber_counts.items():
            st.markdown(f"- **{sumber}**: {count} paket")

    # ── Filters ───────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="section-title">📋 Tabel Status Paket</div>', unsafe_allow_html=True)

    # Legend
    st.markdown("""
        <div class="legend-box">
            <div class="legend-item"><span class="legend-dot" style="background:#28a745"></span> Selesai</div>
            <div class="legend-item"><span class="legend-dot" style="background:#007bff"></span> Berlangsung</div>
            <div class="legend-item"><span class="legend-dot" style="background:#ffc107"></span> Selesai/Berlangsung (Tanpa Nilai Kontrak)</div>
            <div class="legend-item"><span class="legend-dot" style="background:#aaa"></span> Status Lainnya</div>
            <div class="legend-item"><span class="legend-dot" style="background:#fff;border:1px solid #ccc"></span> Belum Ada Data</div>
        </div>
    """, unsafe_allow_html=True)

    # Filter row
    f1, f2, f3, f4, _ = st.columns([2, 1, 1, 1, 1])

    with f1:
        satker_list = ["Semua"] + sorted(df["nama_satker"].dropna().unique().tolist()) if "nama_satker" in df.columns else ["Semua"]
        sel_satker = st.selectbox("🏢 Nama Satker", satker_list, key="mon_satker")

    with f2:
        status_opts = ["Semua", "✅ Selesai", "🔄 Berlangsung", "⚠️ Tanpa Nilai Kontrak", "❌ Belum Ada Data", "Lainnya"]
        sel_status = st.selectbox("Status", status_opts, key="mon_status")

    with f3:
        sumber_opts = ["Semua", "Tender", "Non-Tender", "E-Katalog", "-"]
        sel_sumber = st.selectbox("Sumber", sumber_opts, key="mon_sumber")

    with f4:
        page_size = st.selectbox("Baris per halaman", PAGE_SIZE_OPTIONS, index=1, key="mon_pagesize")

    # Apply filters
    df_view = df.copy()

    if sel_satker != "Semua" and "nama_satker" in df_view.columns:
        df_view = df_view[df_view["nama_satker"] == sel_satker]

    status_class_map = {
        "✅ Selesai":              "selesai",
        "🔄 Berlangsung":          "berlangsung",
        "⚠️ Tanpa Nilai Kontrak":  "warning",
        "❌ Belum Ada Data":       "none",
        "Lainnya":                 "other",
    }
    if sel_status != "Semua":
        df_view = df_view[df_view["_color_class"] == status_class_map[sel_status]]

    if sel_sumber != "Semua":
        df_view = df_view[df_view["Sumber Status"] == sel_sumber]

    # ── Build display columns ──────────────────────────────────────────────
    display_cols = []
    for c in ["nama_satker", "nama_paket", "pagu", "kd_rup",
              "jenis_pengadaan", "metode_pengadaan"]:
        if c in df_view.columns:
            display_cols.append(c)

    # Add status columns if they exist
    for c in ["status_tender", "status_nontender", "status_ekatalog",
              "nilai_kontrak_t", "nilai_kontrak_nt"]:
        if c in df_view.columns:
            display_cols.append(c)

    display_cols += ["Status Paket", "Sumber Status"]

    df_show = df_view[display_cols].copy()

    # Format rupiah
    for money_col in ["pagu", "nilai_kontrak_t", "nilai_kontrak_nt"]:
        if money_col in df_show.columns:
            df_show[money_col] = df_show[money_col].apply(
                lambda x: fmt_rupiah(x) if pd.notna(x) else "-"
            )

    # ── Pagination ────────────────────────────────────────────────────────
    total_rows  = len(df_show)
    total_pages = max(1, -(-total_rows // page_size))

    if "mon_page" not in st.session_state:
        st.session_state.mon_page = 1
    if st.session_state.mon_page > total_pages:
        st.session_state.mon_page = 1

    start_idx = (st.session_state.mon_page - 1) * page_size
    end_idx   = min(start_idx + page_size, total_rows)

    st.caption(f"Menampilkan baris {start_idx + 1}–{end_idx} dari {total_rows} total ({len(df)} paket penyedia)")

    # ── Styled Dataframe ──────────────────────────────────────────────────
    df_page   = df_show.iloc[start_idx:end_idx].copy()
    color_page = df_view["_color_class"].iloc[start_idx:end_idx].tolist()

    def style_rows(row):
        idx     = row.name
        loc     = df_page.index.get_loc(idx)
        c_class = color_page[loc] if loc < len(color_page) else "none"
        css     = row_color(c_class)
        return [css] * len(row)

    styled = df_page.style.apply(style_rows, axis=1)
    st.dataframe(styled, use_container_width=True, height=450)

    # ── Pagination Buttons ────────────────────────────────────────────────
    MAX_BUTTONS = 7
    half        = MAX_BUTTONS // 2
    start_page  = max(1, st.session_state.mon_page - half)
    end_page    = min(total_pages, start_page + MAX_BUTTONS - 1)
    if end_page - start_page < MAX_BUTTONS - 1:
        start_page = max(1, end_page - MAX_BUTTONS + 1)

    btn_cols = st.columns(MAX_BUTTONS + 2)
    with btn_cols[0]:
        if st.button("‹", key="mon_prev", disabled=st.session_state.mon_page == 1):
            st.session_state.mon_page -= 1
            st.rerun()

    for i, page_num in enumerate(range(start_page, end_page + 1)):
        with btn_cols[i + 1]:
            is_cur = page_num == st.session_state.mon_page
            label  = f"**{page_num}**" if is_cur else str(page_num)
            if st.button(label, key=f"mon_p_{page_num}", disabled=is_cur):
                st.session_state.mon_page = page_num
                st.rerun()

    with btn_cols[MAX_BUTTONS + 1]:
        if st.button("›", key="mon_next", disabled=st.session_state.mon_page == total_pages):
            st.session_state.mon_page += 1
            st.rerun()

    # ── Download ──────────────────────────────────────────────────────────
    st.markdown("---")
    dl1, dl2 = st.columns(2)
    with dl1:
        csv_filtered = df_show.to_csv(index=False)
        st.download_button(
            "⬇️ Download Data Terfilter (CSV)",
            csv_filtered, f"monitoring_{kode_klpd}_{tahun}_filtered.csv", "text/csv",
            key="dl_filtered"
        )
    with dl2:
        export_all = df[display_cols].copy()
        for money_col in ["pagu", "nilai_kontrak_t", "nilai_kontrak_nt"]:
            if money_col in export_all.columns:
                export_all[money_col] = export_all[money_col].apply(
                    lambda x: fmt_rupiah(x) if pd.notna(x) else "-"
                )
        csv_all = export_all.to_csv(index=False)
        st.download_button(
            "⬇️ Download Semua Data (CSV)",
            csv_all, f"monitoring_{kode_klpd}_{tahun}_all.csv", "text/csv",
            key="dl_all"
        )

except requests.exceptions.HTTPError as e:
    st.error(f"❌ API Error {e.response.status_code}: {e.response.text}")
except Exception as e:
    st.error(f"❌ Error: {e}")