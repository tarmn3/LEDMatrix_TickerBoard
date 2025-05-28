# LEDMatrix_TickerBoard

Raspberry Pi に MAX7219 搭載の LED マトリックスパネルを接続し、株価の（簡易）ティッカーボードを実装します。



https://github.com/user-attachments/assets/e1aaa651-0fee-4e85-a2a0-5173b3088bcc



LED ドットマトリックスパネルは、8×8 ドットのマトリックスが 4 枚並んだボードで、ネット通販等で千円程度で比較的安価に入手可能です。

Python からは [luma.led_matrix](https://luma-led-matrix.readthedocs.io/en/latest/install.html) ライブラリを利用します。  
Raspberry Pi の設定やパネルとの接続方法は、上記ドキュメントの手順に従ってください。

---

## 目次

1. [前提条件](#前提条件)  
2. [環境準備](#環境準備)  
3. [使い方](#使い方)  
4. [ファイル一覧](#ファイル一覧)  


---

## 前提条件

- インターネット接続されたRaspberry Pi（GPIO／SPI が使えるモデル）  
- MAX7219 搭載 LED ドットマトリクスパネル（8×8 ドット ×4）

  <picture> <img width=30% src="https://github.com/user-attachments/assets/b7f07664-90d6-428e-83f7-1167e926df8a"> </picture>

- Python 3.x  
- Python ライブラリ  

## 環境準備

  利用するPythonライブラリをお使いの環境にインストールしておきます

  ```
  pip install luma.led-matrix yfinance
  ```

## 使い方
  LEDドットマトリクスパネルをドキュメントに沿って Raspberry Pi の SPI ピンに接続します
  スクリプトを実行するとLEDパネルに表示されます。
  ```
  python ticker_board.py
  ```
  ※表示内容や銘柄リストは各スクリプト内で適宜編集してください


## ファイル一覧
  - ticker_board.py

    - 英数字だけの ASCII 文字列で株価を表示（日本語文字列表示が不要ならこのファイルだけでOK）
    - フォント不要（ライブラリ内蔵フォント使用）
    - 株価データは Yahoo Finance! から取得（約 15 分遅延）

  - convert_bdf_to_bmf.py
    - BDF 形式の美咲フォントファイルを BMF 形式に変換

    - 別途［美咲フォント］(https://osdn.net/projects/misaki-font/) の BDF ファイルをダウンロードして用意

  - stock_ticker_board_nihongo.py
    - 変換済みのBMF形式の美咲フォントを利用して銘柄名を日本語文字列表示

    - 銘柄リストはスクリプト内の配列を編集して自由に追加・変更可能



