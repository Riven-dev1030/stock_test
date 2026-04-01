# OHLCV 策略回測驗證系統 v1.0

基於 OHLCV 數據的交易策略回測與統計驗證平台。使用純 Python 標準庫實作，不依賴任何第三方套件（pytest 除外）。

---

## 專案結構

```
backtest-system/
├── core/
│   ├── data_gen.py          # 模擬數據生成（5 種市場模式）
│   ├── data_loader.py       # CSV / JSON 數據載入
│   ├── indicators.py        # 技術指標（SMA, ATR, Volume MA, Highest High）
│   ├── pattern.py           # K 棒型態辨識（錘子、吞噬、十字星等）
│   ├── strategy.py          # 策略定義、驗證、條件計算
│   └── engine.py            # 回測引擎（逐根掃描）
├── output/
│   ├── serializer.py        # JSON 序列化 / 存檔 / 讀檔
│   ├── summary.py           # 統計摘要（勝率、期望值、最大回撤等）
│   └── slicer.py            # OHLCV 切片擷取（供 AI 診斷）
├── validation/
│   ├── monte_carlo.py       # Monte Carlo Simulation
│   ├── monkey_test.py       # Monkey Test（隨機策略對照）
│   └── overfit_detect.py    # Walk-Forward 過擬合偵測
├── config/
│   └── strategy_config.json # 範例策略設定（趨勢突破 v1）
├── tests/
│   ├── unit/                # 單元測試（DAT / IND / STR / ENG / OUT / VAL / PRF）
│   └── integration/         # 整合測試（INT）
└── main.py                  # 程式入口
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

### 執行回測（模擬數據）

```bash
python main.py
python main.py --mode bull --bars 500 --seed 42
```

### 執行回測（真實 CSV 數據）

```bash
python main.py --csv path/to/data.csv
```

CSV 格式要求：包含 `date, open, high, low, close, volume` 欄位（大小寫不敏感，支援 `Vol` 等常見別名）。

### 儲存結果到檔案

```bash
python main.py --output results.json
```

### 跳過統計驗證（加快速度）

```bash
python main.py --no-validation
```

### 自訂策略

```bash
python main.py --strategy config/my_strategy.json
```

---

## 執行測試

```bash
# 全套測試
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
  "entry": {
    "mode": "ALL",
    "conditions": [
      { "type": "breakout",        "params": { "period": 20, "field": "high" } },
      { "type": "volume_above_ma", "params": { "multiplier": 1.5, "period": 20 } },
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

### 內建進場條件

| type | 說明 |
|------|------|
| `breakout` | 價格突破 N 日高/低點 |
| `volume_above_ma` | 成交量超過均量 N 倍 |
| `ma_alignment` | 均線多頭/空頭排列 |
| `price_above_ma` | 價格高於/低於指定均線 |

### 內建出場條件

| type | 說明 |
|------|------|
| `atr_stop` | ATR 倍數止損 |
| `ma_stop` | 均線交叉止損 |
| `trailing_stop` | 移動止盈 |
| `fixed_stop` | 固定百分比止損 |
| `time_stop` | 持倉天數上限 |

### 自定義條件

```python
class MyCondition:
    def __init__(self, params: dict):
        self.params = params

    def check(self, data: list, index: int, position: dict = None) -> bool:
        return True  # 自訂邏輯

result = run_backtest(ohlcv, config, custom_conditions={"my_type": MyCondition({})})
```

---

## 技術規格

- **語言：** Python 3.10+
- **核心相依：** 僅 Python 標準庫（`json`, `math`, `random`, `csv`）
- **測試框架：** pytest
