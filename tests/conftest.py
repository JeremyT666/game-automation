import asyncio
import json
import requests
import sys
from datetime import datetime

from pathlib import Path
# 添加 src 到 Python 路徑, 這邊必須先添加, 否則以下src路徑內的import會報錯
project_root = Path(__file__).parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

import pytest
from src.utils.config_manager import ConfigManager

from src.gateserver.gateserver_handler import GateServerHandler
from src.heartbeat.heartbeat import start_heartbeat
from src.utils.logger import logger


def pytest_configure(config):
    """動態設置帶有時間戳的報告檔名"""
    # 創建報告目錄（如果不存在）
    report_dir = Path(project_root) / "reports"
    report_dir.mkdir(exist_ok=True)
    
    # 生成帶有時間戳的報告檔名
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    report_path = report_dir / f"report_{timestamp}.html"
    
    # 修改 addopts，添加新的報告檔名
    if hasattr(config.option, 'htmlpath'):
        config.option.htmlpath = str(report_path)
    
    # 將時間戳添加到 pytest 配置供其他函數使用
    config._timestamp = timestamp

@pytest.fixture(scope="session")
def config_manager():
    """提供配置管理器的單例"""
    return ConfigManager()

# TODO: 目前以下cli選項(player-id, currency, seamless), 同時間只能指定一項, 後續再做優化
def pytest_addoption(parser):
    """添加玩家選擇的cli選項"""
    parser.addoption(
        "--player-id", action="append", default=[], 
        help="指定要測試的玩家ID，可以多次使用此選項指定多個玩家"
    )
    parser.addoption(
        "--currency", action="append", default=[],
        help="指定要測試的幣別，可以多次使用此選項指定多個幣別"
    )
    parser.addoption(
        "--seamless", action="store", default=None, choices=["True", "False"],
        help="是否為單一錢包帳號，不指定則使用所有玩家，指定 True 為單一錢包，False 為轉帳錢包"
    )

