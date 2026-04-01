# OHLCV 策略回測驗證系統 — 使用教程

**版本：** v1.0  
**適合對象：** 初次使用者

---

## 目錄

1. [安裝與環境](#1-安裝與環境)
2. [第一次回測：30 秒快速上手](#2-第一次回測)
3. [了解輸出結果](#3-了解輸出結果)
4. [設計你自己的策略](#4-設計你自己的策略)
5. [載入真實 CSV 數據](#5-載入真實-csv-數據)
6. [使用網頁 GUI](#6-使用網頁-gui)
7. [解讀統計驗證結果](#7-解讀統計驗證結果)
8. [自定義條件擴充](#8-自定義條件擴充)
9. [常見問題](#9-常見問題)

---

## 1. 安裝與環境

### 需求

- Python 3.10 以上
- pytest（僅用於跑測試，非必要）

### 安裝

```bash
# 克隆專案
git clone <repo-url>
cd stock_test

# 安裝測試框架（可選）
pip install pytest

# 確認環境正常
python -m pytest tests/ -q
# 預期輸出：123 passed, 1 skipped
```

### 專案不依賴任何第三方套件

所有核心功能（數據生成、指標計算、回測、統計驗證）均使用 Python 標準庫實作。

---

## 2. 第一次回測

### 最簡單的執行方式

```bash
python main.py
```

這會：
1. 生成 200 根模擬 K 棒（bull 模式，seed=42）
2. 用內建的「趨勢突破 v1」策略執行回測
3. 在終端機列印結果摘要
4. 同時執行 Monte Carlo、Monkey Test、Walk-Forward 驗證

**終端機輸出範例：**
```
[1/4] Generating simulated data (mode=bull, bars=200, seed=42)
      Loaded 200 bars (2026-01-01 → 2026-07-19)
[2/4] Loading strategy from: config/strategy_config.json
      Strategy: Trend Following Breakout v1
[3/4] Running backtest...
      Trades:        3
      Win rate:      66.7%
      Total return:  13.80%
      Max drawdown:  -5.20%
      Profit factor: 2.66
      Sharpe ratio:  1.85
[4/4] Running statistical validation...
      Monte Carlo p50 return: 13.50%  ruin prob: 1.2%
      Monkey Test rank: 74.5th percentile  p-value: 0.255  significant: False
      Walk-Forward folds: 4  degradation: 0.26  overfit warning: True
```

### 儲存結果到 JSON 檔案

```bash
python main.py --output my_result.json
```

之後可以用網頁 GUI 開啟 `my_result.json` 查看視覺化結果。

### 常用參數

| 參數 | 預設值 | 說明 |
|------|--------|------|
| `--mode` | `bull` | 市場模式：`random` / `bull` / `bear` / `choppy` / `diverge` |
| `--bars` | `200` | K 棒數量 |
| `--seed` | `42` | 隨機種子（相同種子每次結果一致） |
| `--output` | 無 | 儲存完整結果到 JSON 檔案 |
| `--no-validation` | 關閉 | 跳過統計驗證（加快速度）|
| `--strategy` | `config/strategy_config.json` | 策略設定檔路徑 |
| `--csv` | 無 | 使用真實 CSV 數據（見第 5 節）|

**範例：**
```bash
# 測試 bear 市場、500 根、存檔
python main.py --mode bear --bars 500 --seed 123 --output bear_result.json

# 快速跑，不做統計驗證
python main.py --bars 1000 --no-validation

# 用自訂策略
python main.py --strategy config/my_strategy.json --output result.json
```

---

## 3. 了解輸出結果

### 3.1 終端機摘要

執行後會看到：

| 欄位 | 說明 |
|------|------|
| Trades | 總交易次數 |
| Win rate | 勝率（獲利交易 / 總交易）|
| Total return | 累計報酬（所有交易 PnL% 加總）|
| Max drawdown | 最大回撤（累計損益曲線的最深谷底）|
| Profit factor | 毛利 / 毛損（> 1 代表整體獲利）|
| Sharpe ratio | 夏普比率（風險調整後報酬）|

### 3.2 JSON 輸出結構

儲存的 JSON 包含四個頂層欄位：

```
results.json
├── metadata       → 策略名稱、數據範圍、warmup 期數等
├── trades         → 每一筆交易的完整記錄
├── scan_log       → 逐根 K 棒掃描日誌（含每根的進出場條件狀態）
└── summary        → 統計摘要（勝率、期望值、最大回撤等）
```

### 3.3 交易記錄（trades）

每筆交易包含：

```json
{
  "id": 1,
  "entry_date": "2026-04-11",
  "entry_price": 105.20,
  "exit_date": "2026-05-01",
  "exit_price": 115.80,
  "exit_reason": "trailing_stop",   ← 出場原因
  "bars_held": 20,                  ← 持倉天數
  "pnl_pct": 10.07,                 ← 損益百分比
  "peak_price": 118.50,             ← 持倉期間最高價
  "max_drawdown_during_trade": -2.3 ← 持倉期間最大回撤
}
```

**出場原因說明：**

| exit_reason | 意義 |
|-------------|------|
| `atr_stop` | ATR 倍數止損觸發 |
| `ma_stop` | 均線交叉止損觸發 |
| `trailing_stop` | 移動止盈觸發（漲幅達門檻後回落）|
| `end_of_data` | 數據結束時強制平倉 |

### 3.4 掃描日誌（scan_log）

每根 K 棒一筆記錄，例如（持倉中）：

```json
{
  "index": 110,
  "date": "2026-04-21",
  "ohlcv": { "open": 112.3, "high": 114.1, "low": 111.5, "close": 113.8, "volume": 13500 },
  "indicators": { "sma_20": 109.2, "sma_50": 105.8, "atr_14": 2.4 },
  "entry_triggered": false,
  "position": {
    "entry_price": 105.20,
    "current_pnl_pct": 8.17,  ← 當前未實現損益
    "peak_price": 114.1,
    "bars_held": 9
  },
  "exit_conditions": {
    "atr_stop":      { "triggered": false, "stop_price": 97.98, "distance_pct": 13.9 },
    "trailing_stop": { "triggered": false, "active": false, "trail_price": null }
  }
}
```

---

## 4. 設計你自己的策略

### 4.1 策略設定格式

策略用 JSON 定義，放在 `config/` 目錄：

```json
{
  "name": "我的第一個策略",
  "entry": {
    "mode": "ALL",
    "conditions": [
      { "type": "條件類型", "params": { "參數": 值 } }
    ]
  },
  "exit": {
    "mode": "ANY",
    "conditions": [
      { "type": "條件類型", "params": { "參數": 值 } }
    ]
  }
}
```

- `entry.mode = "ALL"`：所有進場條件同時滿足才進場
- `entry.mode = "ANY"`：任一進場條件滿足即可進場
- `exit.mode = "ANY"`：任一出場條件觸發就出場（常用）

### 4.2 內建進場條件

**breakout** — 收盤價突破 N 日最高點
```json
{ "type": "breakout", "params": { "period": 20, "field": "high" } }
```

**volume_above_ma** — 成交量超過 N 日均量的 M 倍
```json
{ "type": "volume_above_ma", "params": { "multiplier": 1.5, "period": 20 } }
```

**ma_alignment** — 快均線在慢均線之上（多頭排列）
```json
{ "type": "ma_alignment", "params": { "fast": 20, "slow": 50, "direction": "bullish" } }
```
> `direction` 可以是 `"bullish"`（快>慢）或 `"bearish"`（快<慢）

**price_above_ma** — 收盤價高於均線
```json
{ "type": "price_above_ma", "params": { "period": 20, "direction": "above" } }
```

### 4.3 內建出場條件

**atr_stop** — ATR 倍數止損（最常用）
```json
{ "type": "atr_stop", "params": { "multiplier": 3, "period": 14 } }
```
> 止損價 = 進場價 - 3 × ATR(14)

**trailing_stop** — 移動止盈
```json
{ "type": "trailing_stop", "params": { "activation_pct": 15, "trail_pct": 97 } }
```
> 漲幅達 15% 後啟動，若從峰值回落超過 3%（100% - 97% = 3%）則止盈

**ma_stop** — 均線交叉止損
```json
{ "type": "ma_stop", "params": { "fast": 20, "slow": 50 } }
```
> 快均線下穿慢均線且價格低於快均線時觸發

**fixed_stop** — 固定百分比止損
```json
{ "type": "fixed_stop", "params": { "stop_pct": 5 } }
```
> 從進場價跌 5% 就止損

**time_stop** — 持倉天數上限
```json
{ "type": "time_stop", "params": { "max_days": 20 } }
```

### 4.4 策略設計範例

**簡單均線策略**（MA Cross）：
```json
{
  "name": "Simple MA Cross",
  "entry": {
    "mode": "ALL",
    "conditions": [
      { "type": "ma_alignment",   "params": { "fast": 10, "slow": 20, "direction": "bullish" } },
      { "type": "price_above_ma", "params": { "period": 10 } }
    ]
  },
  "exit": {
    "mode": "ANY",
    "conditions": [
      { "type": "ma_stop",   "params": { "fast": 10, "slow": 20 } },
      { "type": "atr_stop",  "params": { "multiplier": 2, "period": 14 } },
      { "type": "time_stop", "params": { "max_days": 30 } }
    ]
  }
}
```

儲存為 `config/ma_cross.json`，執行：
```bash
python main.py --strategy config/ma_cross.json --bars 500 --output ma_result.json
```

---

## 5. 載入真實 CSV 數據

### 5.1 CSV 格式要求

最少需要這 6 個欄位（大小寫不敏感）：

```
date, open, high, low, close, volume
```

**支援的欄位別名：**

| 標準欄位 | 接受的別名 |
|---------|-----------|
| `date` | `Date`, `datetime`, `time`, `timestamp` |
| `open` | `Open`, `OPEN`, `o` |
| `high` | `High`, `HIGH`, `h` |
| `low` | `Low`, `LOW`, `l` |
| `close` | `Close`, `CLOSE`, `c`, `Adj Close` |
| `volume` | `Volume`, `VOLUME`, `Vol`, `vol`, `v` |

### 5.2 範例 CSV 格式

```csv
date,open,high,low,close,volume
2025-01-02,150.00,155.20,149.50,153.80,12500000
2025-01-03,153.80,158.00,152.10,156.50,11800000
2025-01-06,156.50,160.30,155.80,159.20,13200000
```

### 5.3 執行

```bash
python main.py --csv path/to/data.csv --output real_result.json
```

### 5.4 如果欄位名稱不在預設別名中

使用 Python API（在自己的腳本中）：
```python
from core.data_loader import load_from_csv

custom_map = {
    "date":   ["交易日期"],
    "open":   ["開盤"],
    "high":   ["最高"],
    "low":    ["最低"],
    "close":  ["收盤"],
    "volume": ["成交量"],
}
ohlcv = load_from_csv("tw_stock.csv", column_mapping=custom_map)
```

---

## 6. 使用網頁 GUI

### 6.1 啟動方式

不需要後端伺服器，直接用瀏覽器開啟：

```bash
# macOS
open gui/index.html

# Linux
xdg-open gui/index.html

# Windows
start gui/index.html
```

### 6.2 載入回測結果

1. 先產生 JSON 結果：
   ```bash
   python main.py --output result.json
   ```
2. 在 GUI 頁面點擊「選擇 JSON 檔案」，選取 `result.json`
3. 也可以直接把 JSON 檔案拖拉到頁面上

> **快速測試：** `gui/sample_result.json` 是內建的範例數據，可直接載入。

### 6.3 GUI 功能說明

| 頁籤 | 內容 |
|------|------|
| **總覽** | 8 個核心統計數字、出場原因分佈圖 |
| **K 線圖** | 互動式 K 線圖，含 SMA 線、進場/出場標記、成交量 |
| **交易記錄** | 所有交易的明細表格（點欄位標題可排序）|
| **統計驗證** | Monte Carlo 百分位、Monkey Test 排名、Walk-Forward 過擬合偵測 |
| **AI 診斷** | 問題交易的 K 線切片與診斷提示文字 |

### 6.4 K 線圖操作

- **滑鼠懸停：** 顯示該根 K 棒的 OHLCV 數值
- **綠色三角 ▲：** 進場點
- **紅色三角 ▼：** 出場點（附出場原因標籤）
- **藍色線：** SMA 20
- **橙色線：** SMA 50
- 底部灰色柱狀圖：成交量

---

## 7. 解讀統計驗證結果

### 7.1 Monte Carlo Simulation

**問題：「這個策略的績效是運氣還是真實優勢？」**

方法：把所有交易的損益隨機排列，重複 5,000 次，看看結果的分佈範圍。

```
Monte Carlo 結果範例：
  p50 return: 13.5%   ← 中位數（大多數情況下的報酬）
  ruin prob:   1.2%   ← 觸及 -30% 的機率
```

**如何解讀：**
- `p50` 接近你的實際 total_return → 結果相對穩健
- `ruin_probability` > 10% → 需要考慮降低倉位或縮緊止損
- `p5` 到 `p95` 的範圍很寬 → 結果波動大，受運氣影響較多

### 7.2 Monkey Test

**問題：「你的策略比隨機買賣好嗎？」**

方法：在同一份數據上，隨機選擇進場時間和持倉天數，重複 10,000 次，看你的策略排在哪個百分位。

```
Monkey Test 結果範例：
  percentile_rank: 74.5   ← 你的策略比 74.5% 的隨機策略好
  p_value: 0.255           ← > 0.05，不顯著（可能只是運氣）
  significant: False
```

**如何解讀：**
- `percentile_rank` > 90 且 `p_value` < 0.05 → 策略有統計顯著優勢
- `percentile_rank` 在 50~80 之間 → 中等，需要更多數據驗證
- `percentile_rank` < 50 → 比隨機還差，策略需要重新設計

### 7.3 Walk-Forward Analysis

**問題：「策略是否過擬合到歷史數據？」**

方法：用滾動窗口，在 in-sample 期間「使用」策略，在 out-of-sample 期間「驗證」。

```
Walk-Forward 結果範例：
  in_sample_avg_return:     8.2%   ← 樣本內平均報酬
  out_of_sample_avg_return: 2.1%   ← 樣本外平均報酬
  degradation_ratio:        0.26   ← 越接近 1 越好
  overfit_warning:          True   ← < 0.3 觸發警告
```

**如何解讀：**
- `degradation_ratio` > 0.7 → 優秀，樣本外表現接近樣本內
- `degradation_ratio` 0.3~0.7 → 尚可，有些過擬合
- `degradation_ratio` < 0.3 或 `overfit_warning: True` → 高過擬合風險，策略在真實交易中可能大幅退化

---

## 8. 自定義條件擴充

如果內建條件不夠用，可以實作自己的條件類別：

### 8.1 自定義進場條件範例

```python
# my_strategy.py
from core.strategy import validate_strategy, ALL_CONDITION_TYPES
from core.engine import run_backtest
from core.data_gen import generate
from output.summary import compute_summary
import json

# 1. 定義自定義條件類別
class RSIOversoldCondition:
    """RSI 超賣條件（收盤價連續 3 根下跌 > 3% 作為簡化版 RSI）"""
    def __init__(self, params: dict):
        self.lookback = params.get("lookback", 3)
        self.threshold = params.get("threshold", 0.03)

    def check(self, data: list, index: int, position: dict = None) -> bool:
        if index < self.lookback:
            return False
        for i in range(index - self.lookback + 1, index + 1):
            if (data[i]["close"] - data[i-1]["close"]) / data[i-1]["close"] > -self.threshold:
                return False
        return True

# 2. 註冊到允許的 type 清單
ALL_CONDITION_TYPES.add("rsi_oversold")

# 3. 定義策略設定
config = {
    "name": "RSI Oversold Bounce",
    "entry": {
        "mode": "ALL",
        "conditions": [
            { "type": "rsi_oversold", "params": { "lookback": 3, "threshold": 0.02 } },
            { "type": "ma_alignment", "params": { "fast": 20, "slow": 50, "direction": "bullish" } }
        ]
    },
    "exit": {
        "mode": "ANY",
        "conditions": [
            { "type": "atr_stop",      "params": { "multiplier": 2, "period": 14 } },
            { "type": "trailing_stop", "params": { "activation_pct": 8, "trail_pct": 97 } }
        ]
    }
}

# 4. 執行回測
ohlcv = generate(n=500, mode="random", seed=42)
custom_conditions = {
    "rsi_oversold": RSIOversoldCondition({"lookback": 3, "threshold": 0.02})
}
result = run_backtest(ohlcv, config, custom_conditions=custom_conditions)
result["summary"] = compute_summary(result["trades"])

print(f"交易數: {result['summary']['total_trades']}")
print(f"勝率: {result['summary']['win_rate']:.1f}%")
print(f"總報酬: {result['summary']['total_return_pct']:.2f}%")
```

執行：
```bash
python my_strategy.py
```

---

## 9. 常見問題

**Q: 回測結果為 0 筆交易，怎麼辦？**

A: 策略進場條件太嚴格。常見原因：
1. `volume_above_ma` 的 multiplier 設太高（試試 1.2 而非 1.5）
2. `ma_alignment` 要求的均線週期太長（試試 fast=10, slow=20）
3. 數據太少（建議至少 warmup_period × 3 根以上）
4. 試試 `--bars 1000` 增加數據量

**Q: 為什麼相同策略每次結果不同？**

A: 模擬數據有隨機性。加上 `--seed 42`（或任意固定數字）可確保每次結果完全一致。

**Q: `overfit_warning: True` 代表策略不能用嗎？**

A: 不一定。這只是警告，表示樣本內外表現差距較大。可能原因：
- 數據太少（走勢前後差異大）
- 策略本身具有趨勢跟隨特性，在區間市場會退化

建議用更多真實數據驗證，或調整參數降低策略的週期敏感度。

**Q: `p_value: 0.255` 代表策略沒用嗎？**

A: Monkey Test 的 p-value 不顯著（> 0.05）通常表示交易次數不夠多，統計功效不足。3~5 筆交易很難達到統計顯著性。需要累積更多交易記錄（建議至少 30 筆）才能做有意義的判斷。

**Q: 如何讓 GUI 顯示更多 K 線？**

A: 增加 `--bars` 參數，例如 `--bars 500`。注意 warmup_period（預設 50 根）的 K 線不會出現在 scan_log 中，因此圖表會從第 51 根開始。

**Q: CSV 載入失敗怎麼辦？**

A: 錯誤訊息會說明原因：
- `Missing required columns` → 欄位名稱不在預設別名中，需要用 `column_mapping` 參數手動指定
- `row N: missing values` → 第 N 行有空值，請清理數據後重試
