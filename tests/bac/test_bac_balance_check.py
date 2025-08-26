import asyncio
import pytest
from itertools import combinations

from src.user.enter_table import enter_table
from src.game.bet import (
    BetInfo,
    place_bet,
    set_nocomm_switch,
    set_duobao_switch,
    # raise_bet,
)
from src.game.settle import recv_settle_resp
from src.game.playtype_enums import BacPlayType
from src.utils.balance_checker import BalanceChecker


GAME_TYPE = "BAC"   # 定義遊戲類型
# 定義測試桌台ID, REL先用B001, 已將限制局數調整為60局
TABLE_ID = "B001"

# 定義投注測試用相關參數
play_types = [
    BacPlayType.BANKER,  # playtype=0
    BacPlayType.BANKER_NOCOMMISSION,  # playtype=1
    BacPlayType.PLAYER,  # playtype=2
    BacPlayType.TIE,  # playtype=3
    BacPlayType.BANKER_PAIR,  # playtype=4
    BacPlayType.PLAYER_PAIR,  # playtype=5
    BacPlayType.BANKER_DRAGON_BONUS,  # playtype=8
    BacPlayType.PLAYER_DRAGON_BONUS,  # playtype=9
    BacPlayType.LUCKY6,  # playtype=12
    BacPlayType.DUO_BAO,  # playtype=23
    BacPlayType.LUCKY6_2,  # playtype=24
    BacPlayType.LUCKY6_3,  # playtype=25
    BacPlayType.LUCKY7,  # playtype=26
    BacPlayType.SUPER_LUCKY7,  # playtype=27
]
# 不含免傭莊和多寶的玩法
regular_play_types = [
    item
    for item in play_types
    if item not in (BacPlayType.BANKER_NOCOMMISSION, BacPlayType.DUO_BAO)
]
multi_play_types_combo_2 = list(combinations(regular_play_types, 2))  # 取2個玩法的玩法組合, C(12,2) C12取2
multi_play_types_combo_3 = list(combinations(regular_play_types, 3))  # 取3個玩法的玩法組合, C(12,3) C12取3
multi_play_types_all = list(combinations(regular_play_types, 10))  # 取12個玩法的玩法組合(全取), C(12,12) C12取12
regular_all_combos = (
    multi_play_types_combo_2 + multi_play_types_combo_3 + multi_play_types_all
)   # 資料型態是list of tuple, tuple裡面是BacPlayType的enum

# 不含一般莊和多寶的玩法
play_types_with_nocomm = [
    item for item in play_types if item not in (BacPlayType.BANKER, BacPlayType.DUO_BAO)
]
nocomm_multi_play_types_combo_2 = list(combinations(play_types_with_nocomm, 2))  # 取2個玩法的玩法組合, C(12,2) C12取2
nocomm_multi_play_types_combo_3 = list(combinations(play_types_with_nocomm, 3))  # 取3個玩法的玩法組合, C(12,3) C12取3
nocomm_multi_play_types_all = list(combinations(play_types_with_nocomm, 10))  # 取12個玩法的玩法組合(全取), C(12,12) C12取12
nocomm_all_combos = (
    nocomm_multi_play_types_combo_2
    + nocomm_multi_play_types_combo_3
    + nocomm_multi_play_types_all
)  # 資料型態是list of tuple, tuple裡面是BacPlayType的enum


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
        # print(f"Creating new BalanceChecker for player {player_id}")
        balance_checker = BalanceChecker(player_connection, player_id=player_id)
        await balance_checker.initialize(player_init_balance)
        balance_checkers[player_id] = balance_checker
    else:
        # print(f"Using existing BalanceChecker for player {player_id}")
        balance_checker = balance_checkers[player_id]
    # print(f"player_balance_checker fixture called, creating or retrieving checker for player {player_id}")
    return balance_checker