def pytest_generate_tests(metafunc):
    """
    自動參數化需要玩家數據的測試

    - 這是一個 pytest 特殊 hook 函數，當 pytest 收集測試用例時會自動調用
    - metafunc 參數包含測試函數的相關信息，可用於動態參數化
    """
    # 檢查測試是否需要 player_data fixture
    if "player_data" in metafunc.fixturenames:
        config_manager = ConfigManager()
        
        # 從命令行獲取玩家選擇選項, 這些選項是在 pytest_addoption 函數中定義的
        player_ids = metafunc.config.getoption("--player-id")
        currencies = metafunc.config.getoption("--currency")
        seamless_str = metafunc.config.getoption("--seamless")
        # 從cli獲取的seamless_str是字串, 需要轉換為布林值, 存到seamless變數中, 如果cli給值是 "True" 則為 True, 否則為 False
        seamless = seamless_str == "True"
        
        # 初始化空list，用於儲存所有玩家資料和玩家ID列表
        all_player_data = []
        player_ids_list = []
        
        # 如果指定了特定玩家ID
        if player_ids:
            # 迴圈遍歷所有指定的玩家ID, 並取其詳細資訊
            for player_id in player_ids:
                player_data = config_manager.get_player_info(player_id)
                if player_data:
                    # 確保 player_data 包含必要信息
                    player_data["player_id"] = player_id
                    # 根據 callback_key 判斷 seamless 類型
                    callback_key = player_data.get(player_id, {}).get("callback_key", None)   # 必須多做一次解開嵌套結構, 因callback_key是在player_id的下一層
                    if callback_key is None or callback_key == "N/A":
                        player_data["seamless"] = False
                    else:
                        player_data["seamless"] = True
                    # 如果 currency 不存在，嘗試從玩家ID推斷或使用預設值
                    try:
                        # 嘗試從 player_id 中提取幣別, 並轉換為大寫
                        currency_str = player_id.split("_")[1].upper()
                        player_data["currency"] = currency_str
                    except (IndexError, AttributeError) as e:
                        logger.error (f">>> [FIXTURE] Error occurred while pytest_generate_tests: {e}")
                        player_data["currency"] = "JPY"  # default value
                    except Exception as e:
                        logger.error (f">>> [FIXTURE] Unexpected error occurred while pytest_generate_tests: {e}")
                        player_data["currency"] = "JPY"  # default value
                    all_player_data.append(player_data)
                    player_ids_list.append(f"{currency_str}_{player_id}")
                    # player_ids_list.append(player_id)

        # 如果指定了特定幣別
        elif currencies:
            # 迴圈遍歷所有指定的幣別, 並取其詳細資訊
            for currency in currencies:
                currency_players = config_manager.get_player_info_by_currency(currency)
                for player_id, data in currency_players.items():
                    # 確保 player_data 包含必要信息
                    data["player_id"] = player_id
                    currency_str = str(currency).upper()
                    data["currency"] = currency_str

                    callback_key = data.get("callback_key", None)
                    if callback_key is None or callback_key == "N/A":
                        data["seamless"] = False
                    else:
                        data["seamless"] = True

                    all_player_data.append(data)
                    player_ids_list.append(f"{currency_str}_{player_id}")
                    # player_ids_list.append(player_id)

        # 如果指定了錢包類型
        elif seamless_str in ["True", "False"]:
            # 載入所有玩家資料
            all_data = config_manager.load_all_player_info()
            
            # 遍歷所有幣別和玩家
            for currency, players in all_data.items():
                for player_id, data in players.items():
                    # 確保 player_data 包含必要信息
                    data["player_id"] = player_id
                    currency_str = str(currency).upper()
                    data["currency"] = currency_str
                    
                    # 根據 callback_key 判斷 seamless 類型
                    callback_key = data.get("callback_key", None)
                    if callback_key is None or callback_key == "N/A":
                        data["seamless"] = False
                        # seamless 為 True 時，只選擇單一錢包玩家
                        if seamless == True:
                            continue  # 跳過轉帳錢包玩家
                    else:
                        data["seamless"] = True
                        # seamless 為 False 時，只選擇轉帳錢包玩家
                        if seamless == False:
                            continue  # 跳過單一錢包玩家
                            
                    # 添加符合條件的玩家數據
                    all_player_data.append(data)
                    player_ids_list.append(f"{currency_str}_{player_id}")

        # 默認：使用所有幣別的所有玩家
        else:
            all_currencies = config_manager.load_all_player_info()
            # print(f"\nall currencies data: {all_currencies}")
            for currency, players in all_currencies.items():
                for player_id, data in players.items():
                    # 確保 player_data 包含必要信息
                    data["player_id"] = player_id
                    currency_str = str(currency).upper()
                    data["currency"] = currency_str
                    
                    callback_key = data.get("callback_key", None)
                    if callback_key is None or callback_key == "N/A":
                        data["seamless"] = False
                    else:
                        data["seamless"] = True
                    all_player_data.append(data)
                    player_ids_list.append(f"{currency_str}_{player_id}")
                    # player_ids_list.append(player_id)
        
        # 如果沒有找到玩家數據，添加一個警告資訊
        if not all_player_data:
            all_player_data.append({"player_id": "NoPlayerData", "currency": "UNKNOWN", "seamless": False})
            player_ids_list.append("NoPlayerData")
            
        # 使用玩家數據參數化測試函數
        metafunc.parametrize(
            "player_data", 
            all_player_data,
            ids=player_ids_list,
            # scope="module" 是關鍵設置，確保執行順序是「先玩家資料、再測試用例」，即對於每個玩家，會先執行完它的所有測試用例，再切換到下一個玩家
            scope="module" 
        )

# HACK: 嘗試取代原有的 player_connection 跟 module_player_connection fixture
def player_connection_factory(scope):
    """產生不同 scope 的玩家連線 fixture Factory Function"""
    
    @pytest.fixture(scope=scope)
    async def _player_connection(player_data):
        """提供玩家連線的 fixture
        
        scope 參數決定了此 fixture 的生命週期：
        - function：每次測試都會重新登入
        - module：整個測試模組共享同一連線
        """
        handler = GateServerHandler()
        hb_task = None
        try:
            # 從 player_data 中獲取玩家信息
            player_id = player_data.get("player_id", "Unknown Player")
            seamless = player_data.get("seamless", False)
            # print(f">>> [FIXTURE] Player ID: {player_id}, Seamless: {seamless}")
            currency = player_data.get("currency", "Unknown Currency")
            
            # 嘗試登入
            gate_conn_result, player_init_balance = await handler.gate_server_connection(
                player_id=player_id,
                seamless=seamless,
                currency=currency
            )
            
            if gate_conn_result:
                # 登入成功, 啟動心跳包
                loop = asyncio.get_running_loop()
                hb_task = loop.create_task(start_heartbeat(handler))
                await asyncio.sleep(0.1)
                yield handler, player_init_balance
            else:
                # 登入失敗, 返回None
                logger.error(f">>> [FIXTURE] Login failed for player_id: {player_id}")
                yield None, None
                
        except Exception as e:
            logger.error(f">>> [FIXTURE] Error occurred: {e}")
            raise

        finally:
            if hb_task and not hb_task.done():
                hb_task.cancel()
                try:
                    await hb_task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f">>> [FIXTURE] Unexpected error during cancellation: {e}")

            if hasattr(handler, 'packet_handler'):
                try:
                    await handler.packet_handler.stop_processor()
                except Exception as e:
                    logger.error(f">>> [FIXTURE] Error stopping packet_handler: {e}")
                
            if hasattr(handler, 'websocket') and handler.websocket:
                try:
                    await handler.close()
                except Exception as e:
                    logger.error(f">>> [FIXTURE] Error closing websocket: {e}")
    
    return _player_connection

