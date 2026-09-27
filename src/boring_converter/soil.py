"""土質名(自由記述)を可視化用の大分類に振り分ける。

柱状図の土質名は「砂質シルト」「盛土(粘性土)」「砂利・礫混り砂」のように表記の揺れが大きいので、
対応表ではなく規則で分類する。

1. 表土・盛土などの人工物、岩、火山灰質土、有機質土は、名前のどこかに含まれていれば優先
   (ただし「火山灰混り砂」「有機質土混りシルト」のような「〜混り」は修飾なので 2. に回す)
2. それ以外は、名前の中で最後に現れる土質の語で決める
   (日本語は後ろが主体: 砂質シルト → シルト、シルト質砂 → 砂、砂礫 → 礫、砂混りシルト → シルト)
"""
from __future__ import annotations

import re
import unicodedata

# (コード, 表示名)。並びは凡例の順
CLASSES = [
    ("topsoil", "表土"),
    ("fill", "盛土・埋土"),
    ("organic", "有機質土"),
    ("volcanic", "火山灰質土(ローム)"),
    ("clay", "粘性土"),
    ("silt", "シルト"),
    ("sand", "砂"),
    ("gravel", "礫"),
    ("rock", "岩"),
    ("unknown", "不明"),
]

_PRIORITY = [
    ("topsoil", re.compile(r"表土|表層|耕作土|農耕土")),
    ("fill", re.compile(r"盛土|盛り土|埋土|埋戻|客土|改良土|覆土|砕石|捨石|舗装|アスファルト|コンクリ|廃棄物|瓦礫|ガラ")),
    ("rock", re.compile(r"岩|破砕帯")),
    ("volcanic", re.compile(r"ローム|黒ボク|黒ぼく|シラス|しらす|火砕流|火山灰(?!混)|スコリア|軽石|浮石")),
    ("organic", re.compile(r"腐植|泥炭|高有機質|^有機質(?!土混)|有機質土$")),
]

# 終わりの位置が最も後ろの語で決める(「砂利」は「砂」より後ろで終わるので礫になる)
_LAST_WORD = [
    ("gravel", re.compile(r"礫|玉石|転石|砂利")),
    ("sand", re.compile(r"砂|まさ土|マサ")),
    ("silt", re.compile(r"シルト|しると|沈泥")),
    ("clay", re.compile(r"粘土|粘性土|細粒土|軟泥|浮泥")),
    # 「〜岩」以外の岩の固有名。「チャート礫」「石炭片混じり砂」のように修飾にも使われるので、
    # 優先ではなく最後に現れた語で決める(全国データで多いもの)
    ("rock", re.compile(r"チャート|アプライト|ペグマタイト|デイサイト|ホルンフェルス|カタクレーサイト|マイロナイト|石炭|亜炭")),
]


def normalize(name: str) -> str:
    s = unicodedata.normalize("NFKC", name)
    s = re.sub(r"ロ[-‐ｰ―]ム", "ローム", s)  # 「ロ－ム」等
    s = re.sub(r"\([A-Za-z]+\)$", "", s)  # 「シルト(M)」の記号
    return s.strip()


def classify(name: str | None) -> str:
    if not name:
        return "unknown"
    s = normalize(name)
    for code, pattern in _PRIORITY:
        if pattern.search(s):
            return code
    best = None  # (終わりの位置, コード)
    for code, pattern in _LAST_WORD:
        for m in pattern.finditer(s):
            if best is None or m.end() > best[0]:
                best = (m.end(), code)
    return best[1] if best else "unknown"