# HACK: 在沒收到派彩協議或者投注回包timeout的情況下, 可能會有error, 持續觀察 20250510
@pytest.mark.bac_bet
@pytest.mark.bac_balancecheck
@pytest.mark.asyncio(loop_scope="module")
class TestBacBalance:
    """百家樂額度測試"""

    @pytest.mark.basic
    @pytest.mark.parametrize(
        "play_types",
        regular_play_types,
        ids=[f"{pt.name}" for pt in regular_play_types],
    )
    async def test_bac_bet_balance(
        self,
        module_player_connection,
        player_data,
        player_balance_checker,
        bac_bet_amounts,
        play_types,
    ):
        """百家樂基本玩法下注額度確認"""
        # Pre-condition 1. 登入並獲取玩家連線
        player_connection, player_init_balance = module_player_connection
        if player_connection is None:
            pytest.fail("Player connection is None, skipping this case")

        player_id = player_data.get("player_id", "Unknown Player")

        # Pre-condition 2. 直接使用 fixture 提供的balance checker
        balance_checker = player_balance_checker
        # print(f"Using balance checker, current expected balance: {balance_checker.expected_balance}")
        # print(f"Test {play_types.name} using balance checker ID: {id(balance_checker)}")

        # Pre-condition 3. 進入桌台
        enter_table_result = await enter_table(player_connection, TABLE_ID)
        if not enter_table_result:
            pytest.fail("Failed to enter table, skipping this test case")

        # Step 1. 下注
        bet_amounts = getattr(bac_bet_amounts, play_types.name.lower())
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

        # TODO: 先保留, 後續評估是否可以直接從額度歷史資料直接做Test Case的額度確認是否正確的判斷 20250510
        # 打印餘額歷史記錄
        # balance_history = balance_checker.get_history()
        # print(f"餘額歷史: {balance_history}")

    @pytest.mark.basic
    async def test_bac_bet_balance_nocomm(
        self,
        module_player_connection,
        player_data,
        player_balance_checker,
        bac_bet_amounts,
    ):
        """百家樂免傭莊玩法下注額度確認"""
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

        # Pre-condition 4. 開啟免傭開關
        set_switch_result = await set_nocomm_switch(player_connection, 1)
        if set_switch_result is False:
            pytest.fail("Set nocomm switch failed")

        # 等待0.5s, 確保開關已經生效, 因core server也是採用非同步的方式處理
        # 有可能client已經收到切換開關的response, 但server端還沒處理完, 故加入等待
        # await asyncio.sleep(0.5) 

        # Step 1. 下注
        # 注單金額與下注玩法
        betinfos = [
            BetInfo(
                play_type=BacPlayType.BANKER_NOCOMMISSION,
                credit=bac_bet_amounts.banker_nocomm,
            ),
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

        # 下注完成, 且符合預期, 再次關閉免傭開關, 以免影響後續重複的測試
        set_switch_result = await set_nocomm_switch(player_connection, 0)
        if set_switch_result is False:
            pytest.fail("Set nocomm switch failed")

    @pytest.mark.basic
    async def test_bac_bet_balance_duobao(
        self,
        module_player_connection,
        player_data,
        player_balance_checker,
        bac_bet_amounts,
    ):
        """百家樂多寶玩法下注額度確認"""
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

        # Pre-condition 4. 開啟多寶開關
        set_switch_result = await set_duobao_switch(player_connection, 3)
        if set_switch_result is False:
            pytest.fail("Set duobao switch failed")

        # 等待0.5s, 確保開關已經生效, 因core server也是採用非同步的方式處理
        # 有可能client已經收到切換開關的response, 但server端還沒處理完, 故加入等待
        # await asyncio.sleep(0.5)

        # Step 1. 下注
        # 注單金額與下注玩法
        betinfos = [
            BetInfo(play_type=BacPlayType.DUO_BAO, credit=bac_bet_amounts.duo_bao),
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

        # 下注完成, 且符合預期, 再次關閉多寶開關, 以免影響後續重複的測試
        set_switch_result = await set_duobao_switch(player_connection, 4)
        if set_switch_result is False:
            pytest.fail("Set duobao switch failed")

    @pytest.mark.parametrize(
        "play_types_combo",
        regular_all_combos,
        ids=[f"{'/'.join(pt.name for pt in combo)}" for combo in regular_all_combos],
    )
    async def test_bac_bet_balance_multi_playtypes_combo(
        self,
        module_player_connection,
        player_data,
        player_balance_checker,
        bac_bet_amounts,
        play_types_combo,
    ):
        """百家樂多玩法組合下注額度確認"""
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
            bet_amounts = getattr(bac_bet_amounts, play_type.name.lower())
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

    @pytest.mark.parametrize(
        "play_types_combo_nocomm",
        nocomm_all_combos,
        ids=[f"{'/'.join(pt.name for pt in combo)}" for combo in nocomm_all_combos],
    )
    async def test_bac_bet_balance_multi_playtypes_combo_nocomm(
        self,
        module_player_connection,
        player_data,
        player_balance_checker,
        bac_bet_amounts,
        play_types_combo_nocomm,
    ):
        """百家樂免傭莊多玩法組合下注額度確認"""
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

        # Pre-condition 4. 開啟免傭開關
        set_switch_result = await set_nocomm_switch(player_connection, 1)
        if set_switch_result is False:
            pytest.fail("Set nocomm switch failed")

        # 等待0.5s, 確保開關已經生效, 因core server也是採用非同步的方式處理
        # 有可能client已經收到切換開關的response, 但server端還沒處理完, 故加入等待
        # await asyncio.sleep(0.5) 

        # Step 1. 下注
        betinfos = []
        for play_type in play_types_combo_nocomm:
            play_type_name = play_type.name.lower()
            # 因config中, 參數命名為banker_nocomm, 故需對取下注金額的部分特別轉換
            if play_type_name == "banker_nocommission":
                play_type_name = "banker_nocomm"
            bet_amounts = getattr(bac_bet_amounts, play_type_name)
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
        
        # 下注完成, 且符合預期, 再次關閉免傭開關, 以免影響後續重複的測試
        set_switch_result = await set_nocomm_switch(player_connection, 0)
        if set_switch_result is False:
            pytest.fail("Set nocomm switch failed")