# 使用Factory Function生成兩個不同 scope 的 fixtures
player_connection = player_connection_factory("function")   # 作用域為每個測試函數, 每個測試函數都會重新建立連線
module_player_connection = player_connection_factory("module")  # 作用域為整個模組, 整個模組只會建立一次連線


def game_bet_amounts_factory(game_type_prefix):
    """
    通用的遊戲投注金額 fixture 工廠函數
    
    Args:
        game_type_prefix: 遊戲類型前綴 (例如 "bac", "dtb", "sic", "rlt")
    """
    
    @pytest.fixture
    def _game_bet_amounts(player_data, config_manager):
        """提供指定遊戲所有玩法的投注金額作為便捷屬性"""
        player_id = player_data.get("player_id", "Unknown Player")
        
        # 內部函數來獲取投注金額，直接使用 config_manager
        def get_bet_amount(game_type, bet_type, default_value=100):
            try:
                bet_amounts = config_manager.get_bet_amounts(player_id, game_type)
                return bet_amounts.get(bet_type, default_value)
            except Exception as e:
                logger.error(f">>> [FIXTURE] Error getting bet amount for {game_type}.{bet_type}: {e}")
                return default_value
        
        class GameBets:
            def __init__(self):
                if game_type_prefix == "bac":
                    self.banker = get_bet_amount(game_type_prefix, "banker", 100)
                    self.banker_nocomm = get_bet_amount(game_type_prefix, "banker_nocomm", 100)
                    self.player = get_bet_amount(game_type_prefix, "player", 100)
                    self.tie = get_bet_amount(game_type_prefix, "tie", 100)
                    self.banker_pair = get_bet_amount(game_type_prefix, "banker_pair", 100)
                    self.player_pair = get_bet_amount(game_type_prefix, "player_pair", 100)
                    self.any_pair = get_bet_amount(game_type_prefix, "any_pair", 100)
                    self.perfect_pair = get_bet_amount(game_type_prefix, "perfect_pair", 100)
                    self.banker_dragon_bonus = get_bet_amount(game_type_prefix, "banker_dragon_bonus", 100)
                    self.player_dragon_bonus = get_bet_amount(game_type_prefix, "player_dragon_bonus", 100)
                    self.lucky6 = get_bet_amount(game_type_prefix, "lucky6", 100)
                    self.duo_bao = get_bet_amount(game_type_prefix, "duo_bao", 100)
                    self.lucky6_2 = get_bet_amount(game_type_prefix, "lucky6_2", 100)
                    self.lucky6_3 = get_bet_amount(game_type_prefix, "lucky6_3", 100)
                    self.lucky7 = get_bet_amount(game_type_prefix, "lucky7", 100)
                    self.super_lucky7 = get_bet_amount(game_type_prefix, "super_lucky7", 100)
                elif game_type_prefix == "dtb":
                    self.tiger = get_bet_amount(game_type_prefix, "tiger", 100)
                    self.dragon = get_bet_amount(game_type_prefix, "dragon", 100)
                    self.tie = get_bet_amount(game_type_prefix, "tie", 100)
                    self.tiger_odd = get_bet_amount(game_type_prefix, "tiger_odd", 100)
                    self.tiger_even = get_bet_amount(game_type_prefix, "tiger_even", 100)
                    self.dragon_odd = get_bet_amount(game_type_prefix, "dragon_odd", 100)
                    self.dragon_even = get_bet_amount(game_type_prefix, "dragon_even", 100)
                    self.tiger_red = get_bet_amount(game_type_prefix, "tiger_red", 100)
                    self.tiger_black = get_bet_amount(game_type_prefix, "tiger_black", 100)
                    self.dragon_red = get_bet_amount(game_type_prefix, "dragon_red", 100)
                    self.dragon_black = get_bet_amount(game_type_prefix, "dragon_black", 100)
        
        return GameBets()
    
    return _game_bet_amounts

