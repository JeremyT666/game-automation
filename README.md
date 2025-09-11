# Game Automation Testing

## 專案概述
針對遊戲客戶端的自動化測試框架

### 主要功能
- 自動化登入與連線管理
- 多遊戲類型驗證支援
- 賠率計算與投注驗證
- html報告生成

### 技術棧
- 語言: Python 3.10+
- 測試框架: pytest
- 異步處理: asyncio
- WebSocket: websockets
- 配置管理: PyYAML
- 報告生成: pytest-html
- 日誌管理: 自訂 logger 模組
- 位元運算: 自訂 bitmap 解析工具

## 快速開始
### 前置需求
  - python 3.10或以上版本
  - 測試環境訪問權限
  - 有效的測試帳號

### 安裝與設定
```
# 1. 克隆專案
git clone <repository-url>
cd game-automation

# 2. 建立虛擬環境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 安裝依賴
pip install -r requirements.txt

# 4. 設定測試資料
# 編輯測試伺服器配置
nano test_data/config.yaml

# 編輯測試玩家資訊
nano test_data/player_info/<currency>_player_info.yaml
```

### 第一次執行
```
# 執行登入測試驗證環境
python -m pytest -v -m "login"

# 執行特定玩家的百家樂測試
python -m pytest -v --player-id=rel_usd_single_player -m "bac_bet"
```

## 使用指南
### 基本測試執行
```
# 執行登入測試
python -m pytest -v -m "login"

# 執行進桌測試
python -m pytest -v -m "table"

# 執行百家樂投注測試
python -m pytest -v --player-id=rel_usd_single_player -m "bac_bet"

# 執行龍虎投注測試
python -m pytest -v --player-id=rel_usd_single_player -m "dtb_bet"

# 執行餘額檢查測試
python -m pytest -v --player-id=rel_usd_single_player -m "bac_balancecheck"

# 執行所有單桌測試
python -m pytest -v --player-id=rel_usd_single_player -m "single_table"
```

### 進階選項
```
# 生成 HTML 報告
python -m pytest --html=reports/report.html --self-contained-html

# 並行執行 (需安裝 pytest-xdist)
python -m pytest -v -n 4 -m "single_table"

# 只執行失敗的測試
python -m pytest --lf

# 詳細日誌模式
python -m pytest -v -s --log-cli-level=DEBUG

# 指定特定測試檔案
python -m pytest tests/bac/single_table/test_bac_odds.py -v
```

## 環境配置
### 測試環境需求
1. 測試帳號設定:
   - 測試帳號要放到Operator熱加載永不踢桌內
   - 確保帳號有足夠的測試額度
2. 桌台配置:
   - 結算秒數: 5秒
   - 延遲秒數: 0秒
   - 特定玩法限制局數: 60局
3. AutoDealer 設定:
   - 換靴局數: 60局

### 配置檔案說明
- config.yaml: 測試伺服器連線的相關設定
- player_info: 各幣別測試用玩家的配置資訊

## 專案架構
    game-automation/
        ├── src/                        # 核心程式代碼目錄
        │   ├── conf/                   # 配置文件目錄
        │   ├── connection/             # 連接處理模塊
        │   │   └── wss_handler.py      # WebSocket連線與封包收發
        │   ├── game/                   # 遊戲邏輯相關模塊
        │   │   ├── bet.py              # 下注功能實現
        │   │   ├── card_parser.py      # 撲克牌解析工具 - bitmap轉換為牌面資訊
        │   │   ├── game_result_parser.py # 遊戲結果解析器 - bitmap轉換為遊戲狀態
        │   │   ├── get_result.py       # 遊戲結果接收處理
        │   │   ├── odds_tables.py      # 賠率表配置
        │   │   ├── playtype_enums.py   # 遊戲玩法枚舉定義
        │   │   ├── settle.py           # 派彩相關協議處理
        │   │   └── payout/             # 賠率計算相關
        │   │       ├── payout_calculator.py  # 賠率計算邏輯
        │   │       └── payout_verifier.py    # 賠率驗證邏輯
        │   ├── gateserver/             # GateServer連線模塊
        │   │   └── gateserver_handler.py  # GateServer連線處理
        │   ├── gameapi/                # GameAPI 相關模塊
        │   │   └── gameapi_handler.py  # GameAPI連線處理
        │   ├── heartbeat/              # 心跳包處理模塊
        │   │   └── heartbeat.py        # 連線心跳包處理邏輯
        │   ├── loginserver/            # LoginServer連線模塊
        │   │   └── loginserver_handler.py # 登入與取得GateServer Token
        │   ├── packet/                 # 封包處理相關模塊
        │   │   └── packet_handler.py   # 封包處理核心邏輯 - 打包與解包
        │   ├── protocols/              # 協議相關模塊
        │   │   ├── generate_protocol_format.py # 格式化協議字串
        │   │   └── protocols.py        # 所有對接協議定義與格式內容
        │   ├── user/                   # 用戶操作相關模塊
        │   │   ├── balance.py          # 額度相關協議處理
        │   │   └── enter_table.py      # 進桌功能
        │   ├── utils/                  # 共用工具函數
        │   │   ├── balance_checker.py  # 額度檢查工具
        │   │   ├── bitmap_mapping.py   # 位元運算工具
        │   │   ├── config_loader.py    # 配置加載工具
        │   │   ├── encryption.py       # 加密函數
        │   │   ├── logger.py           # 日誌模塊
        │   │   └── random_string.py    # 隨機字串生成
        │   └── main_test.py            # 模擬客戶端測試程式
        ├── tests/                      # 測試目錄
        │   ├── conftest.py             # pytest 配置和 fixtures
        │   ├── test_login.py           # 登入相關測試
        │   ├── test_enter_table.py     # 進桌相關測試
        │   ├── bac/                    # 百家樂測試
        │   │   ├── test_bac_balance_check.py  # 百家樂餘額檢查測試
        │   │   └── single_table/       # 單桌測試
        │   │       ├── test_bac_betting.py    # 百家樂投注測試
        │   │       └── test_bac_odds.py       # 百家樂賠率測試
        │   └── dtb/                    # 龍虎測試
        │       ├── test_dtb_balance_check.py  # 龍虎餘額檢查測試
        │       └── single_table/       # 單桌測試
        │           ├── test_dtb_betting.py    # 龍虎投注測試
        │           └── test_dtb_odds.py       # 龍虎賠率測試
        ├── test_data/                  # 測試資料目錄
        │   ├── config.yaml             # 測試伺服器配置
        │   └── player_info             # 各幣別測試用玩家配置資訊
        ├── reports/                    # 測試報告目錄
        │   ├── report.html             # HTML 格式測試報告
        │   ├── logs                    # 執行log
        ├── .vscode/                    # VS Code 配置
        ├── .gitignore                  # Git 忽略文件
        ├── .coveragerc                 # 代碼覆蓋率配置
        ├── pytest.ini                 # pytest 配置文件
        ├── pyproject.toml              # 專案配置
        ├── requirements.txt            # Python 依賴庫
        ├── todo.md                     # 待辦事項
        └── README.md                   # 專案文檔

