# OHLCV 策略回測驗證系統 — 使用教程

**版本：** v1.1  
**適合對象：** 初次使用者

---

## 目錄

1. [安裝與環境](#1-安裝與環境)
2. [第一次回測：30 秒快速上手](#2-第一次回測)
3. [了解輸出結果](#3-了解輸出結果)
4. [生成圖表](#4-生成圖表)
5. [策略比較](#5-策略比較)
6. [設計你自己的策略](#6-設計你自己的策略)
7. [多倉位策略](#7-多倉位策略)
8. [載入真實 CSV 數據](#8-載入真實-csv-數據)
9. [解讀統計驗證結果](#9-解讀統計驗證結果)
10. [自定義條件擴充](#10-自定義條件擴充)
11. [常見問題](#11-常見問題)

---

## 1. 安裝與環境

### 需求

- Python 3.10 以上
- pytest（執行測試用）
- matplotlib（生成圖表用）

### 建立虛擬環境（推薦）

```bash
git clone <repo-url>
cd stock_test

# 一鍵建立虛擬環境並安裝所有相依
bash setup.sh
source venv/bin/activate
```

或手動安裝：

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 確認環境正常

```bash
python -m pytest tests/ -q
# 預期輸出：123 passed, 1 skipped
```

---

## 2. 第一次回測

### 最簡單的執行方式

```bash
python main.py
```

這會：
1. 生成 500 根模擬 K 棒（bull 模式，seed=42）
2. 用內建的「趨勢突破 v1」策略執行回測
3. 在終端機列印結果摘要
4. 同時執行 Monte Carlo、Monkey Test、Walk-Forward 驗證

**終端機輸出範例：**
```
[1/4] Generating simulated data (mode=bull, bars=500, seed=42)
      Loaded 500 bars (2026-01-01 → 2027-05-15)
[2/4] Loading strategy from: config/strategy_config.json
      Strategy: Trend Following Breakout v1
[3/4] Running backtest...
      Trades:        7
      Win rate:      85.7%
      Total return:  118.81%
      Max drawdown:  -6.95%
      Profit factor: 18.1058
      Sharpe ratio:  1.28
[4/4] Running statistical validation...
      Monte Carlo p50 return: 118.81%  ruin prob: 0.0%
      Monkey Test rank: 100.0th percentile  p-value: 0.000  significant: True
      Walk-Forward folds: 13  degradation: 0.0  overfit warning: True
```

### 常用指令範例

```bash
# 指定市場模式與 K 棒數
python main.py --mode bear --bars 1000 --seed 99

# 儲存結果到 JSON
python main.py --output results.json

# 快速跑，不做統計驗證
python main.py --no-validation

# 用自訂策略
python main.py --strategy config/my_strategy.json
```

### 完整旗標一覽

| 旗標 | 預設值 | 說明 |
|------|--------|------|
| `--mode` | `bull` | 市場模式：`random` / `bull` / `bear` / `choppy` / `diverge` |
| `--bars` | `500` | K 棒數量 |
| `--seed` | `42` | 隨機種子（相同種子每次結果一致）|
| `--csv` | — | 使用真實 CSV 數據（見第 8 節）|
| `--strategy` | `config/strategy_config.json` | 策略設定檔路徑 |
| `--output` | — | 儲存完整結果到 JSON 檔案 |
| `--chart` | — | 配合 `--output`，同時生成 PNG 圖表 |
| `--to-image` | — | 將現有 JSON 轉成 PNG 圖表 |
| `--image-out` | — | 圖表輸出路徑（預設同 JSON 名稱）|
| `--compare` | — | 並列比較 4 種內建策略 |
| `--no-validation` | — | 跳過統計驗證（加快速度）|
| `--mc-sims` | `5000` | Monte Carlo 模擬次數 |
| `--mt-sims` | `10000` | Monkey Test 模擬次數 |

---

## 3. 了解輸出結果

### 3.1 終端機摘要

| 欄位 | 說明 |
|------|------|
| Trades | 總交易次數 |
| Win rate | 勝率（獲利交易 / 總交易）|
| Total return | 累計報酬（所有交易 PnL% 加總）|
| Max drawdown | 最大回撤（累計損益曲線的最深谷底）|
| Profit factor | 毛利 / 毛損（> 1 代表整體獲利）|
| Sharpe ratio | 夏普比率（風險調整後報酬）|

### 3.2 JSON 輸出結構

```
results.json
├── metadata       → 策略名稱、數據範圍、warmup 期數等
├── trades         → 每一筆交易的完整記錄
├── scan_log       → 逐根 K 棒掃描日誌
├── summary        → 統計摘要（勝率、期望值、最大回撤等）
└── validation     → Monte Carlo / Monkey Test / Walk-Forward 結果
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
  "exit_reason": "trailing_stop",
  "bars_held": 20,
  "pnl_pct": 10.07,
  "peak_price": 118.50,
  "max_drawdown_during_trade": -2.3
}
```

**出場原因說明：**

| exit_reason | 意義 |
|-------------|------|
| `atr_stop` | ATR 倍數止損觸發 |
| `ma_stop` | 均線交叉止損觸發 |
| `trailing_stop` | 移動止盈觸發 |
| `fixed_stop` | 固定百分比止損觸發 |
| `time_stop` | 持倉天數上限到期 |
| `end_of_data` | 數據結束時強制平倉 |

### 3.4 掃描日誌（scan_log）

每根 K 棒一筆記錄，持倉中的範例：

```json
{
  "index": 110,
  "date": "2026-04-21",
  "ohlcv": { "open": 112.3, "high": 114.1, "low": 111.5, "close": 113.8, "volume": 13500 },
  "indicators": { "sma_20": 109.2, "sma_50": 105.8, "atr_14": 2.4 },
  "entry_triggered": false,
  "positions": [
    {
      "trade_id": 1,
      "entry_price": 105.20,
      "current_pnl_pct": 8.17,
      "peak_price": 114.1,
      "bars_held": 9
    }
  ],
  "exit_triggered": false,
  "exit_reason": null,
  "exits_this_bar": []
}
```

> `positions` 是陣列，支援多倉位同時持有（見第 7 節）。

---

## 4. 生成圖表

需要 matplotlib（已包含在 `requirements.txt`）。

### 方法一：回測時同時生成

```bash
python main.py --output results.json --chart
# 自動生成 results.png
```

### 方法二：轉換現有 JSON

```bash
python main.py --to-image results.json
# 生成 results.png（同目錄）

python main.py --to-image results.json --image-out my_chart.png
# 指定輸出路徑
```

### 圖表內容

生成的 PNG 包含 4 個區塊：

| 區塊 | 說明 |
|------|------|
| **Equity Curve** | 累積損益折線圖，綠色填充為獲利，紅色為虧損 |
| **Per-trade PnL** | 每筆交易損益柱狀圖 |
| **Exit Reason Breakdown** | 各出場原因占比橫條圖 |
| **Summary Statistics** | 12 個核心統計數字 |

---

## 5. 策略比較

用 `--compare` 旗標可同時跑 4 種內建策略並排比較：

```bash
# 比較全部 4 種市場模式
python main.py --compare

# 只比較特定市場
python main.py --compare --mode choppy

# 自訂 K 棒數
python main.py --compare --bars 1000 --seed 99
```

**輸出範例：**

```
Strategy               Mode     #    WR%     Ret%      DD%       PF      Sharpe
Trend Breakout         bull     7    85.7%   118.8%    -6.9%     18.1    1.3
MA Crossover           bull     2    100.0%  395.5%    0.0%      None    1.4
RSI Rebound            bull     0    0.0%    0.0%      0.0%      —       0.0
Momentum               bull     11   81.8%   167.1%    -5.1%     17.9    1.0
```

**四種內建策略說明：**

| 策略 | 進場條件 | 出場條件 | 適合市場 |
|------|---------|---------|---------|
| **Trend Breakout** | 20日高點突破 + 量能 + 均線排列 | ATR止損 / 均線止損 / 移動止盈 | 多頭趨勢 |
| **MA Crossover** | SMA20 > SMA50 + 價格站上均線 | 均線死叉 / ATR止損 | 趨勢明確 |
| **RSI Rebound** | RSI-14 < 30 | RSI > 50 / ATR止損 | 震盪逆勢 |
| **Momentum** | 20日高點突破 + 價格在SMA50之上 | 移動止盈 / ATR止損 | 強勢多頭 |

---

## 6. 設計你自己的策略

### 6.1 策略設定格式

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

- `mode = "ALL"`：所有條件同時滿足
- `mode = "ANY"`：任一條件滿足即可

### 6.2 內建進場條件

**breakout** — 收盤價突破 N 日最高點
```json
{ "type": "breakout", "params": { "period": 20, "field": "high" } }
```

**volume_above_ma** — 成交量超過 N 日均量的 M 倍
```json
{ "type": "volume_above_ma", "params": { "multiplier": 1.2, "period": 20 } }
```

**ma_alignment** — 快均線在慢均線之上
```json
{ "type": "ma_alignment", "params": { "fast": 20, "slow": 50, "direction": "bullish" } }
```

**price_above_ma** — 收盤價高於均線
```json
{ "type": "price_above_ma", "params": { "period": 20 } }
```

### 6.3 內建出場條件

**atr_stop** — ATR 倍數止損
```json
{ "type": "atr_stop", "params": { "multiplier": 3, "period": 14 } }
```
> 止損價 = 進場價 - multiplier × ATR(period)

**trailing_stop** — 移動止盈
```json
{ "type": "trailing_stop", "params": { "activation_pct": 15, "trail_pct": 97 } }
```
> 漲幅達 15% 後啟動，從峰值回落超過 3% 即止盈

**ma_stop** — 均線交叉止損
```json
{ "type": "ma_stop", "params": { "fast": 20, "slow": 50 } }
```

**fixed_stop** — 固定百分比止損
```json
{ "type": "fixed_stop", "params": { "stop_pct": 5 } }
```

**time_stop** — 持倉天數上限
```json
{ "type": "time_stop", "params": { "max_days": 20 } }
```

### 6.4 範例：簡單均線策略

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

```bash
python main.py --strategy config/ma_cross.json --bars 500 --output result.json --chart
```

---

## 7. 多倉位策略

預設引擎每次只持有 1 個倉位。設定 `max_positions` 可同時持有多個：

```json
{
  "name": "多倉策略",
  "max_positions": 5,
  "entry": { ... },
  "exit": { ... }
}
```

**應用場景：**
- **網格策略**：在不同價位同時持有多個買入倉位
- **金字塔加碼**：趨勢中多次加碼
- **分批建倉**：分多次進場降低成本

示範腳本：

```bash
# 網格策略示範（8 格，±10% 區間）
python run_grid.py

# 海龜策略示範（System 1：20日突破 + 10日低點出場 + 2x ATR止損）
python run_turtle.py
```

`scan_log` 中的 `positions` 欄位會包含當下所有開倉的狀態：

```json
"positions": [
  { "trade_id": 1, "entry_price": 100.0, "current_pnl_pct": 5.2, "bars_held": 10 },
  { "trade_id": 2, "entry_price": 95.0,  "current_pnl_pct": 10.8, "bars_held": 5 }
]
```

---

## 8. 載入真實 CSV 數據

### 8.1 CSV 格式要求

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

### 8.2 執行

```bash
python main.py --csv path/to/data.csv --output result.json --chart
```

### 8.3 自訂欄位對應

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

## 9. 解讀統計驗證結果

### 9.1 Monte Carlo Simulation

**問題：「這個策略的績效是運氣還是真實優勢？」**

把所有交易的損益隨機排列，重複 5,000 次，看結果的分佈。

```
Monte Carlo 結果範例：
  p5  return: 118.8%   ← 最差 5% 情境
  p50 return: 118.8%   ← 中位數
  p95 return: 118.8%   ← 最好 5% 情境
  ruin prob:    0.0%   ← 觸及 -30% 的機率
```

**解讀：**
- `p50` 接近實際 total_return → 結果相對穩健
- `ruin_probability` > 10% → 需要考慮降低倉位或縮緊止損
- `p5` 到 `p95` 範圍很寬 → 受運氣影響較多

### 9.2 Monkey Test

**問題：「你的策略比隨機買賣好嗎？」**

在同一份數據上，隨機選擇進場時間和持倉天數，重複 10,000 次比較。

```
Monkey Test 結果範例：
  percentile_rank: 100.0   ← 優於 100% 的隨機策略
  p_value:           0.000 ← < 0.05，具統計顯著性
  significant:        True
```

**解讀：**
- `percentile_rank` > 90 且 `p_value` < 0.05 → 策略有統計顯著優勢
- `percentile_rank` 50~90 → 中等，需更多數據驗證
- `percentile_rank` < 50 → 比隨機還差，需重新設計

### 9.3 Walk-Forward Analysis

**問題：「策略是否過擬合到歷史數據？」**

用滾動窗口，在樣本內使用策略，在樣本外驗證。

```
Walk-Forward 結果範例：
  in_sample_avg_return:     8.2%
  out_of_sample_avg_return: 2.1%
  degradation_ratio:        0.26
  overfit_warning:          True
```

**解讀：**
- `degradation_ratio` > 0.7 → 優秀，樣本外接近樣本內
- `degradation_ratio` 0.3~0.7 → 尚可，有些過擬合
- `degradation_ratio` < 0.3 或 `overfit_warning: True` → 高過擬合風險

---

## 10. 自定義條件擴充

### 10.1 實作自訂條件

```python
from core.strategy import ALL_CONDITION_TYPES
from core.engine import run_backtest
from core.data_gen import generate
from output.summary import compute_summary

# 1. 定義條件類別
class RSICondition:
    def __init__(self, params: dict):
        self.period    = params.get("period", 14)
        self.threshold = params.get("threshold", 30)

    def check(self, ohlcv: list, index: int, position: dict = None) -> bool:
        if index < self.period:
            return False
        closes = [b["close"] for b in ohlcv[:index+1]]
        # 計算 RSI...（簡化示意）
        return closes[-1] < closes[-self.period] * (1 - self.threshold / 100)

# 2. 註冊到允許的 type 清單
ALL_CONDITION_TYPES.add("rsi_entry")

# 3. 定義策略設定
config = {
    "name": "Custom RSI Strategy",
    "entry": {
        "mode": "ALL",
        "conditions": [
            { "type": "rsi_entry", "params": { "period": 14, "threshold": 30 } }
        ]
    },
    "exit": {
        "mode": "ANY",
        "conditions": [
            { "type": "atr_stop", "params": { "multiplier": 2, "period": 14 } }
        ]
    }
}

# 4. 執行回測
ohlcv = generate(n=500, mode="random", seed=42)
result = run_backtest(ohlcv, config, custom_conditions={
    "rsi_entry": RSICondition({"period": 14, "threshold": 30})
})
result["summary"] = compute_summary(result["trades"])
print(f"交易數: {result['summary']['total_trades']}")
```

### 10.2 完整實作範例

參考 `run_turtle.py`（自訂 `LowestLowExit`）和 `run_grid.py`（自訂 `GridEntryCondition` / `GridExitCondition`）。

---

## 11. 常見問題

**Q: 回測結果為 0 筆交易，怎麼辦？**

A: 策略進場條件太嚴格。常見原因：
1. `volume_above_ma` 的 multiplier 設太高（模擬數據建議用 1.2 以內）
2. 數據太少，試試 `--bars 1000`
3. `ma_alignment` 要求的均線週期太長

**Q: 為什麼相同策略每次結果不同？**

A: 模擬數據有隨機性。加上 `--seed 42` 可確保每次結果完全一致。

**Q: `overfit_warning: True` 代表策略不能用嗎？**

A: 不一定。這只是警告，表示樣本內外表現差距較大。建議用更多真實數據驗證，或調整參數降低週期敏感度。

**Q: `p_value: 0.255` 代表策略沒用嗎？**

A: Monkey Test p-value 不顯著通常是交易次數太少（< 30 筆），統計功效不足，不代表策略無效。

**Q: CSV 載入失敗怎麼辦？**

A: 錯誤訊息會說明原因：
- `Missing required columns` → 欄位名稱不在預設別名中，需用 `column_mapping` 手動指定
- `row N: missing values` → 第 N 行有空值，清理數據後重試

**Q: 如何同時持有多個倉位？**

A: 在策略 JSON 中加入 `"max_positions": N`，然後搭配自訂條件實作多倉邏輯。參考 `run_grid.py`。
