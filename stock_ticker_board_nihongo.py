#!/usr/bin/env python3
"""
Raspberry Pi MAX7219 スクロール株価表示
  - luma.led_matrix (MAX7219) で 8x8 マトリクスにテキストをスクロール
  - yfinance で株価取得、自前の TTL キャッシュ
  - 設定は Config クラスに集約
  - シンボル→社名マッピング対応
"""

import time
import re
import logging
import argparse
from typing import List, Optional, Tuple, Dict

import yfinance as yf
from luma.core.interface.serial import spi, noop
from luma.led_matrix.device import max7219
from luma.core.render import canvas
from luma.core.virtual import viewport
from luma.core.bitmap_font import load


class Config:
    # 表示するティッカーシンボル／コード一覧
    STOCK_CODES: List[str] = [
        "AAPL",
        "NVDA",
        "7011.T",
        "8058.T",
        "9104.T",
        "7203.T",
        "6758.T",
        "9984.T"
    ]

    # カスタム社名マッピング: シンボル → 表示社名
    # マッピング型で用意された場合はここを優先
    COMPANY_NAMES: Dict[str, str] = {
        "AAPL": "Ａｐｐｌｅ",
        "NVDA": "ＮＶＩＤＩＡ",
        "7011.T": "三菱重工",
        "8058.T": "三菱商事",
        "9104.T": "商船三井",
        "7203.T": "トヨタ",
        "6758.T": "ＳＯＮＹ",
        "9984.T": "ソフトバンクＧ"
        # 以下、必要に応じて追加してください
    }

    CACHE_TTL: int = 160           # キャッシュ有効期間（秒）
    SPI_PORT: int = 0
    SPI_DEVICE: int = 0
    CASCADED: int = 8
    BLOCK_ORIENTATION: int = -90
    ROTATE: int = 2
    REVERSE_ORDER: bool = False
    CONTRAST: int = 1
    SCROLL_SPEED: float = 0.1     # スクロール間隔（秒）
    FONT_PATH: str = "misaki_gothic.bmf"


class StockFetcher:
    def __init__(self, codes: List[str], ttl: int):
        self.tickers = {code: yf.Ticker(code) for code in codes}
        self.ttl = ttl
        self._cache: Dict[str, Tuple[Optional[float], float]] = {}

    def fetch_price(self, code: str) -> Optional[float]:
        now = time.time()
        if code in self._cache:
            price, ts = self._cache[code]
            if now - ts < self.ttl:
                return price
        try:
            info = self.tickers[code].info
            price = info.get("regularMarketPrice")
            if price is None:
                hist = self.tickers[code].history(period="1d", interval="1m")
                price = hist["Close"].iloc[-1]
        except Exception as e:
            logging.warning(f"株価取得エラー {code}: {e}")
            price = self._cache.get(code, (None, 0))[0]
        self._cache[code] = (price, now)
        return price


class LEDDisplay:
    def __init__(self, cfg: Config):
        serial = spi(port=cfg.SPI_PORT, device=cfg.SPI_DEVICE, gpio=noop())
        self.device = max7219(
            serial,
            cascaded=cfg.CASCADED,
            block_orientation=cfg.BLOCK_ORIENTATION,
            rotate=cfg.ROTATE,
            blocks_arranged_in_reverse_order=cfg.REVERSE_ORDER
        )
        self.device.contrast(cfg.CONTRAST)
        self.font = load(cfg.FONT_PATH)
        self.speed = cfg.SCROLL_SPEED

    def scroll_text(self, message: str):
        msg_w, _ = self.font.getsize(message)
        virt = viewport(self.device,
                        width=msg_w + self.device.width,
                        height=self.device.height)
        with canvas(virt) as draw:
            draw.text((self.device.width, 0), message, fill="white", font=self.font)
        for x in range(msg_w + 1):
            virt.set_position((x, 0))
            time.sleep(self.speed)


def clean_name(name: str) -> str:
    # 法人表記除去
    pattern = r'\b(?:Corporation|Co|Holdings|Inc|LTD|CORP|MOTOR|GROUP)\b\.?'
    return re.sub(pattern, '', name, flags=re.IGNORECASE).strip()


def build_message(codes: List[str], fetcher: StockFetcher) -> str:
    entries: List[str] = []
    for code in codes:
        # カスタムマッピングがあればそちらを優先
        if code in Config.COMPANY_NAMES:
            name = Config.COMPANY_NAMES[code]
        else:
            raw = fetcher.tickers[code].info.get("shortName", code)
            name = clean_name(raw)

        price = fetcher.fetch_price(code)
        entries.append(f" {name}:{price:.2f}  " if price else f"{name} Err")

    prefix = " " * 8
    suffix = " " * 20
    return prefix + " ".join(entries) + suffix


def parse_args():
    p = argparse.ArgumentParser(description="MAX7219 Stock Ticker")
    p.add_argument("--stocks", nargs="+",
                   help="表示する銘柄コード一覧（デフォルトは設定ファイル）")
    p.add_argument("--speed", type=float,
                   help="スクロール速度（秒単位）")
    return p.parse_args()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s: %(message)s"
    )
    args = parse_args()
    codes = args.stocks or Config.STOCK_CODES
    fetcher = StockFetcher(codes, Config.CACHE_TTL)
    display = LEDDisplay(Config)
    if args.speed:
        display.speed = args.speed

    try:
        while True:
            msg = build_message(codes, fetcher)
            display.scroll_text(msg)
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("ユーザーによる中断で終了")


if __name__ == "__main__":
    main()