bac_bet_amounts = game_bet_amounts_factory("bac")
dtb_bet_amounts = game_bet_amounts_factory("dtb")

def pytest_html_report_title(report):
    """修改測試報告的標題"""
    # pytest-html 會自動生成測試報告的標題
    report.title = "WT Automation Test Report"

@pytest.hookimpl(optionalhook=True)
# optionalhook=True：表示這是一個可選的 hook，pytest 系統不會因為找不到這個 hook 而報錯
def pytest_html_results_table_header(cells):
    """修改測試報告的表格標題"""
    # cells 是一個包含現有表頭單元格的列表
    # 在表頭的第2個位置（索引 1）插入新的欄位標題
    # 創建一個 HTML <th> 元素，用於表頭
    cells.insert(1, "<th>Description</th>")
    cells.insert(2, "<th>Parameters</th>")

@pytest.hookimpl(optionalhook=True)
def pytest_html_results_table_row(report, cells):
    """修改測試報告的表格行"""
    # report 是包含測試結果數據的物件
    # cells 一個列表，包含當前測試結果行中所有的表格單元格
    # getattr(report, "custom_description", "") 從報告物件中獲取名為 "custom_description" 的屬性，如果不存在則使用空字符串
    # cells.insert(1, "<td>{}</td>".format(custom_description)) 在每行的第2個位置插入包含描述的單元格
    # "<td>{}</td>"：HTML 表格單元格標籤
    description = getattr(report, "description", "")
    cells.insert(1, "<td>{}</td>".format(description))

    params_str = getattr(report, "params_str", "")
    cells.insert(2, "<td>{}</td>".format(params_str))

@pytest.hookimpl(hookwrapper=True)  # 表示這是一個 hook 包裝器，可以在原始 hook 執行前後運行代碼
def pytest_runtest_makereport(item, call):
    """在測試報告中添加自定義描述"""
    # outcome._result 是測試結果報告物件
    # item.function.__doc__ 獲取測試函數的文檔字符串（docstring）
    # outcome._result.custom_description = item.function.__doc__ 將測試函數的文檔字符串設置為報告物件的 description 屬性
    outcome = yield
    outcome._result.description = item.function.__doc__

    if outcome._result.when == "call":
        if hasattr(item, "callspec") and hasattr(item.callspec, "id"):
            # 直接使用 ids 參數定義的值作為測試的顯示名稱
            # outcome._result.params_str = item.callspec.id

            # TODO: 最後版本, 後續看能不能在做優化, 20250425
            player_data = item.callspec.params.get("player_data")
            if isinstance(player_data, dict):
                currency = player_data.get("currency", "Unknown Currency")
                player_id = player_data.get("player_id", "Unknown Player")
            # params = item.callspec.params.get("play_type", "Unknown Play Type")
            # 多判斷該測試用例是否有參數化, 如果有則取出來
            if "-" in item.callspec.id:
                params = item.callspec.id.split("-")[1:]  # 從"-"split字串後, 直接slice取出後面的參數
                # 檢查分割後的列表是否為空
                if not params:
                    params = "N/A"
            else:
                params = "N/A"

            # outcome._result.params_str = f"currency: {currency}<br> player_id: {player_id}<br> params: {params}"

            # 建立基本參數字符串
            params_parts = [f"currency: {currency}", f"player_id: {player_id}"]

            # 有條件地添加 params 部分
            if params and params != "N/A":
                params_parts.append(f"params: {params}")

            outcome._result.params_str = "<br> ".join(params_parts)

def pytest_collection_modifyitems(items):
    """自定義測試項目排序邏輯"""
    # 定義模組執行順序
    module_order = {
        "test_login": 100, 
        "test_enter_table": 200, 
        "test_bac_betting": 300, 
        "test_bac_balance_check": 400,
        "test_dtb_betting": 500,
        "test_dtb_balance_check": 600,
    }
                        
    def get_order(item):
        # 先按模組排序
        module_name = item.module.__name__.split('.')[-1]
        module_priority = module_order.get(module_name, 999)
        # 同一模組內按函數定義順序排序
        if hasattr(item, 'definition_order'):
            return (module_priority, item.definition_order.value)
        return (module_priority, 0)
    
    # 按自定義順序排序
    items.sort(key=get_order)

