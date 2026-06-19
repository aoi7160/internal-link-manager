@echo off
echo === 内部リンク管理ツール ===
echo.

echo [1/3] 依存パッケージをインストール中...
pip install -r requirements.txt -q

echo [2/3] データベースを初期化・データ投入中...
python seed_data.py

echo [3/3] サーバー起動中...
echo.
echo ブラウザで http://localhost:5000 を開いてください
echo 終了するには Ctrl+C を押してください
echo.

python app.py
pause
