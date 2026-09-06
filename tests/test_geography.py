from src.geography import geographic_relevance


def relevant(text, config, source_context=False):
    return geographic_relevance(text, config.geography, source_context)[0]


def test_local_and_province_are_relevant(config):
    assert relevant("Produksi padi Lombok Tengah meningkat", config)
    assert relevant("Produksi padi NTB turun 10 persen", config)


def test_other_district_only_is_not_relevant(config):
    assert not relevant("Hotel baru dibangun di Kota Bima", config)
    assert not relevant("Produksi jagung Dompu meningkat", config)
    assert not relevant("Program NTB dilaksanakan khusus di Kabupaten Bima", config)


def test_local_wins_over_other_area_and_source_context(config):
    assert relevant("Produksi padi NTB turun; Lombok Tengah ikut terdampak bersama Bima", config)
    assert relevant("Berita ekonomi tanpa nama wilayah", config, source_context=True)