@pytest.hookimpl(optionalhook=True)
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """收集測試執行summary"""
    test_summary_info = {}
    
    # 獲取執行統計
    stats = terminalreporter.stats
    passed = len(stats.get("passed", []))
    failed = len(stats.get("failed", []))
    skipped = len(stats.get("skipped", []))
    warnings = len(stats.get("warnings", []))
    error = len(stats.get("error", []))
    xfailed = len(stats.get("xfailed", []))
    xpassed = len(stats.get("xpassed", []))
    
    # 當有失敗的cases時, 取出失敗cases的nodeid
    if failed > 0:
        failed_test_lists = []
        failed_tests = stats.get("failed", [])
        for test in failed_tests:
            nodeid = test.nodeid
            failed_test_lists.append(nodeid)
    
    # 計算總測試數和耗時, deselected 是指被排除的測試用例, 這邊不計算在內
    total = passed + failed + skipped + warnings + error  + xfailed + xpassed
    # 目前這邊計算的時間會跟console上的時間有些微落差, 且與html report不同, html report的時間是實際TestCase執行的時間
    duration = datetime.now().timestamp() - terminalreporter._sessionstarttime

    # 格式化執行時間為可讀格式
    def format_duration(seconds):
        if seconds < 60:
            return f"{seconds:.2f}s"
        minutes, seconds = divmod(seconds, 60)
        if minutes < 60:
            return f"{int(minutes)}m {int(seconds)}s"
        hours, minutes = divmod(minutes, 60)
        return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
    
    formatted_duration = format_duration(duration)

    # # 獲取測試參數資訊
    # player_ids = config.getoption("--player-id")
    # currencies = config.getoption("--currency")
    # seamless = config.getoption("--seamless")
    # # 獲取 pytest marker
    # mark_expr = config.getoption("-m")
    
    # 保存摘要資訊
    test_summary_info.update({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        # "duration": f"{duration:.2f}s", # 取小數後兩位
        "duration": formatted_duration,  # 使用格式化後的時間
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "warnings": warnings,   # 執行過程中產生Python警告的測試
        "error": error,     # 在fixture設置或者teardown過程中發生錯誤的測試, 不是在測試主體內的錯誤
        "xfailed": xfailed, # 預期失敗的測試 (@pytest.mark.xfail)
        "xpassed": xpassed, # 預期失敗的測試，但實際上通過了 (@pytest.mark.xfail標記後, 卻執行成功了)
        "success_rate": f"{passed / total * 100:.1f}%" if total > 0 else "N/A",
        # "player_ids": ", ".join(player_ids) if player_ids else "All",
        # "currencies": ", ".join(currencies) if currencies else "All",
        # "seamless": seamless if seamless else "All",
        # "marker": mark_expr if mark_expr else "All",
        # "environment": sys.platform,
        "failed_test_lists": failed_test_lists if failed > 0 else "N/A",
    })

    send_slack_notification(test_summary_info, config)

