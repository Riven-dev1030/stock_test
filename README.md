# OHLCV 策略回測驗證系統 v1.0

基於 OHLCV 數據的交易策略回測與統計驗證平台。使用純 Python 實作，相依套件僅 pytest 與 matplotlib。

---

## 專案結構

```
stock_test/
├── core/
│   ├── data_gen.py          # 模擬數據生成（5 種市場模式）
│   ├── data_loader.py       # CSV / JSON 數據載入
│   ├── indicators.py        # 技術指標（SMA, ATR, Volume MA, Highest/Lowest）
│   ├── pattern.py           # K 棒型態辨識（錘子、吞噬、十字星等）
│   ├── strategy.py          # 策略定義、驗證、條件計算
│   └── engine.py            # 回測引擎（逐根掃描，支援多倉位）
├── output/
│   ├── serializer.py        # JSON 序列化 / 存檔 / 讀檔
│   ├── summary.py           # 統計摘要（勝率、期望值、最大回撤等）
│   ├── slicer.py            # OHLCV 切片擷取（供 AI 診斷）
│   └── chart.py             # PNG 圖表生成（需 matplotlib）
├── validation/
│   ├── monte_carlo.py       # Monte Carlo Simulation
│   ├── monkey_test.py       # Monkey Test（隨機策略對照）
│   └── overfit_detect.py    # Walk-Forward 過擬合偵測
├── config/
│   ├── strategy_config.json # 預設策略（趨勢突破 v1）
│   └── turtle_strategy.json # 海龜策略設定
├── tests/
│   ├── unit/                # 單元測試（DAT / IND / STR / ENG / OUT / VAL / PRF）
│   └── integration/         # 整合測試（INT）
├── main.py                  # 主程式入口（含所有 CLI 旗標）
├── run_compare.py           # 四策略比較腳本
├── run_turtle.py            # 海龜策略示範腳本
├── run_grid.py              # 網格策略示範腳本
├── requirements.txt         # 相依套件
└── setup.sh                 # 一鍵建立虛擬環境
```

---

## 快速開始

### 建立虛擬環境（推薦）

```bash
bash setup.sh
source venv/bin/activate
```

或手動建立：

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

## 主程式指令（main.py）

### 基本回測

```bash
# 預設：bull 模式，500 根 K 棒，seed=42（約 7 筆交易，勝率 ~85%）
python main.py

# 指定市場模式與 K 棒數
python main.py --mode bear --bars 1000 --seed 99

# 讀取真實 CSV 數據
python main.py --csv path/to/data.csv
```

CSV 格式要求：包含 `date, open, high, low, close, volume` 欄位（大小寫不敏感）。

### 輸出與圖表

```bash
# 儲存結果到 JSON
python main.py --output results.json

# 儲存 JSON 並同時生成 PNG 圖表
python main.py --output results.json --chart

# 把已存在的 results.json 轉成圖表
python main.py --to-image results.json
python main.py --to-image results.json --image-out my_chart.png
```

圖表包含：累積損益曲線、每筆交易損益、出場原因分布、統計摘要。

### 策略比較

```bash
# 比較 4 種內建策略（全市場模式）
python main.py --compare

# 只比較特定模式
python main.py --compare --mode choppy

# 自訂 K 棒數
python main.py --compare --bars 1000
```

四種內建策略：Trend Breakout、MA Crossover、RSI Rebound、Momentum。

### 其他旗標

```bash
# 指定策略設定檔
python main.py --strategy config/turtle_strategy.json

# 跳過統計驗證（加快速度）
python main.py --no-validation

# 自訂 Monte Carlo / Monkey Test 模擬次數
python main.py --mc-sims 10000 --mt-sims 20000
```

### 完整旗標一覽

