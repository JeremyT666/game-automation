import pytest
from itertools import combinations

from src.user.enter_table import enter_table
from src.game.bet import BetInfo, place_bet
from src.game.settle import recv_settle_resp
from src.game.playtype_enums import DtbPlayType
from src.utils.balance_checker import BalanceChecker


GAME_TYPE = "DTB"  # 定義遊戲類型
# 定義測試桌台ID, REL先用DT99, 要測試前記得確認操盤玩法限制局數, 以及AutoDealer換靴設定
TABLE_ID = "DT99"

# 定義投注測試用相關參數
dtb_play_types = [
    DtbPlayType.TIGER,   # playtype=1
    DtbPlayType.DRAGON,  # playtype=2
    DtbPlayType.TIE,     # playtype=3
    DtbPlayType.TIGER_ODD,  # playtype=4
    DtbPlayType.TIGER_EVEN, # playtype=5
    DtbPlayType.DRAGON_ODD, # playtype=6
    DtbPlayType.DRAGON_EVEN, # playtype=7
    DtbPlayType.TIGER_RED, # playtype=8
    DtbPlayType.TIGER_BLACK, # playtype=9
    DtbPlayType.DRAGON_RED, # playtype=10
    DtbPlayType.DRAGON_BLACK, # playtype=11
]
multi_play_types_combo_2 = list(combinations(dtb_play_types, 2))  # 取2個玩法的玩法組合, C(11,2) C11取2
multi_play_types_combo_3 = list(combinations(dtb_play_types, 3))  # 取3個玩法的玩法組合, C(11,3) C11取3
multi_play_types_all = list(combinations(dtb_play_types, 11))  # 取11個玩法的玩法組合(全取), C(11,11) C11取11
regular_all_combos = (
    multi_play_types_combo_2 + multi_play_types_combo_3 + multi_play_types_all
)   # 資料型態是list of tuple, tuple裡面是DtbPlayType的enum

# 定義測試桌台ID, REL先用DT99, 要測試前記得確認操盤玩法限制局數, 以及AutoDealer換靴設定
TABLE_ID = "DT99"


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


# HACK: 在沒收到派彩協議或者投注回包timeout的情況下, 可能會有error, 持續觀察 20250510
@pytest.mark.dtb_bet
@pytest.mark.dtb_balancecheck
@pytest.mark.asyncio(loop_scope="module")
class TestDtbBalance:
    """龍虎額度測試"""

    @pytest.mark.parametrize(
        "play_types",
        dtb_play_types,
        ids=[f"{pt.name}" for pt in dtb_play_types],
    )
    async def test_dtb_bet_balance(
        self,
        module_player_connection,
        player_data,
        player_balance_checker,
        dtb_bet_amounts,
        play_types,
    ):
        """龍虎基本玩法下注額度確認"""
        # Pre-condition 1. 登入並獲取玩家連線
        player_connection, player_init_balance = module_player_connection
        if player_connection is None:
            pytest.fail("Player connection is None, skipping this case")

        player_id = player_data.get("player_id", "Unknown Player")

        # Pre-condition 2. 直接使用 fixture 提供的balance checker
        balance_checker = player_balance_checker

        # Pre-condition 3. 進入桌台
        enter_table_result = await enter_table(player_connection, TABLE_ID)
        if not enter_table_result:
            pytest.fail("Failed to enter table, skipping this test case")

        # Step 1. 下注
        bet_amounts = getattr(dtb_bet_amounts, play_types.name.lower())
        betinfos = [
            BetInfo(play_type=play_types, credit=bet_amounts),
        ]

        bet_result = await place_bet(player_connection, betinfos, GAME_TYPE, TABLE_ID)
        if not bet_result["result"]:
            pytest.fail("Bet failed, skipping this test case")

        # 紀錄下注金額, 以便後續計算使用
        total_bet_amounts = sum([bet.credit for bet in betinfos])
        # 取下注局號, 以便記錄額度歷史使用
        gmcode = bet_result["bet_resp_gmcode"]

        # Expected 1: 下注後檢查額度是否正確扣除, 預期從Server取得的額度異動與local端計算一致
        balanced, message = await balance_checker.check_after_bet(
            total_bet_amounts, gmcode
        )
        assert balanced is True, message

        # Step 2. 等待結算
        settle_result, win_amount = await recv_settle_resp(player_connection, TABLE_ID)
        if not settle_result:
            pytest.fail("Get settle result failed, skipping this test case")

        # Expected 2. 結算後再次查餘額是否正確, 預期從Server取得的額度異動與local端計算一致
        balanced, message = await balance_checker.check_after_settlement(
            win_amount, total_bet_amounts, gmcode
        )
        assert balanced is True, message

    @pytest.mark.parametrize(
        "play_types_combo",
        regular_all_combos,
        ids=[f"{'/'.join(pt.name for pt in combo)}" for combo in regular_all_combos],
    )
    async def test_dtb_bet_balance_multi_playtypes_combo(
        self,
        module_player_connection,
        player_data,
        player_balance_checker,
        dtb_bet_amounts,
        play_types_combo,
    ):
        """龍虎多玩法組合下注額度確認"""
        # Pre-condition 1. 登入並獲取玩家連線
        player_connection, player_init_balance = module_player_connection
        if player_connection is None:
            pytest.fail("Player connection is None, skipping this test case")

        player_id = player_data.get("player_id", "Unknown Player")

        # Pre-condition 2. 直接使用 fixture 提供的balance checker
        balance_checker = player_balance_checker

        # Pre-condition 3. 進入桌台
        enter_table_result = await enter_table(player_connection, TABLE_ID)
        if not enter_table_result:
            pytest.fail("Failed to enter table, skipping this test case")

        # Step 1. 下注
        betinfos = []
        for play_type in play_types_combo:
            bet_amounts = getattr(dtb_bet_amounts, play_type.name.lower())
            betinfos.append(BetInfo(play_type=play_type, credit=bet_amounts))

        bet_result = await place_bet(player_connection, betinfos, GAME_TYPE, TABLE_ID)
        if not bet_result["result"]:
            pytest.fail("Bet failed, skipping this test case")

        # 紀錄下注金額, 以便後續計算使用
        total_bet_amounts = sum([bet.credit for bet in betinfos])
        # 取下注局號, 以便記錄額度歷史使用
        gmcode = bet_result["bet_resp_gmcode"]

        # Expected 1: 下注後檢查額度是否正確扣除, 預期從Server取得的額度異動與local端計算一致
        balanced, message = await balance_checker.check_after_bet(
            total_bet_amounts, gmcode
        )
        assert balanced is True, message

        # Step 2. 等待結算
        settle_result, win_amount = await recv_settle_resp(player_connection, TABLE_ID)
        if not settle_result:
            pytest.fail("Get settle result failed, skipping this test case")

        # Expected 2. 結算後再次查餘額是否正確, 預期從Server取得的額度異動與local端計算一致
        balanced, message = await balance_checker.check_after_settlement(
            win_amount, total_bet_amounts, gmcode
        )
        assert balanced is True, message