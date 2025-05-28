#!/usr/bin/env python3
"""
Raspberry Pi MAX7219 スクロール株価表示
  - luma.led_matrix (MAX7219) で 8x8 マトリクスにテキストをスクロール
  - yfinance で株価取得、自前の TTL キャッシュ
  - Config クラスに設定集約、社名マッピング対応
  - 銘柄名は美咲フォント、株価数字は CP437 フォントで混在表示
  - 株価数字を 1 ドット下にオフセット、末尾の空白で見切れ防止
  - ".T" で終わるコードは3000円以下:小数1位、3001円以上:整数表示
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
# レガシーフォント用
from luma.core.legacy import text as legacy_text
from luma.core.legacy.font import proportional, CP437_FONT


class Config:
    # 表示するティッカーシンボル／コード一覧
STOCK_CODES: List[str] = [
    "AAPL",
    "NVDA",
    "TSLA",
    "7203.T",
    "6758.T",
    "9984.T",
    "2914.T",
    "7011.T",
    "8058.T",
    "9104.T"
]

    # カスタム社名マッピング: シンボル → 表示社名
COMPANY_NAMES: Dict[str, str] = {
    "AAPL":    "Ａｐｐｌｅ",
    "NVDA":    "ＮＶＩＤＩＡ",
    "TSLA":    "Ｔｅｓｌａ",
    "7203.T":  "トヨタ",
    "6758.T":  "ＳＯＮＹ",
    "9984.T":  "ソフトバンクＧ",
    "2914.T":  "ＪＴ",
    "7011.T":  "三菱重工",
    "8058.T":  "三菱商事",
    "9104.T":  "商船三井"
}

    CACHE_TTL: int = 160           # キャッシュ有効期間（秒）
    SPI_PORT: int = 0
    SPI_DEVICE: int = 0
    CASCADED: int = 8              # LEDドットマトリクス基板1個だけなら 4 にする
    BLOCK_ORIENTATION: int = -90
    ROTATE: int = 2
    REVERSE_ORDER: bool = False
    CONTRAST: int = 1              # 明るさ (大きくするとより明るくなる）
    SCROLL_SPEED: float = 0.05     # スクロール間隔（秒) 大きくすると遅くなる
    FONT_PATH: str = "misaki_gothic.bmf"
    LEGACY_FONT = proportional(CP437_FONT)


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
        self.legacy_font = cfg.LEGACY_FONT
        self.speed = cfg.SCROLL_SPEED

    def scroll_entries(self, entries: List[Tuple[str, str]]):
        char_w = 6
        blank_name_price = 2
        blank_entry = 3
        suffix_blanks = (self.device.width // char_w) + 1
        total_chars = sum(
            len(name) + blank_name_price + len(price) + blank_entry
            for name, price in entries
        ) + suffix_blanks
        msg_w = total_chars * char_w

        virt = viewport(
            self.device,
            width=msg_w + self.device.width,
            height=self.device.height
        )
        with canvas(virt) as draw:
            x = self.device.width
            for name, price in entries:
                draw.text((x, 0), name, fill="white", font=self.font)
                x += len(name) * char_w
                x += blank_name_price * char_w
                legacy_text(draw, (x, 1), price, fill="white", font=self.legacy_font)
                x += len(price) * char_w
                x += blank_entry * char_w

        for pos in range(msg_w + 1):
            virt.set_position((pos, 0))
            time.sleep(self.speed)


def clean_name(name: str) -> str:
    pattern = r'\b(?:Corporation|Co|Holdings|Inc|LTD|CORP|MOTOR|GROUP)\b\.?'
    return re.sub(pattern, '', name, flags=re.IGNORECASE).strip()


def build_entries(codes: List[str], fetcher: StockFetcher) -> List[Tuple[str, str]]:
    entries: List[Tuple[str, str]] = []
    for code in codes:
        name = Config.COMPANY_NAMES.get(
            code,
            clean_name(fetcher.tickers[code].info.get("shortName", code))
        )
        price = fetcher.fetch_price(code)
        if price is None:
            price_str = "Err"
        else:
            if code.endswith('.T'): #東証銘柄の呼値単位処理
                if price <= 3000:
                    price_str = f"{price:.1f}"
                else:
                    price_str = f"{int(price)}"
            else:
                price_str = f"{price:.2f}"
        entries.append((name, price_str))
    return entries


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
            entries = build_entries(codes, fetcher)
            display.scroll_entries(entries)
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("ユーザーによる中断で終了")


if __name__ == "__main__":
    main()
