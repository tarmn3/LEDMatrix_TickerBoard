#!/usr/bin/env python3
import time
import re
import yfinance as yf
from luma.led_matrix.device import max7219
from luma.core.interface.serial import spi, noop
from luma.core.render import canvas
from luma.core.virtual import viewport
from luma.core.legacy import text
from luma.core.legacy.font import proportional, CP437_FONT

# List of stock codes to display
stock_codes = ["AAPL", "NVDA", "2914.T", "9984.T"]

# Create a Ticker object for each code once at startup
tickers = {code: yf.Ticker(code) for code in stock_codes}

# Cache settings
CACHE_DURATION = 160  # seconds
price_cache = {}
last_update = {}

# LED matrix settings
CASCADED = 4
BLOCK_ORIENTATION = -90
ROTATE = 2
REVERSE_ORDER = False

# Initialize MAX7219 device
serial = spi(port=0, device=0, gpio=noop())
device = max7219(
    serial,
    cascaded=CASCADED,
    block_orientation=BLOCK_ORIENTATION,
    rotate=ROTATE,
    blocks_arranged_in_reverse_order=REVERSE_ORDER
)
device.contrast(3)


def clean_company_name(name):
    """
    Remove specified corporate identifiers from the company name,
    case-insensitive, including optional trailing period.
    """
    pattern = r'\b(?:Corporation|Inc|LTD|CORP|MOTOR|GROUP)\b\.?'
    cleaned = re.sub(pattern, '', name, flags=re.IGNORECASE)
    return re.sub(r'\s{2,}', ' ', cleaned).strip()


def fetch_stock_price(code):
    """
    Fetch the current price via Ticker.info (fallback to history if needed),
    with per-symbol caching to reduce requests.
    """
    now = time.time()

    if code not in price_cache or now - last_update.get(code, 0) > CACHE_DURATION:
        try:
            info = tickers[code].info
            price = info.get("regularMarketPrice")
            if price is None:
                hist = tickers[code].history(period="1d", interval="1m")
                price = hist["Close"].iloc[-1]

            price_cache[code] = price
            last_update[code] = now
        except Exception as e:
            print(f"Warning: fetch error for {code}: {e}", flush=True)
            price = price_cache.get(code)
    else:
        price = price_cache[code]

    return price


def main():
    # Continuously update and scroll stock ticker
    while True:
        # Prepare message entries
        data_list = []
        for code in stock_codes:
            price = fetch_stock_price(code)
            info = tickers[code].info
            raw_name = info.get("shortName", code)
            name = clean_company_name(raw_name)
            entry = f"{name}:{price:.2f}" if price is not None else f"{name} Err"
            data_list.append(entry)

        # Build full scrolling text with padding at start and end
        prefix = "         "  # spaces before first entry
        suffix = "         "  # spaces after last entry
        message = prefix + "   ".join(data_list) + suffix
        text_width = len(message) * 6  # approximate pixel width

        # Create virtual viewport and draw text once
        virt = viewport(device, width=text_width, height=device.height)
        with canvas(virt) as draw:
            text(draw, (0, 0), message, fill="white", font=proportional(CP437_FONT))

        # Scroll text by advancing viewport without overflow
        max_pos = text_width - device.width
        for x in range(max_pos + 1):
            virt.set_position((x, 0))
            time.sleep(0.05)  # adjust speed as needed

if __name__ == "__main__":
    main()

