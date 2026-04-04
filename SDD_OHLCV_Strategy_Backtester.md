# OHLCV 策略回測驗證系統 — Software Design Document (SDD)

**版本：** v1.1  
**日期：** 2026-04-04  
**狀態：** Updated

---

## 1. 系統概述

### 1.1 目的

本系統是一個基於 OHLCV（Open, High, Low, Close, Volume）數據的交易策略回測與驗證平台。它不是一個固定策略的執行器，而是一個通用的**策略驗證器** — 使用者可以透過內建介面設定或載入自定義策略，在模擬或真實歷史數據上執行回測，並透過結構化輸出與統計驗證工具來判斷策略的有效性。

### 1.2 範圍

- OHLCV 數據生成與載入（模擬 / 真實數據源）
- 策略定義介面（進場條件 + 出場機制）
- 回測引擎（逐根 K 棒運算）
- 結構化輸出（JSON 格式）
- 統計驗證工具（Monte Carlo Simulation, Monkey Test, Overfitting Detection）
- AI 診斷介面（摘要 + OHLCV 切片輸出）

### 1.3 讀者

- 開發者（人或 AI）：依據本文件實作系統
- 使用者本人：作為後續開發與迭代的對照基準

---

## 2. 系統架構

### 2.1 三層架構

系統採用三層分離設計，核心原則是**核心運算層完全不依賴 DOM 或任何 UI 框架**，確保可在 Node.js / Python 環境直接執行與測試。

| 層級 | 名稱 | 職責 | 技術選型 |
|------|------|------|----------|
| Core | 核心運算層 | 數據處理、指標計算、策略執行、回測引擎 | Python（純函式） |
| Output | 輸出層 | 將回測結果序列化為 JSON，產生摘要與 OHLCV 切片 | Python（JSON 序列化） |
| Consumer | 消費層 | 讀取 JSON 進行視覺化、報表、AI 診斷 | 可替換（CLI / 網頁 / AI） |

### 2.2 模組結構

```
stock_test/
├── core/
│   ├── data_gen.py          # 模擬數據生成
│   ├── data_loader.py       # 真實數據載入介面
│   ├── indicators.py        # 技術指標計算（SMA, ATR, Highest/Lowest 等）
│   ├── pattern.py           # K 棒型態辨識
│   ├── strategy.py          # 策略定義與介面
│   └── engine.py            # 回測引擎（支援多倉位）
├── output/
│   ├── serializer.py        # JSON 結構化輸出
│   ├── summary.py           # 統計摘要生成
│   ├── slicer.py            # OHLCV 切片擷取（供 AI 診斷）
│   └── chart.py             # PNG 圖表生成（matplotlib）
├── validation/
│   ├── monte_carlo.py       # Monte Carlo Simulation
│   ├── monkey_test.py       # Monkey Test（隨機策略對照）
│   └── overfit_detect.py    # Overfitting Detection（Walk-Forward）
├── config/
│   ├── strategy_config.json # 預設策略（趨勢突破 v1）
│   └── turtle_strategy.json # 海龜策略設定（System 1）
├── tests/
│   ├── unit/                # 單元測試
│   └── integration/         # 整合測試
├── main.py                  # 入口點（含所有 CLI 旗標）
├── run_compare.py           # 四策略比較示範腳本
├── run_turtle.py            # 海龜策略示範腳本
├── run_grid.py              # 網格策略示範腳本
├── requirements.txt         # 相依套件
└── setup.sh                 # 一鍵建立虛擬環境
```

### 2.3 數據流

```
數據源（模擬 / 真實）
    ↓
  [OHLCV 陣列]
    ↓
  core/indicators.py → 計算 SMA, ATR, 均量等衍生指標
    ↓
  core/engine.py → 逐根掃描，套用策略規則，產生交易紀錄
    ↓
  output/serializer.py → 結構化 JSON 輸出
    ↓
  ┌─────────────────────────────────┐
  │ validation/ → 統計驗證          │
  │ output/summary.py → 摘要        │
  │ output/slicer.py → OHLCV 切片   │
  │ Consumer（CLI / 網頁 / AI）     │
  └─────────────────────────────────┘
```

---

## 3. 核心模組設計

### 3.1 數據層

#### 3.1.1 OHLCV 數據結構

每根 K 棒的標準格式：

```json
{
  "date": "2026-03-15",
  "open": 105.20,
  "high": 108.50,
  "low": 104.30,
  "close": 107.80,
  "volume": 12500
}
```

