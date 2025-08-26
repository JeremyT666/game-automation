import asyncio
import pytest

from src.game.bet import BetInfo, place_bet
from src.game.get_result import recv_game_result
from src.game.playtype_enums import DtbPlayType
from src.game.payout.payout_verifier import PayoutVerifier
from src.game.settle import recv_settle_resp
from src.user.enter_table import enter_table
from src.utils.balance_checker import BalanceChecker
from src.utils.logger import logger
from src.game.payout.payout_calculator import PayoutCalculator

GAME_TYPE = "DTB"  # 定義遊戲類型
# 定義測試桌台ID, REL先用DT99, 已將限制局數調整為60局
TABLE_ID = "DT99"

# 定義投注測試用相關參數
play_types = [
    DtbPlayType.TIGER,  # playtype=1
    DtbPlayType.DRAGON,  # playtype=2
    DtbPlayType.TIE,  # playtype=3
    DtbPlayType.TIGER_ODD,  # playtype=4
    DtbPlayType.TIGER_EVEN,  # playtype=5
    DtbPlayType.DRAGON_ODD,  # playtype=6
    DtbPlayType.DRAGON_EVEN,  # playtype=7
    DtbPlayType.TIGER_RED,  # playtype=8
    DtbPlayType.TIGER_BLACK,  # playtype=9
    DtbPlayType.DRAGON_RED,  # playtype=10
    DtbPlayType.DRAGON_BLACK,  # playtype=11
]


# 因同一玩家重複進行測試時不會再重新建立連線, 但玩家初始金額取得是在一開始登入就取得了
# 如果不透過fixture的方式針對每個玩家做專用的暫存
# 這會導致每次執行test case時都會塞相同的初始金額做balance checker的初始化, 在同一玩家重複進行不同測試時餘額計算會有錯誤
@pytest.fixture(scope="module")
def balance_checkers():
    """提供玩家balance checker的緩存字典

    此 fixture 創建一個空字典, 用於在測試模組執行期間儲存各個玩家的balance checker實例。
    主要解決問題：
    1. 避免每個測試用例都重新創建balance checker
    2. 確保同一玩家在不同測試中使用相同的balance checker實例
    3. 保持餘額計算的連續性和準確性

    Returns:
        dict: 以玩家ID為key, BalanceChecker實例為value的字典
    """
    return {}


@pytest.fixture
async def player_balance_checker(
    balance_checkers, module_player_connection, player_data
):
    """提供玩家專用的balance checker

    為每個玩家創建並緩存一個唯一的balance checker實例, 確保在多個測試中正確追蹤玩家餘額變化。

    Args:
        balance_checkers: 緩存字典, 存儲已創建的balance checker
        module_player_connection: conftest.py中定義的連線fixture
        player_data: 包含玩家ID的測試數據

    Returns:
        BalanceChecker: 該玩家專用的balance checker實例
    """
    player_connection, player_init_balance = module_player_connection
    player_id = player_data.get("player_id", "Unknown Player")

    # 確認一開始連線有成功建立, 並且初始金額有正確取得
    # 如果沒有取得初始金額, 會導致後續的餘額計算錯誤
    if not player_connection or not player_init_balance:
        pytest.fail(
            f"[FIXTURE] Player connection or initial balance error, player_connect: {player_connection}, player_init_balance: {player_init_balance}"
        )

    if player_id not in balance_checkers:
        balance_checker = BalanceChecker(player_connection, player_id=player_id)
        await balance_checker.initialize(player_init_balance)
        balance_checkers[player_id] = balance_checker
    else:
        balance_checker = balance_checkers[player_id]
    return balance_checker


