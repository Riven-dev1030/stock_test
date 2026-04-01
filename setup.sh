#!/usr/bin/env bash
# 建立並啟動虛擬環境，安裝相依套件
set -e

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "✔ 虛擬環境已建立於 ./venv"
echo "✔ 啟動方式: source venv/bin/activate"
echo "✔ 執行回測: python main.py"
echo "✔ 執行測試: python -m pytest tests/ -v"
