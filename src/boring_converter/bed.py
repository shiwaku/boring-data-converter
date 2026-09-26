"""ボーリング交換用データ(BED*.XML、地質・土質調査成果電子納品要領)の読み込み。

版による違い:
- 2.x : 土質の層は <土質岩種区分>(_下端深度, _土質岩種区分1, _土質岩種記号1, _分類コード1)
- 3.00 : <岩石土区分>(_下端深度, _岩石土名, _岩石土記号)
- 4.00 : <工学的地質区分名現場土質名>(_下端深度, _工学的地質区分名現場土質名, 同_記号)
土質名が空の層(2.x に多い)は推測で埋めず None のままにする。
- 総掘進長は 4.00 で「総削孔長」、測地系コードは 4.00 でゼロ埋め("01")
それ以外(経度緯度情報、孔口標高、色調、標準貫入試験、孔内水位)は共通のタグ名で読める。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

# 版ごとの土質層タグ: (要素名, 下端深度, 土質名, 土質記号)
LAYER_TAGS = [
    ("土質岩種区分", "土質岩種区分_下端深度", "土質岩種区分_土質岩種区分1", "土質岩種区分_土質岩種記号1"),
    ("岩石土区分", "岩石土区分_下端深度", "岩石土区分_岩石土名", "岩石土区分_岩石土記号"),
    ("工学的地質区分名現場土質名", "工学的地質区分名現場土質名_下端深度",
     "工学的地質区分名現場土質名_工学的地質区分名現場土質名",
     "工学的地質区分名現場土質名_工学的地質区分名現場土質名記号"),
]


@dataclass
class Layer:
    top_m: float
    bottom_m: float
    name: str | None
    symbol: str | None
    color: str | None = None


@dataclass
class Spt:
    depth_m: float  # 試験開始深度
    blows: int | None  # 合計打撃回数
    penetration_cm: int | None  # 合計貫入量

    @property
    def n_value(self) -> int | None:
        """30cm あたりに換算した N 値。貫入量が 30cm 未満なら打撃回数 × 30 / 貫入量。"""
        if self.blows is None:
            return None
        if self.penetration_cm and 0 < self.penetration_cm < 30:
            return round(self.blows * 30 / self.penetration_cm)
        return self.blows


@dataclass
class Boring:
    id: str
    dtd_version: str | None
    name: str | None
    survey_name: str | None
    lon: float
    lat: float
    datum: str | None  # 測地系コード(0: 日本測地系、1: 世界測地系 JGD2000、2: JGD2011)
    elevation_m: float | None  # 孔口標高
    length_m: float | None  # 総掘進長
    water_level_m: float | None  # 孔内水位(最初の測定値、孔口からの深さ)
    layers: list[Layer] = field(default_factory=list)
    spts: list[Spt] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _text(el, tag) -> str | None:
    found = el.find(f".//{tag}")
    if found is None or found.text is None:
        return None
    s = found.text.strip()
    return s or None


def _num(s: str | None) -> float | None:
    if s is None:
        return None
    try:
        return float(s.replace("　", "").strip())
    except ValueError:
        return None


def _int(s: str | None) -> int | None:
    v = _num(s)
    return None if v is None else int(round(v))


def tokyo_to_jgd(lon: float, lat: float) -> tuple[float, float]:
    """日本測地系 → 世界測地系の近似変換(誤差数 m 程度。可視化用途)。"""
    lat_w = lat - 0.00010695 * lat + 0.000017464 * lon + 0.0046017
    lon_w = lon - 0.000046038 * lat - 0.000083043 * lon + 0.010040
    return lon_w, lat_w


def _read_xml(path: Path) -> etree._Element:
    raw = path.read_bytes()
    m = re.match(rb'<\?xml[^>]*encoding=["\']([^"\']+)', raw)
    enc = m.group(1).decode().lower() if m else "utf-8"
    # Shift_JIS 宣言でも機種依存文字(①、～ 等)が入っていることが多いので CP932 で読む
    if enc.replace("-", "_") in ("shift_jis", "sjis", "x_sjis", "ms932", "windows_31j"):
        enc = "cp932"
    text = raw.decode(enc, errors="replace")
    text = re.sub(r"^\s*<\?xml[^>]*\?>", "", text)
    parser = etree.XMLParser(recover=True, resolve_entities=False, no_network=True, load_dtd=False)
    return etree.fromstring(text.encode("utf-8"), parser)


def _dms(el, prefix) -> float | None:
    d, m, s = (_num(_text(el, f"{prefix}_{u}")) for u in ("度", "分", "秒"))
    if d is None:
        return None
    return d + (m or 0) / 60 + (s or 0) / 3600


def _intervals(elements, bottom_tag):
    """下端深度だけを持つ要素の並びを (上端, 下端, 要素) の区間に直す。"""
    top = 0.0
    for el in elements:
        bottom = _num(_text(el, bottom_tag))
        if bottom is None or bottom <= top:
            continue
        yield top, bottom, el
        top = bottom


def parse(path: str | Path, boring_id: str | None = None) -> Boring:
    path = Path(path)
    root = _read_xml(path)
    warnings: list[str] = []

    lon, lat = _dms(root, "経度"), _dms(root, "緯度")
    if lon is None or lat is None:
        raise ValueError(f"{path}: 経度緯度情報がありません")
    datum = _text(root, "測地系")
    if datum is not None and datum.isdigit():
        datum = str(int(datum))  # 4.00 は "01" のようにゼロ埋め
    if datum == "0":
        lon, lat = tokyo_to_jgd(lon, lat)
        warnings.append("日本測地系を世界測地系に近似変換")

    water = next((_num(e.text) for e in root.iter("孔内水位_孔内水位") if _num(e.text) is not None), None)

    b = Boring(
        id=boring_id or path.stem,
        dtd_version=(root.get("DTD_version") or "").strip() or None,
        name=_text(root, "ボーリング名"),
        survey_name=_text(root, "調査名"),
        lon=lon,
        lat=lat,
        datum=datum,
        elevation_m=_num(_text(root, "孔口標高")),
        length_m=_num(_text(root, "総掘進長") or _text(root, "総削孔長")),  # 4.00 は総削孔長
        water_level_m=water,
        warnings=warnings,
    )
    if b.elevation_m is None:
        warnings.append("孔口標高なし")

    # 土質の層(版によってタグ名が違う)
    for tag, bottom_tag, name_tag, symbol_tag in LAYER_TAGS:
        els = root.findall(f".//{tag}")
        if els:
            for top, bottom, el in _intervals(els, bottom_tag):
                b.layers.append(Layer(top, bottom, _text(el, name_tag), _text(el, symbol_tag)))
            break
    else:
        warnings.append("土質の層が見つかりません")

    # 色調は層とは別の区間で記録されるので、層の中央深度で対応づける
    colors = [(t, bo, _text(el, "色調_色調名")) for t, bo, el in _intervals(root.findall(".//色調"), "色調_下端深度")]
    for layer in b.layers:
        mid = (layer.top_m + layer.bottom_m) / 2
        layer.color = next((c for t, bo, c in colors if t <= mid < bo), None)

    for el in root.findall(".//標準貫入試験"):
        depth = _num(_text(el, "標準貫入試験_開始深度"))
        if depth is None:
            continue
        b.spts.append(Spt(depth, _int(_text(el, "標準貫入試験_合計打撃回数")),
                          _int(_text(el, "標準貫入試験_合計貫入量"))))
    return b
