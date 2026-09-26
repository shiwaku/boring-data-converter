import json
from pathlib import Path

import pytest

from boring_converter.bed import Spt, parse
from boring_converter.cli import main

FIX = Path(__file__).parent / "fixtures"


def test_v210():
    b = parse(FIX / "kunijiban_149789321_v2.10.xml")
    assert b.dtd_version == "2.10"
    # KuniJiban のマーカー API の座標(世界測地系)と一致する
    assert b.lon == pytest.approx(139.7462208, abs=1e-6)
    assert b.lat == pytest.approx(35.67915111, abs=1e-6)
    assert b.elevation_m == 15.27
    assert b.length_m == 31.16
    assert len(b.layers) == 18
    first = b.layers[0]
    assert (first.top_m, first.bottom_m, first.name, first.color) == (0.0, 4.0, "埋土", "暗褐灰")
    # 層は隙間なく連続する
    assert all(a.bottom_m == c.top_m for a, c in zip(b.layers, b.layers[1:]))
    assert b.spts[0].depth_m == 4.15 and b.spts[0].n_value == 7


def test_v300():
    b = parse(FIX / "kunijiban_506957380_v3.00.xml")
    assert b.dtd_version == "3.00"
    assert len(b.layers) == 10
    assert (b.layers[0].name, b.layers[0].symbol) == ("埋土", "FI")
    assert b.layers[-1].bottom_m == b.length_m == 35.29
    assert b.water_level_m == 10.86


def test_v400():
    b = parse(FIX / "kunijiban_508177590_v4.00.xml")
    assert b.dtd_version == "4.00"
    assert b.datum == "1"  # "01" を正規化
    assert b.length_m == 23.45  # 総削孔長
    assert len(b.layers) == 12
    assert (b.layers[0].name, b.layers[0].symbol) == ("表土", "SF")
    assert b.water_level_m == 4.20


def test_tokyo_datum():
    b = parse(FIX / "kunijiban_243720635_v2.10_tokyo_datum.xml")
    assert b.datum == "0"
    # 近似変換後、KuniJiban が世界測地系で示す位置と数 m 以内
    assert b.lon == pytest.approx(139.626218, abs=5e-5)
    assert b.lat == pytest.approx(35.807662, abs=5e-5)


@pytest.mark.parametrize("blows,pen,n", [(7, 30, 7), (50, 10, 150), (50, 15, 100), (None, None, None), (3, None, 3)])
def test_n_value(blows, pen, n):
    assert Spt(1.0, blows, pen).n_value == n


def test_cli(tmp_path):
    main([str(FIX), "-o", str(tmp_path / "out")])
    layers = [json.loads(line) for line in (tmp_path / "out.layers.ndjson").open(encoding="utf-8")]
    borings = [json.loads(line) for line in (tmp_path / "out.borings.ndjson").open(encoding="utf-8")]
    assert len(borings) == 4
    p = layers[0]["properties"]
    for key in ("top_depth_cm", "bottom_depth_cm", "thickness_cm", "top_elev_cm", "bottom_elev_cm"):
        assert isinstance(p[key], int)  # tippecanoe / mlt 向けに整数 cm
    assert p["top_elev_cm"] - p["bottom_elev_cm"] == p["thickness_cm"]