@pytest.mark.dtb_odds
@pytest.mark.single_table
@pytest.mark.asyncio(loop_scope="module")
class TestDtbOdds:
    """龍虎玩法賠率測試"""

    @pytest.mark.parametrize(
        "play_types",
        play_types,
        ids=[
            f"{pt.name}" for pt in play_types
        ],  # 透過comprhension取出每個play_type的名稱, 放至ids中供html report使用
    )
    async def test_dtb_odds(
        self, module_player_connection, 
        player_data,
        player_balance_checker,
        dtb_bet_amounts,
        play_types,
    ):
        """龍虎賠率驗證 - 測試單一玩法下注的輸贏金額"""

        MAX_ROUNDS = 50  # 最大測試輪數
        
        # 追蹤該玩法的測試狀態
        test_status = {
            "win_tested": False,
            "lose_tested": False,
            "win_count": 0,
            "lose_count": 0
        }

        for round in range(1, MAX_ROUNDS + 1):
            # 如果已經測試完輸贏兩種情況，提前結束
            if test_status["win_tested"] and test_status["lose_tested"]:
                logger.info(f"Both WIN and LOSE scenarios tested for {play_types.name} after {round-1} rounds")
                break
            # Step 1. 登入 (已由 fixture 完成)
            player_connection, player_init_balance = module_player_connection
            if player_connection is None:
                pytest.fail("Player connection is None, skipping this case")

            player_id = player_data.get("player_id", "Unknown Player")

            balance_checker = player_balance_checker

            # Step 2. 進入桌台
            enter_table_result = await enter_table(player_connection, TABLE_ID)
            if not enter_table_result:
                pytest.fail("Failed to enter table, skipping this test case")

            # Step 3. 下注
            # 注單金額與下注玩法
            bet_amounts = getattr(dtb_bet_amounts, play_types.name.lower())
            
            betinfos = [
                BetInfo(play_type=play_types, credit=bet_amounts),
            ]

            bet_result = await place_bet(player_connection, betinfos, GAME_TYPE, TABLE_ID)
            if not bet_result["result"]:
                pytest.fail("Bet failed, skipping this test case")

            # # 紀錄下注金額, 以便後續計算使用
            # total_bet_amounts = sum([bet.credit for bet in betinfos])

            gmcode = bet_result["bet_resp_gmcode"]

            # Expected 1: 下注後檢查額度是否正確扣除, 預期從Server取得的額度異動與local端計算一致
            balanced, message = await balance_checker.check_after_bet(
                bet_amounts, gmcode
            )
            if not balanced:
                pytest.fail(f"Balance check after bet failed: {message}")

            try:
                # 同時監聽局結果(0x020012)和派彩結算(0x020310)協議
                logger.info(f"Waiting for game result and settle response for player on table {TABLE_ID}, gmcode: {gmcode}")
                result = await asyncio.wait_for(
                    asyncio.gather(
                        recv_game_result(player_connection, TABLE_ID, gmcode),
                        recv_settle_resp(player_connection, TABLE_ID, True),
                        return_exceptions=True  # 即便其中一個失敗也繼續
                    ), 
                    timeout=30  # 設定一個合理的超時時間
                )
                game_result_data, settle_result_data = result

                # 初始化變量
                game_result = None
                settle_success = False

                game_result_success, game_result = game_result_data
                settle_success, settle_data = settle_result_data

                if not game_result_success:
                    pytest.fail("Failed to receive game result, skipping this test case")
                if not settle_success:
                    pytest.fail("Failed to receive settle response, skipping this test case")

                # 只有兩個協議都成功收到後才進行後續處理
                if game_result and settle_success:
                    # 驗證賠率
                    try:
                        # Expected 2. 驗證賠率計算
                        verify_result, verify_detail = await PayoutVerifier.verify_game_payout("dtb", game_result, betinfos, settle_data)
                        assert verify_result is True, f"Payout verification failed: {verify_detail}"

                        # 判斷該玩法是否獲勝並更新測試狀態
                        # 修正傳入參數, 應是game_result["card_analysis"]
                        is_winning = PayoutCalculator._check_dtb_winning(play_types, game_result["card_analysis"])
                        logger.info(f"Gmcode: {gmcode}, Winning: {is_winning}")
                        if is_winning:
                            test_status["win_tested"] = True
                            test_status["win_count"] += 1
                            logger.info(f"{play_types.name} WIN scenario verified in round {round}")
                        else:
                            test_status["lose_tested"] = True  
                            test_status["lose_count"] += 1
                            logger.info(f"{play_types.name} LOSE scenario verified in round {round}")

                        # Expected 3. 確認派彩金額與預期一致
                        balanced, message = await balance_checker.check_after_settlement(
                            settle_data["order_detail"][play_types.value], bet_amounts, gmcode
                        )
                        assert balanced is True, message

                    except Exception as e:
                        pytest.fail(f"Error during payout verification: {e}")
                else:
                    pytest.fail("Either game result or settle response was not received successfully")

            except asyncio.TimeoutError:
                pytest.fail("Timeout while waiting for game result or settle response")
            except Exception as e:
                pytest.fail(f"Error during game result or settle response: {e}")

            logger.info(
                f"Round {round}/{MAX_ROUNDS} completed for player {player_id} with play type {play_types.name}"
            )

        # 測試完成後，驗證是否兩種情況都測試到了
        if not (test_status["win_tested"] and test_status["lose_tested"]):
            missing_scenarios = []
            if not test_status["win_tested"]:
                missing_scenarios.append("WIN")
            if not test_status["lose_tested"]:
                missing_scenarios.append("LOSE")

            logger.warning(
                f"Failed to test all scenarios for {play_types.name} after {MAX_ROUNDS} rounds. "
                f"Missing: {', '.join(missing_scenarios)}. "
                f"Win count: {test_status['win_count']}, Lose count: {test_status['lose_count']}"
            )
        
        logger.info(
            f"{play_types.name} test completed successfully!"
            f"Win count: {test_status['win_count']}, Lose count: {test_status['lose_count']}"
        )