系統內部統一使用此格式的陣列（`List[Dict]`）作為數據傳遞的標準。

#### 3.1.2 模擬數據生成（data_gen.py）

- **輸入：** 天數、市場模式（random / bull / bear / choppy / diverge）
- **輸出：** OHLCV 陣列
- **邏輯：** 基於前一根收盤價加上隨機偏移量與趨勢 drift 產生下一根，成交量根據價格波動幅度加權

#### 3.1.3 真實數據載入（data_loader.py）

- **輸入：** 檔案路徑（CSV / JSON）或 API 端點
- **輸出：** 標準 OHLCV 陣列
- **職責：** 處理不同數據源的格式差異，統一轉換為系統標準格式
- **預留介面：** `load_from_csv(path)`, `load_from_json(path)`, `load_from_api(endpoint, params)`

### 3.2 指標計算層（indicators.py）

所有函式皆為**純函式** — 輸入數值陣列，輸出數值陣列，無副作用。

| 函式 | 輸入 | 輸出 | 說明 |
|------|------|------|------|
| `sma(data, period)` | 收盤價陣列, 週期 | 數值陣列（前 period-1 為 None） | Simple Moving Average |
| `atr(ohlcv, period)` | OHLCV 陣列, 週期 | 數值陣列 | Average True Range |
| `volume_ma(volumes, period)` | 成交量陣列, 週期 | 數值陣列 | 成交量移動平均 |
| `highest_high(highs, period)` | 最高價陣列, 週期 | 數值陣列 | N 日最高價 |

### 3.3 策略定義介面（strategy.py）

策略採用**宣告式設定**，使用者不需要寫程式碼，透過 JSON 設定檔或內建介面定義策略。

#### 3.3.1 策略設定結構

```json
{
  "name": "Trend Following Breakout v1",
  "max_positions": 1,
  "entry": {
    "mode": "ALL",
    "conditions": [
      { "type": "breakout", "params": { "period": 20, "field": "high" } },
      { "type": "volume_above_ma", "params": { "multiplier": 1.5, "period": 20 } },
      { "type": "ma_alignment", "params": { "fast": 20, "slow": 50, "direction": "bullish" } },
      { "type": "price_above_ma", "params": { "period": 20 } }
    ]
  },
  "exit": {
    "mode": "ANY",
    "conditions": [
      { "type": "atr_stop", "params": { "multiplier": 3, "period": 14 } },
      { "type": "ma_stop", "params": { "fast": 20, "slow": 50 } },
      { "type": "trailing_stop", "params": { "activation_pct": 15, "trail_pct": 97 } }
    ]
  }
}
```

- `entry.mode`：`ALL` 表示所有條件同時滿足才進場；`ANY` 表示任一滿足即可
- `exit.mode`：`ANY` 表示任一出場條件觸發即出場；`ALL` 表示全部觸發才出場
- 每個 condition 的 `type` 對應一個內建的條件檢查函式

#### 3.3.2 內建條件類型

**進場條件：**

| type | 說明 | 參數 |
|------|------|------|
| `breakout` | 價格突破 N 日高/低點 | `period`, `field`（high/low） |
| `volume_above_ma` | 成交量超過均量 N 倍 | `multiplier`, `period` |
| `ma_alignment` | 均線多頭/空頭排列 | `fast`, `slow`, `direction` |
| `price_above_ma` | 價格高於/低於指定均線 | `period`, `direction`（above/below） |
| `pattern` | K 棒型態觸發 | `pattern_name`, `lookback` |

**出場條件：**

| type | 說明 | 參數 |
|------|------|------|
| `atr_stop` | ATR 倍數止損 | `multiplier`, `period` |
| `ma_stop` | 均線交叉止損 | `fast`, `slow` |
| `trailing_stop` | 移動止盈 | `activation_pct`, `trail_pct` |
| `fixed_stop` | 固定百分比止損 | `stop_pct` |
| `time_stop` | 持倉天數上限 | `max_days` |

#### 3.3.3 自定義條件擴充

使用者可透過實作標準介面新增條件：

```python
class CustomCondition:
    def __init__(self, params: dict):
        self.params = params

    def check(self, data: list, index: int, position: dict = None) -> bool:
        """
        data: OHLCV 陣列（含已計算的衍生指標）
        index: 當前 K 棒索引
        position: 當前持倉資訊（出場條件用），None 表示未持倉
        return: True 表示條件觸發
        """
        pass
```