def send_slack_notification(test_summary_info, config):
    """發送測試摘要資訊到Slack"""
    try:
        # Slack Webhook URL
        slack_webhook_url = "https://hooks.slack.com/services/EXAMPLE/WEBHOOK/URL"  # Sensitive Information
        
        # 設置 emoji 根據測試結果
        if test_summary_info["failed"] > 0 or test_summary_info["error"] > 0:
            status_emoji = ":python-explode:"
            color = "#FF0000"  # 紅色
        else:
            status_emoji = ":alien:"
            color = "#36a64f"  # 綠色
        
        # construct Slack message
        message = {
            "attachments": [
                {
                    "fallback": f"WT Auto Test Report: {test_summary_info['passed']}/{test_summary_info['total']} passed", # slack在手機端通知顯示的訊息摘要
                    "color": color,
                    "pretext": f"{status_emoji} *WT Automation Test Report*",
                    # "title": f"Test Summary",
                    # "title_link": "https://yourjenkins.com/job/your-test-job",  # 串接到CI/CD (jenkins)的測試報告網址
                    "fields": [
                        {
                            "title": "Result Summary",
                            "value": (
                                f"*Total:* {test_summary_info['total']}\n"
                                f"      • Passed: {test_summary_info['passed']}\n"
                                f"      • Failed: {test_summary_info['failed']}\n"
                                f"      • Skipped: {test_summary_info['skipped']}\n"
                                f"      • Warnings: {test_summary_info['warnings']}\n\n"
                                # f"*filters:*\n"
                                # f"      • Player IDs: {test_summary_info['player_ids']}\n"
                                # f"      • Currencies: {test_summary_info['currencies']}\n"
                                # f"      • Seamless: {test_summary_info['seamless']}\n"
                                # f"      • pytest marker: {test_summary_info['marker']}\n\n"
                                # f"*Execution Summary:*\n"
                                # f"      • Timestamp: {test_summary_info['timestamp']}\n"
                                # f"      • Platform: {test_summary_info['environment']}\n"
                                # f"      • Python Version: {sys.version}\n"
                                # f"      • Pytest Version: {pytest.__version__}\n\n"
                                f"*Duration:* {test_summary_info['duration']}\n"
                                f"*Success Rate:* `{test_summary_info['success_rate']}`\n"
                            ),
                            "short": False
                        },
                        # {
                        #     "title": "Environment",
                        #     "value": test_summary_info['environment'],
                        #     "short": True
                        # }
                    ],
                    "footer": "WT Game Automation by JT",
                    # "footer_icon": "https://platform.slack-edge.com/img/default_application_icon.png",    # 預設的footer icon
                    "footer_icon": "https://emoji.slack-edge.com/T3TBQHWBA/jt%25E6%2588%2591%25E4%25B9%259F%25E4%25B8%258D%25E7%259F%25A5%25E9%2581%2593/e68633b7e8521afb.gif",
                    "ts": int(datetime.now().timestamp())
                }
            ]
        }

        # 添加額外測試參數信息（如果有的話）
        if hasattr(config, "option"):
            if hasattr(config.option, "player_id") and config.option.player_id:
                message["attachments"][0]["fields"].append({
                    "title": "Players",
                    "value": ", ".join(config.option.player_id),
                    "short": True
                })
                
            if hasattr(config.option, "currency") and config.option.currency:
                message["attachments"][0]["fields"].append({
                    "title": "Currencies",
                    "value": ", ".join(config.option.currency),
                    "short": True
                })
                
            if hasattr(config.option, "seamless") and config.option.seamless:
                message["attachments"][0]["fields"].append({
                    "title": "Wallet Type",
                    "value": "Seamless" if config.option.seamless == "True" else "Transfer",
                    "short": True
                })
            if hasattr(config.option, "markexpr") and config.option.markexpr:
                message["attachments"][0]["fields"].append({
                    "title": "Marker",
                    "value": config.option.markexpr,
                    "short": True
                })

        # 如果有失敗的測試，添加失敗測試列表
        if test_summary_info["failed_test_lists"] != "N/A" and test_summary_info["failed"] > 0:
            message["attachments"][0]["fields"].append({
                "title": "Failed Tests",
                "value": "\n".join(test_summary_info["failed_test_lists"]),
                "short": False
            })
        
        # 發送請求到 Slack Webhook
        response = requests.post(
            slack_webhook_url,
            data=json.dumps(message),
            headers={"Content-Type": "application/json"}
        )
        
        # 檢查請求狀態
        # if response.status_code == 200:
        #     logger.info(">>> [SLACK] Test results notification sent successfully")
        # else:
        #     logger.warning(f">>> [SLACK] Failed to send notification. Status: {response.status_code}, Response: {response.text}")
     
    except Exception as e:
        logger.error(f">>> [SLACK] Error sending Slack notification: {e}")

# 以下是pytest hook函數, 用於記錄測試執行的開始和結束時間, 並記錄測試結果
# 測試開始執行時
@pytest.hookimpl(trylast=True)
def pytest_runtest_setup(item):
    """測試設置階段 - 記錄測試開始執行"""
    logger.info(f"Start Test: {item.nodeid}")

# 測試完成後
@pytest.hookimpl(trylast=True)
def pytest_runtest_logreport(report):
    """測試報告階段 - 記錄測試結果"""
    if report.when == "call":  # 只處理測試執行階段的報告
        duration = f"{report.duration:.3f}s"

        if report.passed:
            logger.info(f"TEST PASSED: {report.nodeid}, duration: {duration}")
        elif report.failed:
            logger.error(f"TEST FAILED: {report.nodeid}, duration: {duration}")
            # 如果需要記錄失敗的詳細資訊, 可以取消註釋以下代碼, 但相關資料在html報告中已經有了
            # 記錄失敗的詳細資訊
            if hasattr(report, "longrepr"):
                logger.error(f"Failure details: {report.longrepr}")
        else:
            logger.info(f"SKIPPED: {report.nodeid}")