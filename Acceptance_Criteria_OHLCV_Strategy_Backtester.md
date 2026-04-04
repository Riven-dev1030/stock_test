# OHLCV 策略回測驗證系統 — 驗收標準

**版本：** v1.0  
**日期：** 2026-04-01  
**對應 SDD 版本：** v1.0  
**狀態：** Draft

---

## 1. 文件說明

本文件定義 OHLCV 策略回測驗證系統 v1.0 的驗收標準。每一項驗收項目均包含測試方法與通過條件，用於確認系統是否符合 SDD 的設計規格。

### 驗收等級定義

| 等級 | 說明 |
|------|------|
| **P0 — 必須通過** | 核心功能，未通過則系統不可交付 |
| **P1 — 應該通過** | 重要功能，允許有已知限制但需記錄 |
| **P2 — 建議通過** | 增強功能，不影響核心使用 |

---

## 2. 數據層驗收

### 2.1 模擬數據生成

| 項目 | 等級 | 測試方法 | 通過條件 |
|------|------|----------|----------|
| DAT-01 | P0 | 呼叫 `data_gen.generate(n=200, mode="random")` | 回傳長度為 200 的陣列，每筆包含 date, open, high, low, close, volume 六個欄位 |
| DAT-02 | P0 | 檢查每根 K 棒的數值關係 | 所有 K 棒滿足 `low <= open <= high` 且 `low <= close <= high` |
| DAT-03 | P0 | 檢查數據連續性 | 每根的 open 與前一根的 close 差距不超過前一根 close 的 10% |
| DAT-04 | P1 | 分別生成 bull / bear / choppy / diverge 模式各 200 天 | bull 模式的最後收盤價高於第一根；bear 模式低於第一根；choppy 模式首尾差距在 10% 以內 |
| DAT-05 | P0 | 檢查 volume 欄位 | 所有 volume 為正整數 |

### 2.2 真實數據載入

| 項目 | 等級 | 測試方法 | 通過條件 |
|------|------|----------|----------|
| DAT-06 | P0 | 提供一份標準 CSV（含 header），呼叫 `data_loader.load_from_csv(path)` | 正確解析為標準 OHLCV 陣列，欄位名稱不區分大小寫 |
| DAT-07 | P0 | 提供一份欄位名不同的 CSV（如 `Vol` 而非 `volume`） | 系統能透過 mapping 設定正確載入，或拋出明確的欄位缺失錯誤 |
| DAT-08 | P1 | 提供一份含缺失值的 CSV | 系統拋出明確錯誤指出哪幾行有問題，不會靜默產生錯誤數據 |

---

## 3. 指標計算驗收

### 3.1 正確性

| 項目 | 等級 | 測試方法 | 通過條件 |
|------|------|----------|----------|
| IND-01 | P0 | 手動計算 5 根收盤價的 SMA(3)，對比 `sma()` 輸出 | 數值完全一致（浮點誤差 < 0.0001） |
| IND-02 | P0 | 手動計算 5 根的 ATR(3)，對比 `atr()` 輸出 | 數值完全一致 |
| IND-03 | P0 | 手動計算 5 根的 volume_ma(3)，對比輸出 | 數值完全一致 |
| IND-04 | P0 | 計算 highest_high(5) 對 10 根數據，對比輸出 | 數值完全一致 |

### 3.2 邊界條件

| 項目 | 等級 | 測試方法 | 通過條件 |
|------|------|----------|----------|
| IND-05 | P0 | 對 SMA(20) 傳入只有 10 根的數據 | 回傳全部為 None 的陣列，不報錯 |
| IND-06 | P0 | 對空陣列呼叫任意指標函式 | 回傳空陣列，不報錯 |
| IND-07 | P1 | 傳入包含 0 volume 的數據 | 指標正常計算，不因除零而崩潰 |

---

## 4. 策略定義驗收

### 4.1 設定載入

| 項目 | 等級 | 測試方法 | 通過條件 |
|------|------|----------|----------|
| STR-01 | P0 | 載入 SDD 中範例的 JSON 策略設定 | 系統正確解析所有進場與出場條件 |
| STR-02 | P0 | 載入一個缺少必要欄位的 JSON（如缺少 `exit`） | 系統拋出明確的驗證錯誤，指出缺少哪個欄位 |
| STR-03 | P0 | 載入一個包含未知 condition type 的 JSON | 系統拋出明確錯誤，指出不支援的 type 名稱 |

### 4.2 內建條件

| 項目 | 等級 | 測試方法 | 通過條件 |
|------|------|----------|----------|
| STR-04 | P0 | 構造一組已知 OHLCV，使得 breakout 條件在第 25 根觸發 | `breakout.check()` 在第 25 根回傳 True，前後回傳 False |
| STR-05 | P0 | 構造一組已知數據，使成交量恰好等於 1.5 倍均量 | `volume_above_ma.check()` 回傳 True（邊界值包含） |
| STR-06 | P0 | 構造 MA20 > MA50 的數據 | `ma_alignment.check()` 回傳 True |
| STR-07 | P0 | 構造 MA20 < MA50 的數據 | `ma_alignment.check()` 回傳 False |
| STR-08 | P0 | 構造持倉中漲幅達 15% 後回落到 peak 的 97% | `trailing_stop.check()` 在回落那根回傳 True |
| STR-09 | P0 | 構造持倉中漲幅僅 10%（未達 15% 啟動門檻） | `trailing_stop.check()` 回傳 False（trailing 未啟動） |
| STR-10 | P0 | 構造價格跌破 entry - 3*ATR | `atr_stop.check()` 回傳 True |

