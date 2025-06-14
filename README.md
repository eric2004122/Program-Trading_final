# 0050 MACD 策略回測平台

> 一個使用 Flask、yfinance 與 Matplotlib 打造的網頁應用程式，讓使用者能夠對元大台灣50 (0050.TW) ETF 進行 MACD 交易策略的量化回測與績效分析。

這個平台擁有一個優雅且具現代感的「毛玻璃」風格使用者介面，並在後端執行穩健的金融數據分析與策略回測。

![專案截圖](YOUR_SCREENSHOT_PATH_HERE.png)
*(請將此處的路徑替換成您的應用程式截圖，建議使用結果頁面的截圖以展示所有功能)*

---

## ✨ 功能亮點 (Features)

*   **視覺化回測儀表板**：採用「靜謐深藍與青金石」主題的毛玻璃風格介面，資訊清晰，視覺效果專業。
*   **動態參數設定**：使用者可自訂回測的 **投入本金**、**開始日期** 與 **結束日期**。
*   **核心交易策略**：
    *   **買進訊號**：MACD 黃金交叉 (`DIF` 由下往上穿越 `MACD` 線)。
    *   **賣出訊號**：
        *   MACD 死亡交叉 (`DIF` 由上往下穿越 `MACD` 線)。
        *   固定比例停損 (`-5%`)。
        *   固定比例停利 (`+10%`)。
*   **完整的績效指標**：
    *   總報酬率
    *   年化報酬率 (CAGR)
    *   勝率 (%)
    *   最大回撤 (Max Drawdown)
    *   總交易次數
*   **動態圖表生成**：使用 `Matplotlib` 動態生成包含 **收盤價** 與 **MACD 指標** 的策略圖表，並以 Base64 格式內嵌於網頁中。
*   **詳細交易紀錄**：以表格形式清楚列出每一筆買賣的日期、動作、價格、股數、資金餘額及單筆報酬率。
*   **優質使用者體驗**：
    *   非同步操作感：在後端計算時，前端會顯示優雅的「載入中」動畫，防止畫面凍結。
    *   精緻動畫效果：儀表板卡片與內容區塊皆有平滑的淡入動畫。
    *   直觀互動：交易紀錄表格的滑鼠懸停效果，依買賣類型顯示不同顏色。

## 🚀 技術棧 (Tech Stack)

*   **後端 (Backend)**:
    *   [Flask](https://flask.palletsprojects.com/): 輕量級的 Python Web 框架。
    *   [yfinance](https://pypi.org/project/yfinance/): 從 Yahoo Finance 下載金融市場數據。
    *   [Pandas](https://pandas.pydata.org/): 用於數據處理、分析與計算技術指標。
    *   [Matplotlib](https://matplotlib.org/): 用於生成策略分析圖表。

*   **前端 (Frontend)**:
    *   HTML5
    *   [TailwindCSS](https://tailwindcss.com/): 一個 Utility-First 的 CSS 框架，用於快速打造現代化介面。
    *   [Font Awesome](https://fontawesome.com/): 提供各種圖示。
    *   原生 JavaScript: 用於實現前端的互動效果，如載入動畫。

## 🛠️ 安裝與啟動 (Setup & Run)

請依照以下步驟在您的本地環境中啟動此專案。

1.  **複製專案儲存庫**
    ```bash
    git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
    cd YOUR_REPOSITORY
    ```

2.  **建立並啟用虛擬環境 (建議)**
    *   **MacOS / Linux:**
        ```bash
        python3 -m venv venv
        source venv/bin/activate
        ```
    *   **Windows:**
        ```bash
        python -m venv venv
        .\venv\Scripts\activate
        ```

3.  **安裝所需的套件**
    ```bash
    pip install flask yfinance pandas matplotlib
    ```

4.  **啟動 Flask 應用程式**
    ```bash
    python APP.py
    ```

5.  **開啟瀏覽器**
    在您的瀏覽器中開啟 `http://127.0.0.1:5001`，即可開始使用。

## 📁 專案結構 (Project Structure)

```
.
├── APP.py                  # Flask 主程式，包含所有後端邏輯與路由
├── templates/
│   ├── index.html          # 主頁面，用於設定回測參數
│   └── strategy_template.html # 結果頁面，展示績效指標與圖表
├── static/
│   └── favicon.png         # 網站圖示 (請將您的圖示放於此)
└── README.md               # 本文件
```

## 📈 核心策略邏輯 (Core Strategy Logic)

本專案的回測邏輯已將真實交易成本納入考量，以求結果更貼近現實。

*   **交易標的**: `0050.TW` (元大台灣50 ETF)
*   **手續費率**: `0.1425%` (買進與賣出時計算)
*   **交易稅率**: `0.1%` (僅賣出 ETF 時計算)
*   **MACD 參數**:
    *   快線 (EMA): 12日
    *   慢線 (EMA): 26日
    *   信號線 (Signal): 9日

## ⚖️ 免責聲明 (Disclaimer)

本專案僅為學術研究與程式設計實作範例，**不構成任何投資建議**。所有回測結果均基於歷史數據，歷史績效不代表未來表現。任何據此進行的真實投資操作，風險自負。

## 📄 授權條款 (License)

本專案採用 [MIT License](https://opensource.org/licenses/MIT) 授權。