### 3.4 回測引擎（engine.py）

#### 3.4.1 核心邏輯

```
輸入：OHLCV 陣列 + 策略設定
輸出：逐根掃描日誌 + 交易明細

for each bar (index = warmup_period to end):
    計算當根所需的衍生指標值
    
    if 未持倉:
        逐一檢查進場條件，記錄每個條件的 True/False
        if 所有進場條件滿足:
            建立持倉，記錄進場價格與相關止損價位
    
    if 持倉中:
        更新持倉狀態（peak price, trailing stop 等）
        逐一檢查出場條件，記錄每個條件的觸發狀態與距離
        if 任一出場條件觸發:
            平倉，記錄出場價格、原因、損益
```

#### 3.4.2 Warmup Period

回測引擎在前 N 根（N = 策略所需最長指標週期）不進行交易判斷，僅累積指標計算所需的數據。例如策略使用 MA50，則前 50 根只計算指標不做交易。

#### 3.4.3 逐根掃描日誌結構

每根 K 棒產生一筆掃描紀錄：

```json
{
  "index": 55,
  "date": "2026-03-15",
  "ohlcv": { "open": 105.2, "high": 108.5, "low": 104.3, "close": 107.8, "volume": 12500 },
  "indicators": {
    "sma_20": 103.5,
    "sma_50": 101.2,
    "atr_14": 2.8,
    "volume_ma_20": 9800,
    "highest_high_20": 106.0
  },
  "entry_conditions": {
    "breakout": { "result": true, "detail": "close 107.8 > highest_high_20 106.0" },
    "volume_above_ma": { "result": true, "detail": "vol 12500 > 9800 * 1.5 = 14700 → false" },
    "ma_alignment": { "result": true, "detail": "sma_20 103.5 > sma_50 101.2" },
    "price_above_ma": { "result": true, "detail": "close 107.8 > sma_20 103.5" }
  },
  "entry_triggered": false,
  "positions": [],
  "exit_triggered": false,
  "exit_reason": null,
  "exits_this_bar": []
}
```

持倉中的掃描紀錄會額外包含（支援多倉位）：

```json
{
  "positions": [
    {
      "trade_id": 1,
      "entry_price": 107.8,
      "entry_index": 55,
      "current_pnl_pct": 2.3,
      "peak_price": 112.5,
      "bars_held": 8
    }
  ],
  "exit_triggered": false,
  "exit_reason": null,
  "exits_this_bar": []
}
```

