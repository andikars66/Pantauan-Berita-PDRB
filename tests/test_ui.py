from pathlib import Path
from datetime import date, datetime

import pandas as pd
from streamlit.testing.v1 import AppTest


def test_compact_period_and_hierarchical_taxonomy_ui():
    app = AppTest.from_file(Path(__file__).parents[1] / "app.py").run(timeout=30)
    assert not app.exception
    assert len(app.selectbox) == 1
    assert len(app.checkbox) == 91
    assert app.button[-1].label == "🔎 Mulai Pencarian"
    assert app.button[-1].disabled

    app.checkbox[1].check()
    app.run(timeout=30)
    assert not app.exception
    assert [checkbox.value for checkbox in app.checkbox[1:7]] == [True] * 6
    assert not app.button[-1].disabled


def test_result_ui_has_cards_tabs_and_split_dimension_tables():
    selected = pd.DataFrame([
        {
            "dimension": "LU", "taxonomy_code": "LU.F", "label": "Konstruksi",
            "title": "Pembangunan dimulai", "date": date(2026, 8, 1),
            "impact": "Positif", "url": "https://example.com/lu", "source": "Fixture",
        },
        {
            "dimension": "EXP", "taxonomy_code": "EXP.4.a", "label": "Bangunan",
            "title": "Investasi bangunan", "date": date(2026, 8, 2),
            "impact": "Netral", "url": "https://example.com/exp", "source": "Fixture",
        },
    ])
    raw = pd.DataFrame([
        {
            "classifications": "LU.F — Konstruksi", "title": "Pembangunan dimulai",
            "date": date(2026, 8, 1), "impacts": "LU.F=Positif",
            "url": "https://example.com/lu", "source": "Fixture",
            "source_type": "portal", "snippet": "Cuplikan", "classification_count": 1,
        },
    ])
    result = {
        "metadata": {
            "status": "Selesai", "year": 2026, "quarter": 3,
            "start_date": date(2026, 7, 1), "end_date": date(2026, 9, 6),
            "run_at": datetime(2026, 9, 6, 12, 0),
        },
        "summary": {
            "Raw Records": 1, "Raw Records Terklasifikasi": 1,
            "Raw Records Tidak Terklasifikasi": 0, "Classification Rows Terpilih": 2,
            "Positif": 1, "Negatif": 0, "Netral": 1,
        },
        "selected_df": selected,
        "raw_df": raw,
        "taxonomy_summary": pd.DataFrame([
            {"Dimensi": "Lapangan Usaha", "Kode": "F", "Sektor/Subsektor": "Konstruksi", "Jumlah Berita": 1},
            {"Dimensi": "Pengeluaran", "Kode": "4.a", "Sektor/Subsektor": "Bangunan", "Jumlah Berita": 1},
        ]),
        "source_statuses": pd.DataFrame([
            {"Sumber": "Fixture", "Status": "Berhasil", "Ditemukan": 1, "Lolos Periode": 1,
             "Gagal Parse Tanggal": 0, "Warning/Error": ""},
        ]),
        "query_diagnostics": {
            "planned_queries": 2, "requests": 1, "results": 1, "retries": 0, "key_failovers": 0,
        },
    }
    app = AppTest.from_file(Path(__file__).parents[1] / "app.py")
    app.session_state["run_result"] = result
    app.run(timeout=30)
    assert not app.exception
    assert len(app.metric) == 7
    assert len(app.tabs) == 3
    assert len(app.dataframe) == 4
    assert len(app.multiselect) == 4
    download_labels = [button.label for button in app.get("download_button")]
    assert download_labels == [
        "⬇️ Download Lapangan Usaha",
        "⬇️ Download Pengeluaran",
        "⬇️ Download Raw Result",
    ]
