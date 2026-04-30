import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dotenv import load_dotenv
import os
import requests

load_dotenv()

# --- Config ---
st.set_page_config(page_title="INAPROC Dashboard", layout="wide")
JWT_TOKEN = os.getenv("INAPROC_JWT_TOKEN")

# --- Styling ---
st.markdown("""
    <style>
        .metric-card {
            background: linear-gradient(135deg, #1e3a5f, #2d6a9f);
            border-radius: 12px;
            padding: 20px 24px;
            color: white;
            margin-bottom: 8px;
        }
        .metric-card.green {
            background: linear-gradient(135deg, #1a4a2e, #2d9f5f);
        }
        .metric-card.orange {
            background: linear-gradient(135deg, #5f3a1e, #9f6a2d);
        }
        .metric-card.red {
            background: linear-gradient(135deg, #5f1e1e, #9f2d2d);
        }
        .metric-card.purple {
            background: linear-gradient(135deg, #3a1e5f, #6a2d9f);
        }
        .metric-label {
            font-size: 13px;
            opacity: 0.75;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .metric-value {
            font-size: 26px;
            font-weight: 700;
            margin-top: 4px;
        }
        .metric-sub {
            font-size: 12px;
            opacity: 0.6;
            margin-top: 2px;
        }
        .section-title {
            font-size: 18px;
            font-weight: 600;
            color: #1e3a5f;
            border-left: 4px solid #2d6a9f;
            padding-left: 10px;
            margin: 24px 0 12px 0;
        }
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

    def _fetch(self, endpoint: str, params: dict):
        response = requests.get(
            f"{self.base_url}{endpoint}",
            headers=self.headers, params=params, timeout=30
        )
        response.raise_for_status()
        raw = response.json()
        if isinstance(raw, list):
            return pd.DataFrame(raw)
        elif isinstance(raw, dict):
            key = next((k for k in ["data", "result", "results", "items"] if k in raw), None)
            return pd.DataFrame(raw[key]) if key else pd.DataFrame([raw])
        return pd.DataFrame()

    def get_penyedia(self, kode_klpd, tahun):
        return self._fetch("/legacy/rup/paket-penyedia-terumumkan", {"kode_klpd": kode_klpd, "tahun": tahun})

    def get_swakelola(self, kode_klpd, tahun):
        return self._fetch("/legacy/rup/paket-swakelola-terumumkan", {"kode_klpd": kode_klpd, "tahun": tahun})

    def get_epurchasing(self, kode_klpd, tahun):
        return self._fetch("/legacy/ekatalog/paket-e-purchasing", {"kode_klpd": kode_klpd, "tahun": tahun})

    def get_tender(self, kode_klpd, tahun):
        return self._fetch("/legacy/tender/pengumuman", {"kode_klpd": kode_klpd, "tahun": tahun})

    def get_nontender(self, kode_klpd, tahun):
        return self._fetch("/legacy/tender/non-tender-pengumuman", {"kode_klpd": kode_klpd, "tahun": tahun})

# --- Helpers ---
def fmt_rupiah(val):
    if pd.isna(val): return "Rp 0"
    return f"Rp {val:,.0f}".replace(",", ".")

def to_rupiah_short(val):
    try:
        val = float(val)
    except:
        return "Rp 0"
    if val >= 1_000_000_000_000:
        return f"Rp {val/1_000_000_000_000:.2f} T"
    elif val >= 1_000_000_000:
        return f"Rp {val/1_000_000_000:.2f} M"
    elif val >= 1_000_000:
        return f"Rp {val/1_000_000:.2f} Jt"
    return fmt_rupiah(val)

def safe_sum(df, col):
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce").fillna(0).sum()
    return 0

def safe_numeric(df, col):
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df

@st.cache_data(ttl=300)
def load_all(kode_klpd, tahun, token):
    client = InaprocAPIClient(token)
    df_p  = client.get_penyedia(kode_klpd, tahun)
    df_s  = client.get_swakelola(kode_klpd, tahun)
    df_ep = client.get_epurchasing(kode_klpd, tahun)
    df_t  = client.get_tender(kode_klpd, tahun)
    df_nt = client.get_nontender(kode_klpd, tahun)
    return df_p, df_s, df_ep, df_t, df_nt

# --- Sidebar ---
st.sidebar.title("📊 INAPROC Dashboard")
st.sidebar.markdown("---")
kode_klpd = st.sidebar.text_input("Kode KLPD", value="D199")
tahun = st.sidebar.number_input("Tahun", value=2026, min_value=2000, max_value=2100, step=1)
if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()

if st.sidebar.button("📋 Lihat Rincian Paket →", use_container_width=True):
    st.switch_page("pages/📋_Rincian_Paket.py")

st.title("📊 Dashboard RUP INAPROC")
st.caption(f"KLPD: **{kode_klpd}** | Tahun: **{tahun}**")

if not JWT_TOKEN:
    st.error("❌ Token tidak ditemukan! Pastikan INAPROC_JWT_TOKEN ada di file .env")
    st.stop()

# --- Load Data ---
try:
    with st.spinner("Mengambil data dari semua sumber..."):
        df_p, df_s, df_ep, df_t, df_nt = load_all(kode_klpd, tahun, JWT_TOKEN)

    # Normalize pagu columns
    for df in [df_p, df_s, df_ep, df_t, df_nt]:
        for col in ["pagu", "nilai_kontrak", "hps", "total"]:
            safe_numeric(df, col)

    # Totals
    pagu_p  = safe_sum(df_p, "pagu")
    pagu_s  = safe_sum(df_s, "pagu")
    pagu_ep = safe_sum(df_ep, "total")
    pagu_t  = safe_sum(df_t, "pagu")     # tender usually uses hps
    pagu_nt = safe_sum(df_nt, "pagu")
    total_pagu = pagu_ep + pagu_t + pagu_nt

    # ── KPI Cards Row 1: RUP ─────────────────────────────────────────────
    st.markdown('<div class="section-title">📋 RUP (Rencana Umum Pengadaan)</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-label">Total Pagu RUP</div>
            <div class="metric-value">{to_rupiah_short(pagu_p + pagu_s)}</div>
            <div class="metric-sub">Penyedia + Swakelola</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-label">Total Paket RUP</div>
            <div class="metric-value">{len(df_p) + len(df_s):,}</div>
            <div class="metric-sub">{len(df_p)} Penyedia · {len(df_s)} Swakelola</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-label">Pagu Penyedia</div>
            <div class="metric-value">{to_rupiah_short(pagu_p)}</div>
            <div class="metric-sub">{len(df_p)} paket</div>
        </div>""", unsafe_allow_html=True)
    with c4:
        st.markdown(f"""<div class="metric-card">
            <div class="metric-label">Pagu Swakelola</div>
            <div class="metric-value">{to_rupiah_short(pagu_s)}</div>
            <div class="metric-sub">{len(df_s)} paket</div>
        </div>""", unsafe_allow_html=True)

    # ── KPI Cards Row 2: Tender, Non-Tender, E-Purchasing ────────────────
    st.markdown('<div class="section-title">🛒 Realisasi Pengadaan</div>', unsafe_allow_html=True)
    d1, d2, d3, d4 = st.columns(4)

    with d1:
        st.markdown(f"""<div class="metric-card green">
            <div class="metric-label">E-Purchasing</div>
            <div class="metric-value">{to_rupiah_short(pagu_ep)}</div>
            <div class="metric-sub">{len(df_ep)} paket</div>
        </div>""", unsafe_allow_html=True)
    with d2:
        st.markdown(f"""<div class="metric-card orange">
            <div class="metric-label">Tender - Pengumuman (Pagu)</div>
            <div class="metric-value">{to_rupiah_short(pagu_t)}</div>
            <div class="metric-sub">{len(df_t)} paket</div>
        </div>""", unsafe_allow_html=True)
    with d3:
        st.markdown(f"""<div class="metric-card purple">
            <div class="metric-label">Non-Tender - Pengumuman (Pagu)</div>
            <div class="metric-value">{to_rupiah_short(pagu_nt)}</div>
            <div class="metric-sub">{len(df_nt)} paket</div>
        </div>""", unsafe_allow_html=True)
    # with d4:
    #     st.markdown(f"""<div class="metric-card red">
    #         <div class="metric-label">Total Semua Sumber</div>
    #         <div class="metric-value">{to_rupiah_short(total_pagu)}</div>
    #         <div class="metric-sub">5 sumber data</div>
    #     </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # ── Section: Komposisi Pagu Penyedia/Swakelola ─────────────────────────────
    st.markdown('<div class="section-title">📌 Komposisi Pagu & Paket RUP Penyedia/Swakelola</div>', unsafe_allow_html=True)
    pie1, pie2 = st.columns(2)

    SOURCES      = ["Penyedia", "Swakelola"]
    PAGU_VALUES  = [pagu_p, pagu_s]
    PAKET_VALUES = [len(df_p), len(df_s)]
    COLORS       = ["#2d6a9f", "#e07b39"]

    with pie1:
        fig_pagu = px.pie(
            names=SOURCES, values=PAGU_VALUES,
            title="Proporsi Pagu per Sumber",
            color_discrete_sequence=COLORS, hole=0.45
        )
        fig_pagu.update_traces(textinfo="percent+label")
        fig_pagu.update_layout(title_x=0.5, margin=dict(t=50, b=10))
        st.plotly_chart(fig_pagu, use_container_width=True)

    with pie2:
        fig_paket = px.pie(
            names=SOURCES, values=PAKET_VALUES,
            title="Proporsi Jumlah Paket per Sumber",
            color_discrete_sequence=COLORS, hole=0.45
        )
        fig_paket.update_traces(textinfo="percent+label")
        fig_paket.update_layout(title_x=0.5, margin=dict(t=50, b=10))
        st.plotly_chart(fig_paket, use_container_width=True)

    # ── Summary bar: all sources side by side ────────────────────────────
    df_summary = pd.DataFrame({
        "Sumber": SOURCES,
        "Total Pagu": PAGU_VALUES,
        "Jumlah Paket": PAKET_VALUES
    })
    df_summary["Label Pagu"] = df_summary["Total Pagu"].apply(to_rupiah_short)

    fig_all = px.bar(
        df_summary, x="Sumber", y="Total Pagu",
        text="Label Pagu", color="Sumber",
        color_discrete_sequence=COLORS,
        title="Perbandingan Total Pagu per Sumber"
    )
    fig_all.update_traces(textposition="outside")
    fig_all.update_layout(
        title_x=0.5, showlegend=False,
        yaxis=dict(showticklabels=False, showgrid=False),
        margin=dict(t=50, b=10)
    )
    st.plotly_chart(fig_all, use_container_width=True)

    st.markdown("---")

    # ── Section: Komposisi Pagu Semua Sumber ─────────────────────────────
    st.markdown('<div class="section-title">📌 Komposisi Pagu & Paket Semua Sumber</div>', unsafe_allow_html=True)
    pie1, pie2 = st.columns(2)

    SOURCES      = ["E-Purchasing", "Tender", "Non-Tender"]
    PAGU_VALUES  = [pagu_ep, pagu_t, pagu_nt]
    PAKET_VALUES = [len(df_ep), len(df_t), len(df_nt)]
    COLORS       = ["#2d9f5f", "#9f2d9f", "#9f2d2d"]

    with pie1:
        fig_pagu = px.pie(
            names=SOURCES, values=PAGU_VALUES,
            title="Proporsi Pagu per Sumber",
            color_discrete_sequence=COLORS, hole=0.45
        )
        fig_pagu.update_traces(textinfo="percent+label")
        fig_pagu.update_layout(title_x=0.5, margin=dict(t=50, b=10))
        st.plotly_chart(fig_pagu, use_container_width=True)

    with pie2:
        fig_paket = px.pie(
            names=SOURCES, values=PAKET_VALUES,
            title="Proporsi Jumlah Paket per Sumber",
            color_discrete_sequence=COLORS, hole=0.45
        )
        fig_paket.update_traces(textinfo="percent+label")
        fig_paket.update_layout(title_x=0.5, margin=dict(t=50, b=10))
        st.plotly_chart(fig_paket, use_container_width=True)

    # ── Summary bar: all sources side by side ────────────────────────────
    df_summary = pd.DataFrame({
        "Sumber": SOURCES,
        "Total Pagu": PAGU_VALUES,
        "Jumlah Paket": PAKET_VALUES
    })
    df_summary["Label Pagu"] = df_summary["Total Pagu"].apply(to_rupiah_short)

    fig_all = px.bar(
        df_summary, x="Sumber", y="Total Pagu",
        text="Label Pagu", color="Sumber",
        color_discrete_sequence=COLORS,
        title="Perbandingan Total Pagu per Sumber"
    )
    fig_all.update_traces(textposition="outside")
    fig_all.update_layout(
        title_x=0.5, showlegend=False,
        yaxis=dict(showticklabels=False, showgrid=False),
        margin=dict(t=50, b=10)
    )
    st.plotly_chart(fig_all, use_container_width=True)

    st.markdown("---")

    # ── Section: Top Satker RUP ───────────────────────────────────────────
    st.markdown('<div class="section-title">🏆 Ranking Satker – RUP</div>', unsafe_allow_html=True)
    TOP_N = 10
    rank1, rank2 = st.columns(2)

    for col, df_src, label, color in [
        (rank1, df_p, "Penyedia", "#2d6a9f"),
        (rank2, df_s, "Swakelola", "#e07b39")
    ]:
        with col:
            if "nama_satker" in df_src.columns and "pagu" in df_src.columns:
                top = (
                    df_src.groupby("nama_satker")["pagu"].sum()
                    .reset_index().sort_values("pagu", ascending=False).head(TOP_N)
                )
                top["label"] = top["pagu"].apply(to_rupiah_short)
                top["satker_short"] = top["nama_satker"].str[:35]

                fig = go.Figure(go.Bar(
                    x=top["pagu"], y=top["satker_short"], orientation="h",
                    marker_color=color, text=top["label"],
                    textposition="outside",
                    hovertemplate="%{y}<br>%{text}<extra></extra>"
                ))
                fig.update_layout(
                    title=f"Top {TOP_N} Satker – {label}", title_x=0.5,
                    xaxis=dict(showticklabels=False, showgrid=False),
                    yaxis=dict(autorange="reversed"),
                    margin=dict(l=10, r=80, t=50, b=10), height=380
                )
                st.plotly_chart(fig, use_container_width=True)

                tbl = top[["nama_satker", "pagu"]].copy()
                tbl["pagu"] = tbl["pagu"].apply(fmt_rupiah)
                tbl.columns = ["Nama Satker", "Total Pagu"]
                tbl.index = range(1, len(tbl) + 1)
                st.dataframe(tbl, use_container_width=True)

    st.markdown("---")

    # ── Section: Top Satker – E-Purchasing, Tender, Non-Tender ───────────
    st.markdown('<div class="section-title">🏆 Ranking Satker – Realisasi Pengadaan</div>', unsafe_allow_html=True)

    ep_col, t_col, nt_col = st.columns(3)

    for col, df_src, label, color, pagu_col in [
        (ep_col, df_ep, "E-Purchasing", "#2d9f5f", "total"),
        (t_col,  df_t,  "Tender",       "#9f2d9f", "pagu"),
        (nt_col, df_nt, "Non-Tender",   "#9f2d2d", "pagu"),
    ]:
        with col:
            satker_col = next((c for c in ["nama_satker", "nama_klpd", "satker"] if c in df_src.columns), None)
            if satker_col and pagu_col in df_src.columns:
                top = (
                    df_src.groupby(satker_col)[pagu_col].sum()
                    .reset_index().sort_values(pagu_col, ascending=False).head(TOP_N)
                )
                top["label"] = top[pagu_col].apply(to_rupiah_short)
                top["satker_short"] = top[satker_col].str[:30]

                fig = go.Figure(go.Bar(
                    x=top[pagu_col], y=top["satker_short"], orientation="h",
                    marker_color=color, text=top["label"],
                    textposition="outside",
                    hovertemplate="%{y}<br>%{text}<extra></extra>"
                ))
                fig.update_layout(
                    title=f"Top {TOP_N} – {label}", title_x=0.5,
                    xaxis=dict(showticklabels=False, showgrid=False),
                    yaxis=dict(autorange="reversed"),
                    margin=dict(l=10, r=80, t=50, b=10), height=360
                )
                st.plotly_chart(fig, use_container_width=True)

                tbl = top[[satker_col, pagu_col]].copy()
                tbl[pagu_col] = tbl[pagu_col].apply(fmt_rupiah)
                tbl.columns = ["Nama Satker", "Total Nilai"]
                tbl.index = range(1, len(tbl) + 1)
                st.dataframe(tbl, use_container_width=True)
            else:
                st.info(f"Kolom satker/pagu tidak ditemukan di data {label}")

    st.markdown("---")

    # ── Section: Jenis & Metode Pengadaan (RUP only) ─────────────────────
    st.markdown('<div class="section-title">📂 Jenis & Metode Pengadaan (RUP)</div>', unsafe_allow_html=True)
    df_combined = pd.concat([df_p, df_s], ignore_index=True)

    tab1, tab2 = st.tabs(["🗂 Jenis Pengadaan", "⚙️ Metode Pengadaan"])

    for tab, col_name, title in [
        (tab1, "jenis_pengadaan", "Jenis Pengadaan"),
        (tab2, "metode_pengadaan", "Metode Pengadaan")
    ]:
        with tab:
            if col_name in df_combined.columns:
                agg = (
                    df_combined.groupby(col_name)
                    .agg(jumlah_paket=(col_name, "count"), total_pagu=("pagu", "sum"))
                    .reset_index().sort_values("total_pagu", ascending=False)
                )
                agg["total_pagu_fmt"]   = agg["total_pagu"].apply(fmt_rupiah)
                agg["total_pagu_short"] = agg["total_pagu"].apply(to_rupiah_short)

                ch1, ch2 = st.columns(2)
                with ch1:
                    fig_pie = px.pie(
                        agg, names=col_name, values="jumlah_paket",
                        title=f"Jumlah Paket per {title}", hole=0.4,
                        color_discrete_sequence=px.colors.qualitative.Set2
                    )
                    fig_pie.update_traces(textinfo="percent+label")
                    fig_pie.update_layout(title_x=0.5, margin=dict(t=50, b=10))
                    st.plotly_chart(fig_pie, use_container_width=True)

                with ch2:
                    fig_bar = px.bar(
                        agg, x=col_name, y="total_pagu",
                        title=f"Total Pagu per {title}",
                        text="total_pagu_short", color=col_name,
                        color_discrete_sequence=px.colors.qualitative.Set2
                    )
                    fig_bar.update_traces(textposition="outside")
                    fig_bar.update_layout(
                        title_x=0.5, showlegend=False,
                        yaxis=dict(showticklabels=False, showgrid=False),
                        margin=dict(t=50, b=10)
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)

                tbl = agg[[col_name, "jumlah_paket", "total_pagu_fmt"]].copy()
                tbl.columns = [title, "Jumlah Paket", "Total Pagu"]
                tbl.index = range(1, len(tbl) + 1)
                st.dataframe(tbl, use_container_width=True)
            else:
                st.info(f"Kolom `{col_name}` tidak ditemukan di data.")

    # ── Section: Tender Status Breakdown ─────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="section-title">📊 Status Tender & Non-Tender</div>', unsafe_allow_html=True)
    t1, t2 = st.columns(2)

    for col, df_src, label, color_seq in [
        (t1, df_t,  "Tender",     px.colors.qualitative.Pastel),
        (t2, df_nt, "Non-Tender", px.colors.qualitative.Pastel1),
    ]:
        with col:
            status_col = next((c for c in ["status_tender", "status_nontender", "status"] if c in df_src.columns), None)
            if status_col:
                status_agg = df_src[status_col].value_counts().reset_index()
                status_agg.columns = ["Status", "Jumlah"]
                fig_s = px.pie(
                    status_agg, names="Status", values="Jumlah",
                    title=f"Status {label}", hole=0.4,
                    color_discrete_sequence=color_seq
                )
                fig_s.update_traces(textinfo="percent+label")
                fig_s.update_layout(title_x=0.5, margin=dict(t=50, b=10))
                st.plotly_chart(fig_s, use_container_width=True)
                st.dataframe(status_agg, use_container_width=True)
            else:
                st.info(f"Kolom status tidak ditemukan di data {label}.")

except requests.exceptions.HTTPError as e:
    st.error(f"❌ API Error {e.response.status_code}: {e.response.text}")
except Exception as e:
    st.error(f"❌ Error: {e}")