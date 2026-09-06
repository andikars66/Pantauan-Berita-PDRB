from __future__ import annotations

import logging
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from src.config_loader import (
    AppConfig,
    ConfigError,
    load_config,
    update_hierarchical_selection,
)
from src.date_utils import available_quarters, quarter_bounds, today_wita, year_options
from src.exporter import build_main_excel, build_raw_excel
from src.pipeline import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
PROJECT_ROOT = Path(__file__).resolve().parent
QUARTER_LABELS = {1: "Jan–Mar", 2: "Apr–Jun", 3: "Jul–Sep", 4: "Okt–Des"}


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at 12% 0%, rgba(255, 127, 0, .14), transparent 34rem),
                radial-gradient(circle at 92% 18%, rgba(245, 158, 11, .09), transparent 30rem),
                linear-gradient(145deg, #fff8f1 0%, #ffffff 52%, #fffaf5 100%);
        }
        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stToolbar"] { right: 1rem; }
        .block-container {
            max-width: 1120px;
            padding-top: 2.1rem;
            padding-bottom: 4rem;
        }
        .hero-card {
            background: linear-gradient(110deg, #fff0df, rgba(255, 255, 255, .94));
            border: 1px solid rgba(255, 127, 0, .28);
            border-radius: 22px;
            padding: 1.75rem 1.9rem;
            margin-bottom: 1.15rem;
            box-shadow: 0 20px 55px rgba(120, 65, 10, .12);
        }
        .hero-row { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
        .hero-copy { display: flex; align-items: center; gap: 1rem; }
        .hero-icon {
            width: 54px; height: 54px; display: grid; place-items: center;
            border-radius: 15px; font-size: 1.65rem;
            background: linear-gradient(145deg, #ff9a33, #ff7f00);
            border: 1px solid rgba(217, 95, 0, .22);
            box-shadow: 0 8px 20px rgba(255, 127, 0, .20);
        }
        .hero-card h1 { margin: 0; color: #2d1b0e; font-size: 1.9rem; line-height: 1.2; }
        .hero-card p { margin: .45rem 0 0; color: #76583f; font-size: .94rem; }
        .status-badge {
            white-space: nowrap; color: #157347; border: 1px solid rgba(21, 115, 71, .22);
            background: #edf9f2; border-radius: 999px;
            padding: .42rem .72rem; font-size: .72rem; font-weight: 700; letter-spacing: .04em;
        }
        .eyebrow {
            color: #c45f00; font-weight: 800; font-size: .73rem;
            letter-spacing: .12em; margin-bottom: .35rem;
        }
        .period-note {
            color: #76583f; font-size: .84rem; padding-top: .15rem;
        }
        .section-heading {
            display: flex; align-items: center; gap: .6rem; margin: .35rem 0 .75rem;
        }
        .section-heading h3 { margin: 0; font-size: 1.05rem; color: #352318; }
        .section-heading span {
            font-size: .72rem; color: #8a674d; border: 1px solid rgba(138, 103, 77, .22);
            border-radius: 999px; padding: .18rem .5rem;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-color: rgba(255, 127, 0, .20) !important;
            background: rgba(255, 255, 255, .88);
            border-radius: 18px;
            box-shadow: 0 16px 42px rgba(120, 65, 10, .09);
        }
        div[data-testid="stMetric"] {
            min-height: 108px;
            padding: 1rem 1.05rem;
            border: 1px solid rgba(255, 127, 0, .22);
            border-radius: 16px;
            background: linear-gradient(145deg, #ffffff, #fff7ed);
            box-shadow: 0 10px 26px rgba(120, 65, 10, .08);
        }
        div[data-testid="stMetricLabel"] { color: #7c5b45; }
        div[data-testid="stMetricValue"] { color: #2d1b0e; }
        div[data-baseweb="select"] > div,
        div[data-testid="stPopover"] > button {
            background: rgba(255, 255, 255, .94) !important;
            border-color: rgba(255, 127, 0, .30) !important;
            border-radius: 11px !important;
        }
        .stButton > button, .stDownloadButton > button {
            width: auto !important;
            min-height: 2.25rem;
            padding: .42rem .9rem;
            border-radius: 10px;
            font-weight: 700;
            background: linear-gradient(90deg, #FF7F00, #F59E0B) !important;
            color: #ffffff !important;
            box-shadow: 0 10px 26px rgba(255, 127, 0, .28);
        }
        .st-key-run_button button {
            width: 100% !important;
            min-height: 2.65rem;
            border: 0;
            background: linear-gradient(90deg, #FF7F00, #F59E0B) !important;
            color: #ffffff !important;
            box-shadow: 0 10px 26px rgba(255, 127, 0, .28);
        }
        .st-key-run_button button:hover { filter: brightness(1.08); transform: translateY(-1px); }
        div[data-testid="stCheckbox"] { padding: .08rem 0; }
        div[data-testid="stDataFrame"] { border-radius: 14px; overflow: hidden; }
        div[data-testid="stTabs"] button { font-weight: 700; }
        hr { border-color: rgba(138, 103, 77, .16); }
        @media (max-width: 760px) {
            .block-container { padding: 1rem .9rem 3rem; }
            .hero-card { padding: 1.25rem; }
            .hero-row { align-items: flex-start; }
            .hero-card h1 { font-size: 1.45rem; }
            .hero-icon { display: none; }
            .status-badge { font-size: .62rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def get_config() -> AppConfig:
    return load_config(PROJECT_ROOT / "config")


def get_serper_keys() -> list[str]:
    value = None
    try:
        value = st.secrets.get("SERPER_API_KEYS")
    except (FileNotFoundError, KeyError):
        value = None
    if value is None:
        value = os.environ.get("SERPER_API_KEYS", "")
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [str(item).strip() for item in value if str(item).strip()]


def taxonomy_label(code: str, config: AppConfig) -> str:
    row = config.taxonomy.set_index("taxonomy_code").loc[code]
    display_code = code.split(".", 1)[1]
    return f'{"　" * int(row["level"])}{display_code}. {row["label"]}'


def _taxonomy_widget_key(dimension: str, code: str) -> str:
    return f"taxonomy_{dimension}_{code}"


def set_dimension_selection(dimension: str, config: AppConfig, select_all: bool) -> None:
    options = config.taxonomy.loc[
        (config.taxonomy["dimension"] == dimension) & config.taxonomy["selectable"],
        "taxonomy_code",
    ].tolist()
    selected = options if select_all else []
    st.session_state[f"selection_{dimension}"] = selected
    for code in options:
        st.session_state[_taxonomy_widget_key(dimension, code)] = select_all


def toggle_taxonomy_node(dimension: str, code: str, config: AppConfig) -> None:
    selection_key = f"selection_{dimension}"
    checked = bool(st.session_state[_taxonomy_widget_key(dimension, code)])
    selected = update_hierarchical_selection(
        st.session_state.get(selection_key, []), code, checked, config.taxonomy,
    )
    st.session_state[selection_key] = selected
    selected_set = set(selected)
    options = config.taxonomy.loc[
        (config.taxonomy["dimension"] == dimension) & config.taxonomy["selectable"],
        "taxonomy_code",
    ]
    for option in options:
        st.session_state[_taxonomy_widget_key(dimension, option)] = option in selected_set


def render_taxonomy_dropdown(dimension: str, title: str, icon: str, config: AppConfig) -> list[str]:
    selection_key = f"selection_{dimension}"
    st.session_state.setdefault(selection_key, [])
    selected = st.session_state[selection_key]
    options = config.taxonomy.loc[
        (config.taxonomy["dimension"] == dimension) & config.taxonomy["selectable"],
        "taxonomy_code",
    ].tolist()
    st.markdown(f"**{icon} {title}**")
    popover_label = f"{len(selected)} dipilih" if selected else "Pilih kategori"
    with st.popover(popover_label, use_container_width=True):
        st.caption("Centang parent untuk memilih seluruh turunannya.")
        action_left, action_right, _ = st.columns([1, 1, 1.2])
        action_left.button(
            "✓ Semua", key=f"all_{dimension}",
            on_click=set_dimension_selection, args=(dimension, config, True),
        )
        action_right.button(
            "× Bersihkan", key=f"clear_{dimension}",
            on_click=set_dimension_selection, args=(dimension, config, False),
        )
        st.divider()
        selected_set = set(st.session_state[selection_key])
        with st.container(height=410, border=False):
            for code in options:
                widget_key = _taxonomy_widget_key(dimension, code)
                if widget_key not in st.session_state:
                    st.session_state[widget_key] = code in selected_set
                st.checkbox(
                    taxonomy_label(code, config),
                    key=widget_key,
                    on_change=toggle_taxonomy_node,
                    args=(dimension, code, config),
                )
    return st.session_state[selection_key]


def _display_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(
            columns=["Sektor/Subsektor", "Judul Berita", "Tanggal", "Pengaruh", "Tautan", "Sumber"],
        )
    prepared = frame.copy()
    prepared["sector_display"] = prepared.apply(
        lambda row: f'{row["taxonomy_code"].split(".", 1)[1]}. {row["label"]}', axis=1,
    )
    return prepared.rename(columns={
        "sector_display": "Sektor/Subsektor", "title": "Judul Berita", "date": "Tanggal",
        "impact": "Pengaruh", "url": "Tautan", "source": "Sumber",
    })[["Sektor/Subsektor", "Judul Berita", "Tanggal", "Pengaruh", "Tautan", "Sumber"]]


def render_dimension_results(result: dict, dimension: str, title: str, icon: str) -> None:
    frame = result["selected_df"]
    frame = frame[frame["dimension"] == dimension].copy()
    st.markdown(
        f'<div class="section-heading"><h3>{icon} {title}</h3><span>{len(frame)} baris hasil</span></div>',
        unsafe_allow_html=True,
    )
    filter_left, filter_right = st.columns(2)
    sector_codes = frame["taxonomy_code"].drop_duplicates().tolist() if not frame.empty else []
    sector_labels = {
        row.taxonomy_code: f'{row.taxonomy_code.split(".", 1)[1]}. {row.label}'
        for row in frame[["taxonomy_code", "label"]].drop_duplicates().itertuples()
    }
    sectors = filter_left.multiselect(
        "Sektor/subsektor", sector_codes, key=f"filter_sector_{dimension}",
        format_func=lambda code: sector_labels.get(code, code),
        placeholder="Semua sektor",
    )
    impacts = filter_right.multiselect(
        "Pengaruh", ["Positif", "Negatif", "Netral"], key=f"filter_impact_{dimension}",
        placeholder="Semua pengaruh",
    )
    if sectors:
        frame = frame[frame["taxonomy_code"].isin(sectors)]
    if impacts:
        frame = frame[frame["impact"].isin(impacts)]
    display = _display_frame(frame)
    if display.empty:
        st.info(f"Belum ada hasil {title.lower()} untuk pilihan dan filter ini.")
    else:
        st.dataframe(
            display, hide_index=True, use_container_width=True,
            column_config={"Tautan": st.column_config.LinkColumn("Tautan", display_text="Buka ↗")},
        )

    dimension_name = "Lapangan Usaha" if dimension == "LU" else "Pengeluaran"
    summary = result["taxonomy_summary"]
    zero_rows = summary[(summary["Dimensi"] == dimension_name) & (summary["Jumlah Berita"] == 0)]
    if not zero_rows.empty:
        with st.expander(f"{len(zero_rows)} sektor terpilih belum memiliki berita", expanded=False):
            st.caption(
                " · ".join(
                    f'{row["Kode"]}. {row["Sektor/Subsektor"]}' for _, row in zero_rows.iterrows()
                )
            )


def render_summary_cards(result: dict) -> None:
    st.markdown('<div class="eyebrow">RINGKASAN HASIL</div>', unsafe_allow_html=True)
    icons = {
        "Raw Records": "🗞️", "Raw Records Terklasifikasi": "🏷️",
        "Raw Records Tidak Terklasifikasi": "📭", "Classification Rows Terpilih": "📋",
        "Positif": "📈", "Negatif": "📉", "Netral": "➖",
    }
    metric_names = list(result["summary"])
    for group in (metric_names[:4], metric_names[4:]):
        columns = st.columns(len(group))
        for column, name in zip(columns, group):
            column.metric(f'{icons[name]} {name}', result["summary"][name])
    st.caption("Raw Records menghitung hasil scraping; baris klasifikasi menghitung pasangan artikel × taxonomy.")


def render_results(result: dict) -> None:
    status = result["metadata"]["status"]
    if status == "Selesai":
        st.success("Proses selesai")
    elif status == "Selesai dengan peringatan":
        st.warning("Proses selesai dengan peringatan. Periksa tab Status Sumber.")
    else:
        st.error("Proses gagal. Periksa tab Status Sumber.")

    render_summary_cards(result)
    main_tab, raw_tab, status_tab = st.tabs(["📋 Hasil Utama", "🗃️ Raw Result", "🩺 Status Sumber"])
    with main_tab:
        render_dimension_results(result, "LU", "Lapangan Usaha", "🏭")
        st.divider()
        render_dimension_results(result, "EXP", "Pengeluaran", "🛒")
        st.download_button(
            "⬇️ Download Hasil Utama",
            build_main_excel(result),
            file_name=f'berita_pdrb_{result["metadata"]["year"]}_T{result["metadata"]["quarter"]}.xlsx',
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    with raw_tab:
        raw = result["raw_df"].rename(columns={
            "classifications": "Sektor/Subsektor", "title": "Judul Berita", "date": "Tanggal",
            "impacts": "Pengaruh", "url": "Tautan", "source": "Sumber",
        })
        visible = raw[["Sektor/Subsektor", "Judul Berita", "Tanggal", "Pengaruh", "Tautan", "Sumber"]]
        st.dataframe(
            visible, hide_index=True, use_container_width=True,
            column_config={"Tautan": st.column_config.LinkColumn("Tautan", display_text="Buka ↗")},
        )
        st.download_button(
            "⬇️ Download Raw Result",
            build_raw_excel(result),
            file_name=f'raw_berita_pdrb_{result["metadata"]["year"]}_T{result["metadata"]["quarter"]}.xlsx',
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    with status_tab:
        st.dataframe(result["source_statuses"], hide_index=True, use_container_width=True)
        diagnostics = result["query_diagnostics"]
        st.caption(
            f'Serper: {diagnostics["planned_queries"]} query direncanakan · '
            f'{diagnostics["requests"]} request · {diagnostics["results"]} hasil · '
            f'{diagnostics["retries"]} retry · {diagnostics["key_failovers"]} failover key.'
        )


def app() -> None:
    st.set_page_config(page_title="Pantauan Berita PDRB Lombok Tengah", page_icon="📰", layout="centered")
    inject_styles()
    try:
        config = get_config()
    except ConfigError as exc:
        st.error(f"Konfigurasi tidak valid: {exc}")
        st.stop()

    key_status = "SERPER READY" if get_serper_keys() else "PORTAL MODE"
    st.markdown(
        f"""
        <div class="hero-card">
          <div class="hero-row">
            <div class="hero-copy">
              <div class="hero-icon">📰</div>
              <div>
                <h1>Pantauan Berita PDRB</h1>
                <p>BPS Kabupaten Lombok Tengah · Klasifikasi Lapangan Usaha &amp; Pengeluaran</p>
              </div>
            </div>
            <div class="status-badge">● {key_status}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    today = today_wita()
    period_options = [
        (year, quarter)
        for year in year_options(today)
        for quarter in available_quarters(year, today)
    ]
    with st.container(border=True, key="parameter_panel"):
        st.markdown('<div class="eyebrow">🎯 PARAMETER PENCARIAN</div>', unsafe_allow_html=True)
        period_column, lu_column, exp_column = st.columns([.82, 1.1, 1.1])
        with period_column:
            st.markdown("**📅 Periode**")
            year, quarter = st.selectbox(
                "Periode", period_options, index=len(period_options) - 1,
                format_func=lambda value: f"T{value[1]} {value[0]} ({QUARTER_LABELS[value[1]]})",
                label_visibility="collapsed",
            )
        with lu_column:
            lu = render_taxonomy_dropdown("LU", "Lapangan Usaha", "🏭", config)
        with exp_column:
            exp = render_taxonomy_dropdown("EXP", "Pengeluaran", "🛒", config)

        start_date, end_date = quarter_bounds(year, quarter, today)
        selected = lu + exp
        st.markdown(
            f'<div class="period-note">{start_date:%d %b %Y} – {end_date:%d %b %Y} &nbsp;·&nbsp; '
            f'{len(selected)} kategori dipilih</div>',
            unsafe_allow_html=True,
        )
        _, run_column, _ = st.columns([1, .52, 1])
        with run_column:
            started = st.button(
                "🔎 Mulai Pencarian", type="primary", disabled=not selected,
                use_container_width=True, key="run_button",
            )

    if started:
        st.session_state.pop("run_result", None)
        for key in ("filter_sector_LU", "filter_impact_LU", "filter_sector_EXP", "filter_impact_EXP"):
            st.session_state.pop(key, None)
        progress_bar = st.progress(0)
        status_text = st.empty()

        def progress(value: int, label: str) -> None:
            progress_bar.progress(value)
            status_text.caption(label)

        try:
            st.session_state["run_result"] = run_pipeline(
                year, quarter, selected, config, get_serper_keys(), today, progress,
            )
        except Exception:
            logging.getLogger(__name__).exception("Fatal pipeline error")
            st.error("Proses gagal karena kesalahan internal. Periksa konfigurasi atau log aplikasi.")
        finally:
            status_text.empty()
            progress_bar.empty()

    if "run_result" in st.session_state:
        render_results(st.session_state["run_result"])
    else:
        st.info("Pilih periode dan minimal satu kategori, lalu mulai pencarian.", icon="💡")


if __name__ == "__main__":
    app()