## Pytest Marker
1. login: 2 cases
2. table: 52 cases
3. bac_bet: 2496 cases (include bac_balancecheck)
4. bac_balancecheck: 718 cases
5. bac_odds: 14 cases (Payout verification tests - covering win/loss scenarios for all play types)
6. dtb_bet: 928 cases (include dtb_balancecheck)
7. dtb_balancecheck: 232 cases
8. dtb_odds: 11 cases (Payout verification tests - covering win/loss scenarios for all play types)
9. single_table: 2474 cases (include all gametype betting marks)

## 障礙排除
### 賠率驗證錯誤
- 確認賠率表配置是否正確
- 檢查bitmap解析邏輯
- 驗證遊戲規則實作
- 確認測試環境的桌台設定

### 餘額計算異常
- 檢查桌台結算秒數設定
- 確認測試帳號所屬lobby的server log
- 確認vendor api log

# 開發規範

## Git Branch 管理

### Branch命名規範
- **功能開發**: `feature/<功能描述>`
- **Bug 修復**: `fix/<問題描述>`
- **測試相關**: `test/<測試內容>`
- **文檔更新**: `docs/<文檔類型>`
- **重構代碼**: `refactor/<重構範圍>`

### 開發流程

#### 1. 新功能開發
```bash
# 從 main 分支建立新功能分支
git checkout main
git pull origin main
git checkout -b feature/new-bac-playtype

# 開發完成後推送分支
git add .
git commit -m "feat: add new bac playtype validation"
git push origin feature/new-bac-playtype

# 建立 Pull Request 進行 Code Review
```

#### 2. Bug 修復
```bash
# 建立修復分支
git checkout -b fix/payout-calculation-error

# 修復完成後
git commit -m "fix: correct payout calculation for tie scenarios"
git push origin fix/payout-calculation-error
```

#### 3. 測試案例新增
```bash
# 建立測試分支
git checkout -b test/dtb-edge-cases

# 新增測試後
git commit -m "test: add edge case tests for DTB game scenarios"
git push origin test/dtb-edge-cases
```

#### 4. 測試命名規範
```python
# 格式: test_<功能>_<場景>
def test_bac_betting_with_valid_amount():
    pass

def test_dtb_payout_calculation_with_tie():
    pass

def test_login_with_invalid_token():
    pass
```

# Commit Message Style 規範

此規範遵循 [Conventional Commits](https://www.conventionalcommits.org/)，並針對自動化測試、自動化腳本與 QA 團隊的開發習慣做調整。

---

## Prefix 類型（請選擇最符合的前綴）

| Prefix     | 用途說明 |
|------------|----------|
| `feat`     | 新增功能，例如新的 test case、功能流程驗證 |
| `fix`      | 修復 Bug 或修正測試異常行為 |
| `refactor` | 重構邏輯，不影響功能行為（例如提取共用程式碼） |
| `chore`    | 非功能性維護，例如 config、CI、資料更新 |
| `test`     | 純測試腳本新增/修改（如新增 mock, fixture, 測項） |
| `style`    | 格式修改（如命名調整、排版統一、不影響邏輯） |
| `docs`     | 文件編輯，例如 README、測試說明、流程記錄 |
| `perf`     | 效能優化，例如壓測流程、延遲優化等 |
| `ci`       | 修改自動化流程、CI/CD pipeline 設定 |

---