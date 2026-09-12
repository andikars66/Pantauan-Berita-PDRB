from pathlib import Path
from datetime import date, datetime

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest


@pytest.fixture(autouse=True)
def mock_credit_lookup(monkeypatch):
    monkeypatch.setattr("src.serper_client.fetch_serper_credits", lambda _keys: {
        "total": 1234, "checked_keys": 2, "configured_keys": 2,
    })


def test_compact_period_and_hierarchical_taxonomy_ui():
    app = AppTest.from_file(Path(__file__).parents[1] / "app.py").run(timeout=30)
    assert not app.exception
    assert any("<h1>Tukang Koran</h1>" in item.value for item in app.markdown)
    assert any("Telusur Kabar Aktivitas Ekonomi Regional — Koleksi, Kategorisasi, dan Analisis PDRB" in item.value for item in app.markdown)
    assert len(app.selectbox) == 1
    assert len(app.checkbox) == 98
    assert app.button[-1].label == "Mulai Pencarian"
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
        "Download Lapangan Usaha",
        "Download Pengeluaran",
        "Download Raw Result",
    ]


def test_source_checkboxes_and_credit_badge():
    app = AppTest.from_file(Path(__file__).parents[1] / "app.py").run(timeout=30)
    assert not app.exception
    assert any("Credits left: 1,234" in item.value for item in app.markdown)
    sources = [item for item in app.checkbox if item.key.startswith("source_")]
    assert {item.label for item in sources} == {"Serper", "Inside Lombok", "Lombok Post", "Radar Mandalika", "Radar Lombok", "Suara NTB", "Pemkab Lombok Tengah"}
    assert all(item.value for item in sources)
    app.checkbox[1].check()
    for item in sources:
        item.uncheck()
    app.run(timeout=30)
    assert app.button(key="run_button").disabled
    app.checkbox(key="source_radar_mandalika").check().run(timeout=30)
    assert not app.button(key="run_button").disabled
    assert not app.checkbox(key="source_serper").value


def test_incomplete_balance_is_not_presented_as_total(monkeypatch):
    monkeypatch.setattr("src.serper_client.fetch_serper_credits", lambda _keys: {
        "total": None, "checked_keys": 1, "configured_keys": 2,
    })
    app = AppTest.from_file(Path(__file__).parents[1] / "app.py").run(timeout=30)
    assert any("Credits left: Tidak tersedia" in item.value for item in app.markdown)
    assert any("1/2" in item.value for item in app.caption)


def test_balance_cached_on_ui_changes_and_refreshed_after_serper_run(monkeypatch):
    calls = []
    def credits(_keys):
        calls.append(1)
        return {"total": 200 - len(calls), "checked_keys": 1, "configured_keys": 1}
    monkeypatch.setattr("src.serper_client.fetch_serper_credits", credits)
    monkeypatch.setattr("src.serper_client.SerperClient.collect", lambda *_args: [])
    app = AppTest.from_file(Path(__file__).parents[1] / "app.py").run(timeout=30)
    app.checkbox[1].check()
    for item in app.checkbox:
        if item.key.startswith("source_") and item.key != "source_serper":
            item.uncheck()
    app.run(timeout=30)
    assert len(calls) == 1
    app.button(key="run_button").click().run(timeout=30)
    assert not app.exception
    assert len(calls) == 2
    assert app.session_state["run_result"]["metadata"]["selected_sources"] == ["serper"]
    assert any("Credits left: 198" in item.value for item in app.markdown)