### 4.3 自定義條件擴充

| 項目 | 等級 | 測試方法 | 通過條件 |
|------|------|----------|----------|
| STR-11 | P1 | 實作一個簡單的自定義條件（如「收盤價為偶數」），註冊到策略設定中 | 回測引擎正確呼叫該條件的 check() 方法 |

---

## 5. 回測引擎驗收

### 5.1 基本行為

| 項目 | 等級 | 測試方法 | 通過條件 |
|------|------|----------|----------|
| ENG-01 | P0 | 用 200 天模擬數據 + 範例策略跑回測 | 正常執行完畢，輸出 JSON 包含 metadata, trades, scan_log, summary 四個頂層欄位 |
| ENG-02 | P0 | 檢查 warmup period | 前 50 根（MA50 所需）的 scan_log 中 entry_triggered 全部為 false，且 entry_conditions 不存在或標示為 insufficient_data |
| ENG-03 | P0 | 檢查交易不重疊 | trades 陣列中任意兩筆交易的 [entry_index, exit_index] 區間不重疊 |
| ENG-04 | P0 | 構造一組必定觸發進場的數據（所有條件在特定根滿足） | 該根的 scan_log 顯示 entry_triggered = true，trades 中有對應的進場紀錄 |

### 5.2 出場機制

| 項目 | 等級 | 測試方法 | 通過條件 |
|------|------|----------|----------|
| ENG-05 | P0 | 構造進場後立即觸發 ATR 止損的數據 | trades 中該筆的 exit_reason = "atr_stop"，exit_price 符合預期 |
| ENG-06 | P0 | 構造進場後觸發均線止損的數據（MA20 下穿 MA50 且價格低於 MA20） | exit_reason = "ma_stop" |
| ENG-07 | P0 | 構造先漲 15% 再回落至 peak * 0.97 的數據 | exit_reason = "trailing_stop"，且 trailing 在漲幅達 15% 時啟動 |
| ENG-08 | P0 | 構造同時觸發 ATR 止損和均線止損的數據 | 系統選擇其中一個作為 exit_reason（先觸發的優先），不重複記錄 |

### 5.3 逐根掃描日誌

| 項目 | 等級 | 測試方法 | 通過條件 |
|------|------|----------|----------|
| ENG-09 | P0 | 檢查 scan_log 長度 | 等於 total_bars - warmup_period |
| ENG-10 | P0 | 檢查持倉中的 scan_log | 包含 position 物件，且 current_pnl_pct 計算正確 |
| ENG-11 | P0 | 檢查出場條件的 distance_pct | ATR 止損的 distance_pct = (current_price - stop_price) / current_price * 100，數值正確 |

### 5.4 邊界情況

| 項目 | 等級 | 測試方法 | 通過條件 |
|------|------|----------|----------|
| ENG-12 | P0 | 數據結束時仍持倉 | trades 中最後一筆的 exit_reason = "end_of_data"，exit_price 為最後一根收盤價 |
| ENG-13 | P1 | 整段數據完全不觸發進場 | trades 為空陣列，summary 中 total_trades = 0，程式不報錯 |
| ENG-14 | P1 | 只有 warmup period 長度的數據（如 50 根跑 MA50 策略） | trades 為空陣列，程式正常結束 |

---

## 6. 輸出層驗收

### 6.1 JSON 結構

| 項目 | 等級 | 測試方法 | 通過條件 |
|------|------|----------|----------|
| OUT-01 | P0 | 對回測輸出執行 `json.loads()` | 合法的 JSON，無解析錯誤 |
| OUT-02 | P0 | 驗證 JSON schema | 包含 metadata, trades, scan_log, summary 四個必要欄位，trades 中每筆包含 SDD 定義的所有欄位 |

### 6.2 統計摘要

| 項目 | 等級 | 測試方法 | 通過條件 |
|------|------|----------|----------|
| OUT-03 | P0 | 手動計算 3 筆已知交易的 win_rate, profit_factor, expectancy | 與 summary 輸出一致 |
| OUT-04 | P0 | 驗證 exit_reason_breakdown 的總和 | 等於 total_trades |
| OUT-05 | P0 | 驗證 max_drawdown_pct | 手動計算累計損益曲線的最大回撤，與輸出一致 |

### 6.3 AI 診斷切片

| 項目 | 等級 | 測試方法 | 通過條件 |
|------|------|----------|----------|
| OUT-06 | P0 | 對虧損最大的交易呼叫 slicer | 回傳的 ohlcv_slice 長度 = 前後各 15 根 + 交易區間，indicators_slice 的每個指標陣列長度與 ohlcv_slice 一致 |
| OUT-07 | P1 | 檢查 diagnosis_prompt 欄位 | 包含交易損益、進場日期、出場原因等關鍵資訊 |
| OUT-08 | P1 | 自動篩選邏輯：虧損最大 3 筆 | 回傳的 trade_id 對應 trades 中 pnl_pct 最低的 3 筆 |

