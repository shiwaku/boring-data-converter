"""国土交通データプラットフォーム(DPP) GraphQL API の最小クライアント。

APIキーは環境変数 MLIT_API_KEY、.env の MLIT_API_KEY=...、apikey.txt(キーのみ1行)の順に探す。
"""
import json
import os
import time
from pathlib import Path

import requests

ENDPOINT = os.getenv("MLIT_BASE_URL", "https://data-platform.mlit.go.jp/api/v1/")
ROOT = Path(__file__).resolve().parent.parent  # APIキー・出力はプロジェクト直下に置く
RPS = float(os.getenv("DPP_RPS", "2"))  # 公式MCPは4rps。大量取得なので控えめに
MAX_RETRIES = 5


def _load_api_key() -> str:
    key = os.getenv("MLIT_API_KEY")
    env = ROOT / ".env"
    if not key and env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("MLIT_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"')
    txt = ROOT / "apikey.txt"
    if not key and txt.exists():
        key = txt.read_text(encoding="utf-8-sig").strip()
        # 「APIキー: xxxx」のようなラベル付きでも読めるようにする
        key = key.replace("：", ":").split(":", 1)[-1].strip()
    if not key:
        raise SystemExit("APIキーが未設定です(apikey.txt にキーだけを書く、または .env に MLIT_API_KEY=...)")
    return key


class DPPClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "apikey": _load_api_key(),
            "Content-Type": "application/json",
        })
        self._last = 0.0

    def _throttle(self):
        wait = 1.0 / RPS - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()

    def query(self, q: str) -> dict:
        for attempt in range(MAX_RETRIES):
            self._throttle()
            try:
                r = self.session.post(ENDPOINT, json={"query": q}, timeout=60)
            except requests.RequestException as e:
                err = str(e)
            else:
                if r.status_code == 200:
                    body = r.json()
                    if body.get("errors"):
                        raise RuntimeError(json.dumps(body["errors"], ensure_ascii=False))
                    return body["data"]
                if r.status_code not in (429, 500, 502, 503, 504):
                    raise RuntimeError(f"HTTP {r.status_code}: {r.text[:500]}")
                err = f"HTTP {r.status_code}"
            delay = min(60, 2 ** attempt)
            print(f"  retry {attempt + 1}/{MAX_RETRIES} after {delay}s ({err})")
            time.sleep(delay)
        raise RuntimeError(f"giving up after {MAX_RETRIES} retries")


def gql_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)