> **v1.1 變更：** `position`（單一物件）改為 `positions`（陣列），支援 `max_positions > 1` 的多倉位策略。`exit_conditions` 欄位已從 scan_log 移除。
```

### 3.5 K 棒型態辨識（pattern.py）

純函式模組，輸入 OHLCV 陣列與當前索引，輸出型態辨識結果。

#### 3.5.1 內建型態

| 型態 | 所需根數 | 判定邏輯摘要 |
|------|----------|-------------|
| 錘子線（Hammer） | 1 | 下影線 > 2x 實體，上影線 < 0.3x 實體 |
| 吞噬（Engulfing） | 2 | 後一根實體完全包覆前一根實體，方向相反 |
| 十字星（Doji） | 1 | 實體 < 總長的 15% |
| 晨星（Morning Star） | 3 | 長黑 + 小實體（含缺口）+ 長紅 |
| 放量長紅/長黑 | 1 | 實體 > 總長 60% 且成交量 > 1.5x 均量 |

每個型態函式回傳：

```json
{
  "detected": true,
  "pattern": "engulfing_bullish",
  "confidence": 0.85,
  "detail": "bar[i] body fully covers bar[i-1], bullish reversal"
}
```

---

## 4. 輸出層設計

### 4.1 圖表生成（chart.py）

`output/chart.py` 將回測結果渲染為 PNG 圖表（需要 matplotlib）。

- **輸入：** 回測結果 dict 或 JSON 檔案路徑
- **輸出：** 深色主題 PNG（1400×1000px，150 DPI）
- **內容：** 4 個區塊 — 累積損益曲線、每筆交易損益、出場原因分布、統計摘要表

CLI 用法：
```bash
python main.py --output results.json --chart      # 回測同時生成圖表
python main.py --to-image results.json            # 轉換已存在的 JSON
```

### 4.2 JSON 輸出結構（serializer.py）

回測完成後輸出的完整 JSON 結構：

```json
{
  "metadata": {
    "strategy_name": "Trend Following Breakout v1",
    "data_source": "simulated",
    "data_range": { "start": "2026-01-01", "end": "2026-07-15" },
    "total_bars": 200,
    "warmup_period": 50,
    "params": { "...策略參數完整副本..." }
  },
  "trades": [
    {
      "id": 1,
      "entry_index": 55,
      "entry_date": "2026-03-15",
      "entry_price": 107.8,
      "exit_index": 72,
      "exit_date": "2026-04-01",
      "exit_price": 115.2,
      "exit_reason": "trailing_stop",
      "bars_held": 17,
      "pnl_pct": 6.86,
      "pnl_abs": 7.4,
      "peak_price": 118.9,
      "max_drawdown_during_trade": -3.1
    }
  ],
  "scan_log": [ "...逐根掃描日誌（完整版）..." ],
  "summary": { "...統計摘要（見 4.2）..." }
}
```

### 4.2 統計摘要（summary.py）

```json
{
  "total_trades": 12,
  "winning_trades": 7,
  "losing_trades": 5,
  "win_rate": 58.3,
  "avg_win_pct": 8.5,
  "avg_loss_pct": -3.2,
  "profit_factor": 2.66,
  "expectancy_pct": 3.35,
  "max_consecutive_wins": 4,
  "max_consecutive_losses": 3,
  "max_drawdown_pct": -12.5,
  "total_return_pct": 42.1,
  "sharpe_ratio": 1.85,
  "avg_bars_held": 15,
  "avg_bars_held_win": 18,
  "avg_bars_held_loss": 9,
  "exit_reason_breakdown": {
    "atr_stop": 3,
    "ma_stop": 2,
    "trailing_stop": 7
  }
}
```

### 4.3 AI 診斷切片（slicer.py）

用於將問題交易的上下文 OHLCV 切片擷取出來，供 AI 進行具體診斷。

- **輸入：** 交易明細 + 完整 OHLCV 陣列 + 切片參數（前後各 N 根）
- **輸出：** 包含該筆交易前後 context 的 OHLCV 子集 + 該區間的指標值

```json
{
  "trade_id": 3,
  "context_range": { "start_index": 70, "end_index": 100 },
  "ohlcv_slice": [ "...15 根 OHLCV..." ],
  "indicators_slice": { "sma_20": [...], "atr_14": [...] },
  "entry_scan": { "...進場當根的完整掃描紀錄..." },
  "exit_scan": { "...出場當根的完整掃描紀錄..." },
  "diagnosis_prompt": "此筆交易虧損 -8.2%，進場於突破後第 1 根，出場原因為 ATR 止損。請分析進場時的量價狀態是否支持突破有效性，以及止損設定是否合理。"
}
```

#### 4.3.1 自動篩選邏輯

`slicer.py` 內建以下自動篩選規則，用於從所有交易中挑選「最值得診斷」的交易：

1. 虧損最大的 N 筆交易
2. 持倉時間最短的 N 筆（可能是假突破）
3. 最大回撤期間的所有交易
4. 進場條件中有任一條件接近臨界值的交易

---

## 5. 統計驗證模組

### 5.1 Monte Carlo Simulation（monte_carlo.py）

- **輸入：** 交易明細（trades 陣列）、模擬次數（預設 5,000）
- **方法：** 將交易結果序列隨機 shuffle，每次重新計算累計損益曲線
- **輸出：**

```json
{
  "simulations": 5000,
  "percentiles": {
    "p5": { "total_return": 12.3, "max_drawdown": -22.1 },
    "p25": { "total_return": 28.5, "max_drawdown": -15.3 },
    "p50": { "total_return": 41.8, "max_drawdown": -12.5 },
    "p75": { "total_return": 55.2, "max_drawdown": -9.8 },
    "p95": { "total_return": 72.1, "max_drawdown": -6.2 }
  },
  "ruin_probability": 2.3,
  "ruin_threshold": -30.0
}
```

- `ruin_probability`：權益曲線觸及 `ruin_threshold` 的機率百分比

### 5.2 Monkey Test（monkey_test.py）

- **輸入：** 原始 OHLCV 陣列、隨機策略次數（預設 10,000）、持倉天數範圍
- **方法：** 每次隨機選擇進場時間點、隨機決定持倉天數，計算損益。重複 N 次產生隨機策略的績效分佈
- **輸出：**

```json
{
  "random_simulations": 10000,
  "random_distribution": {
    "mean_return": 0.8,
    "std_return": 15.2,
    "p5": -25.3,
    "p95": 28.1
  },
  "strategy_return": 42.1,
  "percentile_rank": 96.5,
  "p_value": 0.035,
  "significant": true
}
```

- `percentile_rank`：你的策略在隨機分佈中的排名百分位
- `p_value`：策略績效顯著優於隨機的 p 值（< 0.05 視為顯著）

### 5.3 Overfitting Detection（overfit_detect.py）

- **輸入：** 完整 OHLCV 陣列、策略參數搜尋空間、分割比例
- **方法 A — Train/Test Split：** 前 70% 數據上做參數最佳化，後 30% 用最佳參數直接跑
- **方法 B — Walk-Forward Analysis：** 滾動窗口，每次用固定長度的 in-sample 調參，在 out-of-sample 測試

**Walk-Forward 輸出：**

```json
{
  "method": "walk_forward",
  "window_size": 100,
  "step_size": 30,
  "folds": [
    {
      "fold": 1,
      "in_sample": { "start": 0, "end": 99, "best_params": {...}, "return": 35.2 },
      "out_of_sample": { "start": 100, "end": 129, "return": 8.1 }
    }
  ],
  "in_sample_avg_return": 32.5,
  "out_of_sample_avg_return": 5.8,
  "degradation_ratio": 0.18,
  "overfit_warning": true
}
```

- `degradation_ratio`：out-of-sample 績效 / in-sample 績效，越接近 1 越好，< 0.3 通常為過擬合警訊

---

## 6. AI 診斷流程

### 6.1 三輪診斷協議

| 輪次 | 輸入給 AI 的內容 | AI 的輸出 | 預估 Token 量 |
|------|------------------|----------|--------------|
| 第一輪 | `summary.json`（統計摘要） | 整體問題方向判斷 | ~2,000 |
| 第二輪 | 問題交易的 OHLCV 切片（由 slicer.py 自動篩選） | 具體進出場診斷與改善建議 | ~5,000 |
| 第三輪 | 特定市況區間的所有訊號（依第二輪結論篩選） | 策略在該市況下的系統性問題分析 | ~8,000 |

### 6.2 Token 預算控制

- 每輪的 OHLCV 切片上限：單筆交易前後各 15 根，最多同時提供 3 筆交易
- 完整的逐根掃描日誌**不**直接傳給 AI，僅傳送問題交易的相關掃描紀錄
- 統計摘要固定在 500 token 以內

---

## 7. 技術規格

### 7.1 語言與環境

| 項目 | 選型 |
|------|------|
| 核心語言 | Python 3.10+ |
| 數據格式 | JSON |
| 測試框架 | pytest |
| 設定格式 | JSON |
| 版本控制 | Git |

### 7.2 效能需求

| 場景 | 預期表現 |
|------|----------|
| 200 天模擬數據生成 | < 10ms |
| 單次回測（200 天） | < 50ms |
| Monte Carlo 5,000 次 | < 2s |
| Monkey Test 10,000 次 | < 5s |
| Walk-Forward 10 folds | < 10s |

### 7.3 相依性

核心運算層僅使用 Python 標準庫（`json`, `math`, `random`, `statistics`, `csv`），不依賴任何第三方套件。這確保在任何環境都能直接執行。

相依套件（`requirements.txt`）：
- `pytest>=7.0`：測試框架
- `matplotlib>=3.7`：PNG 圖表生成（`output/chart.py` 使用）

---

## 8. 未來擴充

以下為已規劃但不在 v1.0 範圍內的功能，系統架構已預留擴充點：

### v1.1 已實作

- **多倉位支援：** `max_positions` 設定值，engine.py 使用 `positions[]` 管理多個同時開倉（用於網格、加碼策略）
- **圖表生成：** `output/chart.py` 輸出深色主題 PNG 報表
- **策略比較：** `--compare` 旗標，一次比較 4 種內建策略
- **示範腳本：** `run_turtle.py`（海龜）、`run_grid.py`（網格）、`run_compare.py`（策略比較）

### 後續規劃

- **多標的同時回測：** engine.py 支援接收多組 OHLCV 並行運算
- **組合層級風控：** 跨策略、跨標的的整體部位控制
- **真實數據源對接：** Yahoo Finance API, TWSE API 等
- **互動式 K 線圖：** 可拖拉縮放的網頁視覺化介面