---

## 7. 統計驗證模組驗收

### 7.1 Monte Carlo Simulation

| 項目 | 等級 | 測試方法 | 通過條件 |
|------|------|----------|----------|
| VAL-01 | P0 | 用固定 random seed 跑 Monte Carlo 兩次 | 兩次輸出完全一致（可重現性） |
| VAL-02 | P0 | 檢查 percentiles 的順序 | p5 <= p25 <= p50 <= p75 <= p95（對 total_return 和 max_drawdown 分別成立） |
| VAL-03 | P0 | 提供全部為正損益的交易 | ruin_probability = 0 |
| VAL-04 | P1 | 跑 5,000 次模擬 | 執行時間 < 2 秒 |

### 7.2 Monkey Test

| 項目 | 等級 | 測試方法 | 通過條件 |
|------|------|----------|----------|
| VAL-05 | P0 | 用固定 random seed 跑 Monkey Test 兩次 | 兩次輸出完全一致 |
| VAL-06 | P0 | 檢查 percentile_rank 計算 | 手動驗算策略 return 在隨機分佈中的排名百分位，誤差 < 1% |
| VAL-07 | P0 | 提供一個績效極差的策略（總虧損 -50%） | percentile_rank 明顯低於 50 |
| VAL-08 | P1 | 跑 10,000 次隨機策略 | 執行時間 < 5 秒 |

### 7.3 Overfitting Detection

| 項目 | 等級 | 測試方法 | 通過條件 |
|------|------|----------|----------|
| VAL-09 | P0 | 用 Walk-Forward 方法跑 200 天數據，window=100, step=30 | 輸出包含正確數量的 folds，每個 fold 的 in_sample 和 out_of_sample 區間不重疊 |
| VAL-10 | P0 | 檢查 degradation_ratio 計算 | 等於 out_of_sample_avg_return / in_sample_avg_return，數值正確 |
| VAL-11 | P1 | 構造一組明顯過擬合的場景（in-sample 高績效，out-of-sample 負績效） | overfit_warning = true |

---

## 8. 整合測試

### 8.1 端到端流程

| 項目 | 等級 | 測試方法 | 通過條件 |
|------|------|----------|----------|
| INT-01 | P0 | 從 main.py 執行完整流程：生成數據 → 回測 → 輸出 JSON → 統計摘要 | 程式正常結束，輸出合法 JSON 檔案 |
| INT-02 | P0 | 從 main.py 執行完整流程 + Monte Carlo + Monkey Test | 三者使用同一份交易結果，統計數據一致 |
| INT-03 | P1 | 用 CSV 載入真實數據 → 回測 → 全套驗證 | 與模擬數據使用完全相同的程式路徑，輸出格式一致 |

### 8.2 策略切換

| 項目 | 等級 | 測試方法 | 通過條件 |
|------|------|----------|----------|
| INT-04 | P0 | 準備兩份不同的 strategy_config.json，分別執行 | 兩次回測使用正確的策略參數，輸出的 metadata.strategy_name 和 params 分別對應 |
| INT-05 | P1 | 用同一份數據、同一策略、同一 random seed 跑兩次 | 輸出結果完全一致（確定性行為） |

---

## 9. 效能驗收

| 項目 | 等級 | 測試方法 | 通過條件 |
|------|------|----------|----------|
| PRF-01 | P1 | 計時 200 天模擬數據生成 | < 10ms |
| PRF-02 | P1 | 計時 200 天數據的單次回測 | < 50ms |
| PRF-03 | P1 | 計時 Monte Carlo 5,000 次 | < 2s |
| PRF-04 | P1 | 計時 Monkey Test 10,000 次 | < 5s |
| PRF-05 | P2 | 計時 Walk-Forward 10 folds | < 10s |

---

## 10. 驗收流程

### 10.1 執行順序

1. **單元測試（Unit Test）** — 跑 `pytest tests/unit/`，涵蓋第 2~4 節所有 P0 項目
2. **整合測試（Integration Test）** — 跑 `pytest tests/integration/`，涵蓋第 5~7 節所有 P0 項目
3. **端到端測試（E2E Test）** — 執行第 8 節的手動或自動化流程
4. **效能測試（Performance Test）** — 執行第 9 節的計時測試

### 10.2 通過標準

| 等級 | 要求 |
|------|------|
| P0 | 100% 通過，零容忍 |
| P1 | 90% 以上通過，未通過項目需記錄為 known issue 並附上修復計畫 |
| P2 | 不影響驗收，作為後續改進參考 |

### 10.3 驗收產出物

驗收完成後應產出以下文件：

- 測試報告（pytest 輸出，含通過/失敗明細）
- 效能測試數據（各項計時結果）
- Known Issues 清單（如有 P1 未通過項目）
- 驗收簽核紀錄（確認日期與版本）