| 旗標 | 預設值 | 說明 |
|------|--------|------|
| `--csv` | — | 讀取 CSV 數據檔 |
| `--strategy` | `config/strategy_config.json` | 策略設定檔路徑 |
| `--mode` | `bull` | 模擬市場模式（random/bull/bear/choppy/diverge）|
| `--bars` | `500` | 模擬 K 棒數量 |
| `--seed` | `42` | 隨機種子 |
| `--output` | — | 儲存結果 JSON 路徑 |
| `--chart` | `False` | 配合 `--output` 生成 PNG 圖表 |
| `--to-image` | — | 將現有 JSON 轉成 PNG 圖表 |
| `--image-out` | — | 圖表輸出路徑（預設同 JSON 名稱）|
| `--compare` | `False` | 比較 4 種內建策略 |
| `--no-validation` | `False` | 跳過 MC / Monkey Test / Walk-Forward |
| `--mc-sims` | `5000` | Monte Carlo 模擬次數 |
| `--mt-sims` | `10000` | Monkey Test 模擬次數 |
| `--mc-seed` | `0` | MC/MT 隨機種子（0 = 不固定）|

---

## 示範腳本

```bash
# 海龜策略（System 1）：20 日高點突破 + 2x ATR 止損 + 10 日低點出場
python run_turtle.py

# 網格策略：價格區間內多格同時持倉
python run_grid.py

# 四策略全面比較
python run_compare.py
```

---

## 執行測試

```bash
# 全套測試（123 tests）
python -m pytest tests/ -v

# 只跑單元測試
python -m pytest tests/unit/ -v

# 只跑整合測試
python -m pytest tests/integration/ -v

# 只跑效能測試
python -m pytest tests/unit/test_performance.py -v
```

---

## 策略設定格式

```json
{
  "name": "策略名稱",
  "max_positions": 1,
  "entry": {
    "mode": "ALL",
    "conditions": [
      { "type": "breakout",        "params": { "period": 20, "field": "high" } },
      { "type": "volume_above_ma", "params": { "multiplier": 1.2, "period": 20 } },
      { "type": "ma_alignment",    "params": { "fast": 20, "slow": 50, "direction": "bullish" } },
      { "type": "price_above_ma",  "params": { "period": 20 } }
    ]
  },
  "exit": {
    "mode": "ANY",
    "conditions": [
      { "type": "atr_stop",      "params": { "multiplier": 3, "period": 14 } },
      { "type": "ma_stop",       "params": { "fast": 20, "slow": 50 } },
      { "type": "trailing_stop", "params": { "activation_pct": 15, "trail_pct": 97 } }
    ]
  }
}
```

`max_positions`（選填，預設 1）：允許同時持有的最大倉位數，設為大於 1 可用於網格、加碼等策略。

### 內建進場條件

| type | 說明 |
|------|------|
| `breakout` | 收盤價突破 N 日最高點 |
| `volume_above_ma` | 成交量超過均量 N 倍 |
| `ma_alignment` | 均線多頭/空頭排列（fast > slow） |
| `price_above_ma` | 收盤價高於/低於指定均線 |

### 內建出場條件

| type | 說明 |
|------|------|
| `atr_stop` | ATR 倍數止損 |
| `ma_stop` | 快線跌破慢線止損 |
| `trailing_stop` | 移動止盈（觸發後追蹤峰值） |
| `fixed_stop` | 固定百分比止損 |
| `time_stop` | 持倉天數上限 |

### 自訂條件

```python
from core.strategy import ALL_CONDITION_TYPES

ALL_CONDITION_TYPES.add("my_type")  # 註冊自訂類型

class MyCondition:
    def __init__(self, params: dict):
        self.params = params

    def check(self, ohlcv: list, index: int, position: dict = None) -> bool:
        return True  # 自訂邏輯

result = run_backtest(ohlcv, config, custom_conditions={"my_type": MyCondition({})})
```

---

## 技術規格

- **語言：** Python 3.10+
- **核心相依：** Python 標準庫（`json`, `math`, `random`, `csv`）
- **測試框架：** pytest
- **圖表生成：** matplotlib
- **引擎特性：** 支援多倉位（`max_positions`）、自訂進出場條件
