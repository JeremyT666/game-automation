import asyncio
import pytest
import random
from itertools import combinations

from src.game.playtype_enums import BacPlayType
from src.game.bet import (
    BetInfo,
    place_bet,
    set_nocomm_switch,
    set_duobao_switch,
    raise_bet,
)
from src.user.enter_table import enter_table


GAME_TYPE = "BAC"   # 定義遊戲類型
# 定義測試桌台ID, REL先用B001, 已將限制局數調整為60局
TABLE_ID = "B001"

# 定義投注測試用相關參數
play_types = [
    BacPlayType.BANKER, # playtype=0
    BacPlayType.BANKER_NOCOMMISSION,    # playtype=1
    BacPlayType.PLAYER, # playtype=2
    BacPlayType.TIE,    # playtype=3
    BacPlayType.BANKER_PAIR,    # playtype=4
    BacPlayType.PLAYER_PAIR,    # playtype=5
    # BacPlayType.ANY_PAIR,
    # BacPlayType.PERFECT_PAIR,
    BacPlayType.BANKER_DRAGON_BONUS,    # playtype=8
    BacPlayType.PLAYER_DRAGON_BONUS,    # playtype=9
    BacPlayType.LUCKY6,   # playtype=12
    BacPlayType.DUO_BAO,    # playtype=23
    BacPlayType.LUCKY6_2,   # playtype=24
    BacPlayType.LUCKY6_3,   # playtype=25
    BacPlayType.LUCKY7,  # playtype=26
    BacPlayType.SUPER_LUCKY7,   # playtype=27
]

# 不含免傭莊和多寶的玩法
regular_play_types = [
    item
    for item in play_types
    if item not in (BacPlayType.BANKER_NOCOMMISSION, BacPlayType.DUO_BAO)
]
multi_play_types_combo_2 = list(combinations(regular_play_types, 2))  # 取2個玩法的玩法組合, C(12,2) C12取2
multi_play_types_combo_3 = list(combinations(regular_play_types, 3))  # 取3個玩法的玩法組合, C(12,3) C12取3
multi_play_types_all = list(combinations(regular_play_types, 12))  # 取12個玩法的玩法組合(全取), C(12,12) C12取12
regular_all_combos = (
    multi_play_types_combo_2 + multi_play_types_combo_3 + multi_play_types_all
)   # 資料型態是list of tuple, tuple裡面是BacPlayType的enum

# 不含一般莊和多寶的玩法
play_types_with_nocomm = [
    item for item in play_types if item not in (BacPlayType.BANKER, BacPlayType.DUO_BAO)
]
nocomm_multi_play_types_combo_2 = list(combinations(play_types_with_nocomm, 2))  # 取2個玩法的玩法組合, C(12,2) C12取2
nocomm_multi_play_types_combo_3 = list(combinations(play_types_with_nocomm, 3))  # 取2個玩法的玩法組合, C(12,3) C12取3
nocomm_multi_play_types_all = list(combinations(play_types_with_nocomm, 12))  # 取12個玩法的玩法組合(全取), C(12,12) C12取12
nocomm_all_combos = (
    nocomm_multi_play_types_combo_2
    + nocomm_multi_play_types_combo_3
    + nocomm_multi_play_types_all
)   # 資料型態是list of tuple, tuple裡面是BacPlayType的enum


@pytest.mark.bac_bet
@pytest.mark.single_table
@pytest.mark.basic
@pytest.mark.asyncio(loop_scope="module")
class TestBacSingleTypeBetting:
    """百家樂單一玩法下注測試"""

    @pytest.mark.parametrize(
        "play_types",
        regular_play_types,
        ids=[f"{pt.name}" for pt in regular_play_types],  # 透過comprhension取出每個play_type的名稱, 放至ids中供html report使用
    )
    async def test_bac_bet_single_playtype(
        self, module_player_connection, bac_bet_amounts, play_types
    ):
        """百家樂單一玩法下注_一般莊與其他玩法"""
        # Step 1. 登入 (已由 fixture 完成)
        player_connection, player_init_balance = module_player_connection
        if player_connection is None:
            pytest.fail("Player connection object should not be None")

        # Step 2. 進入桌台
        enter_table_result = await enter_table(player_connection, TABLE_ID)
        if not enter_table_result:
            pytest.fail(f"Enter Table failed: {TABLE_ID}")


        # Step 3. 下注
        # 注單金額與下注玩法
        bet_amounts = getattr(bac_bet_amounts, play_types.name.lower())
        betinfos = [
            BetInfo(play_type=play_types, credit=bet_amounts),
        ]

        # Expected: 下注成功且bet_resp_code為0
        bet_result = await place_bet(player_connection, betinfos, GAME_TYPE, TABLE_ID)
        assert (
            bet_result["result"] is True and bet_result["bet_resp_code"] == 0
        ), f"Expected bet to succeed, got result={bet_result['result']}, code={bet_result['bet_resp_code']}"

    async def test_bac_bet_single_playtype_no_comm(
        self, module_player_connection, bac_bet_amounts
    ):
        """百家樂單一玩法下注_免傭莊"""
        # Pre-condition 1. 直接拿已登入的狀態, 不再重新登入一次
        player_connection, player_init_balance = module_player_connection
        if player_connection is None:
            pytest.fail("Player connection object should not be None")
        # 直接重新進桌一次, 避免因為局數被踢離桌
        enter_table_result = await enter_table(player_connection, TABLE_ID)
        if not enter_table_result:
            pytest.fail(f"Enter Table failed: {TABLE_ID}")
        # Pre-condition 2. 開啟免傭開關
        set_switch_result = await set_nocomm_switch(
            player_connection, 1
        )
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

        # Expected: 下注成功且bet_resp_code為0
        bet_result = await place_bet(player_connection, betinfos, GAME_TYPE, TABLE_ID)
        assert (
            bet_result["result"] is True and bet_result["bet_resp_code"] == 0
        ), f"Expected bet to succeed, got result={bet_result['result']}, code={bet_result['bet_resp_code']}"

        # 下注完成, 且符合預期, 再次關閉免傭開關, 以免影響後續重複的測試
        set_switch_result = await set_nocomm_switch(player_connection, 0)
        if set_switch_result is False:
            pytest.fail("Set nocomm switch failed")

    async def test_bac_bet_single_playtype_duo_bao(
        self, module_player_connection, bac_bet_amounts
    ):
        """百家樂單一玩法下注_多寶"""
        # Pre-Condition: 直接拿已登入的狀態, 不會再重新登入一次
        player_connection, player_init_balance = module_player_connection
        if player_connection is None:
            pytest.fail("Player connection object should not be None")
        # 直接重新進桌一次, 避免因為局數被踢離桌
        enter_table_result = await enter_table(player_connection, TABLE_ID)
        if not enter_table_result:
            pytest.fail(f"Enter Table failed: {TABLE_ID}")
        # 設定多寶flag - 開啟
        duobao_switch_result = await set_duobao_switch(player_connection, 3)
        if duobao_switch_result is False:
            pytest.fail("Set duobao switch failed")
        
        # 等待0.5s, 確保開關已經生效, 因core server也是採用非同步的方式處理
        # 有可能client已經收到切換開關的response, 但server端還沒處理完, 故加入等待
        # await asyncio.sleep(0.5)

        # Step 1. 直接下注
        # 注單金額與下注玩法
        betinfos = [
            BetInfo(play_type=BacPlayType.DUO_BAO, credit=bac_bet_amounts.duo_bao),
        ]

        # Expected: 下注成功且bet_resp_code為0
        bet_result = await place_bet(player_connection, betinfos, GAME_TYPE, TABLE_ID)
        assert (
            bet_result["result"] is True and bet_result["bet_resp_code"] == 0
        ), f"Expected bet to succeed, got result={bet_result['result']}, code={bet_result['bet_resp_code']}"

        # 下注完成, 且符合預期, 再次切換多寶flag為原本的default值, 以免影響後續重複的測試
        duobao_switch_result = await set_duobao_switch(player_connection, 4)
        if duobao_switch_result is False:
            pytest.fail("Set duobao switch failed")


@pytest.mark.bac_bet
@pytest.mark.single_table
@pytest.mark.asyncio(loop_scope="module")
class TestBacMultiTypeBetting:
    """百家樂多玩法組合下注測試"""

    @pytest.mark.parametrize(
        "play_types_combo",
        regular_all_combos,
        ids=[f"{'/'.join(pt.name for pt in combo)}" for combo in regular_all_combos],   # 透過comprhension取出每個play_type的名稱, 放至ids中供html report使用
    )
    async def test_bac_bet_multi_playtypes(
        self, module_player_connection, bac_bet_amounts, play_types_combo
    ):
        """百家樂多玩法組合下注_一般莊與其他玩法組合"""
        # Pre-Condition: 直接拿已登入的狀態, 不會再重新登入一次
        player_connection, player_init_balance = module_player_connection
        if player_connection is None:
            pytest.fail("Player connection object should not be None")
        # 直接重新進桌一次, 避免因為局數被踢離桌
        enter_table_result = await enter_table(player_connection, TABLE_ID)
        if not enter_table_result:
            pytest.fail(f"Enter Table failed: {TABLE_ID}")

        # Step 1. 直接下注
        # 注單金額與下注玩法
        betinfos = []
        for play_type in play_types_combo:
            bet_amounts = getattr(bac_bet_amounts, play_type.name.lower())
            betinfos.append(BetInfo(play_type=play_type, credit=bet_amounts))

        # Expected: 下注成功且bet_resp_code為0
        bet_result = await place_bet(player_connection, betinfos, GAME_TYPE, TABLE_ID)
        assert (
            bet_result["result"] is True and bet_result["bet_resp_code"] == 0
        ), f"Expected bet to succeed, got result={bet_result['result']}, code={bet_result['bet_resp_code']}"

    @pytest.mark.parametrize(
        "play_types_combo_nocomm",
        nocomm_all_combos,
        ids=[f"{'/'.join(pt.name for pt in combo)}" for combo in nocomm_all_combos],   # 透過comprhension取出每個play_type的名稱, 放至ids中供html report使用
    )
    async def test_bac_bet_multi_playtypes_nocomm(
        self, module_player_connection, bac_bet_amounts, play_types_combo_nocomm
    ):
        """百家樂多玩法組合下注_免傭莊與其他玩法組合"""
        # Pre-Condition: 直接拿已登入的狀態, 不會再重新登入一次
        player_connection, player_init_balance = module_player_connection
        if player_connection is None:
            pytest.fail("Player connection object should not be None")
        # 直接重新進桌一次, 避免因為局數被踢離桌
        enter_table_result = await enter_table(player_connection, TABLE_ID)
        if not enter_table_result:
            pytest.fail(f"Enter Table failed: {TABLE_ID}")
        # Pre-condition 2. 開啟免傭開關
        set_switch_result = await set_nocomm_switch(
            player_connection, 1
        )
        if set_switch_result is False:
            pytest.fail("Set nocomm switch failed")

        # 等待0.5s, 確保開關已經生效, 因core server也是採用非同步的方式處理
        # 有可能client已經收到切換開關的response, 但server端還沒處理完, 故加入等待
        # await asyncio.sleep(0.5)

        # Step 1. 直接下注
        # 注單金額與下注玩法
        betinfos = []
        for play_type in play_types_combo_nocomm:
            play_type_name = play_type.name.lower()
            # 因config中, 參數命名為banker_nocomm, 故需對取下注金額的部分特別轉換
            if play_type_name == "banker_nocommission":
                play_type_name = "banker_nocomm"
            bet_amounts = getattr(bac_bet_amounts, play_type_name)
            betinfos.append(BetInfo(play_type=play_type, credit=bet_amounts))

        # Expected: 下注成功且bet_resp_code為0
        bet_result = await place_bet(player_connection, betinfos, GAME_TYPE, TABLE_ID)
        assert (
            bet_result["result"] is True and bet_result["bet_resp_code"] == 0
        ), f"Expected bet to succeed, got result={bet_result['result']}, code={bet_result['bet_resp_code']}"

        # 下注完成, 且符合預期, 再次關閉免傭開關, 以免影響後續重複的測試
        set_switch_result = await set_nocomm_switch(player_connection, 0)
        if set_switch_result is False:
            pytest.fail("Set nocomm switch failed")

    
# BacGameServer移除免傭開關驗證, 但仍保留相關測試用例, 加上skip marker, 以便處理未來可能的需求變更
# Server端不看免傭開關0/1做為能否下注免傭莊/一般莊的限制, 但UI端仍然會有相關限制
# REL Release Note: https://wiki.star-link-oa.com/pages/viewpage.action?pageId=156679266
@pytest.mark.bac_bet
@pytest.mark.single_table
@pytest.mark.skip(reason="Bac GameServer removed flag validation for nocomm betting")
@pytest.mark.asyncio(loop_scope="module")
class TestBacNoCommSwitch:
    """百家樂免傭開關測試"""

    async def test_bac_bet_single_playtype_1_with_nocomm_switch_0(
        self, module_player_connection, bac_bet_amounts
    ):
        """百家樂_未開免傭_下注免傭莊(預期失敗_error=13)"""
        # Pre-condition: 直接拿已登入的狀態, 不再重新登入一次
        player_connection, player_init_balance = module_player_connection
        if player_connection is None:
            pytest.fail("Player connection object should not be None")
        # 直接重新進桌一次, 避免因為局數被踢離桌
        enter_table_result = await enter_table(player_connection, TABLE_ID)
        if not enter_table_result:
            pytest.fail(f"Enter Table failed: {TABLE_ID}")

        # Step 1. 設定免傭開關
        set_switch_result = await set_nocomm_switch(
            player_connection, 0
        )
        if set_switch_result is False:
            pytest.fail("Set nocomm switch failed")

        # 等待0.5s, 確保開關已經生效, 因core server也是採用非同步的方式處理
        # 有可能client已經收到切換開關的response, 但server端還沒處理完, 故加入等待
        # await asyncio.sleep(0.5)

        # Step 2. 下注
        # 注單金額與下注玩法
        betinfos = [
            BetInfo(
                play_type=BacPlayType.BANKER_NOCOMMISSION,
                credit=bac_bet_amounts.banker_nocomm,
            ),
        ]

        # Expected: 下注失敗且bet_resp_code為13
        bet_result = await place_bet(player_connection, betinfos, GAME_TYPE, TABLE_ID)
        assert (
            bet_result["result"] is False and bet_result["bet_resp_code"] == 13
        ), f"Expected bet to fail with code 13, got result={bet_result['result']}, code={bet_result['bet_resp_code']}"

    @pytest.mark.parametrize(
        "all_play_types_with_nocomm",
        nocomm_multi_play_types_all,    # 因為不是測試組合, 而是全玩法下注
        ids=["all play types with nocomm banker(1/2/3/4/5/8/9/12/24/25)"],
    )
    async def test_bac_bet_banker_nocomm_all_playtypes_with_nocomm_switch_0(
        self, module_player_connection, bac_bet_amounts, all_play_types_with_nocomm
    ):
        """百家樂_未開免傭_下注免傭莊全玩法(預期失敗_error=13)"""
        # Pre-condition: 直接拿已登入的狀態, 不再重新登入一次
        player_connection, player_init_balance = module_player_connection
        if player_connection is None:
            pytest.fail("Player connection object should not be None")
        # 直接重新進桌一次, 避免因為局數被踢離桌
        enter_table_result = await enter_table(player_connection, TABLE_ID)
        if not enter_table_result:
            pytest.fail(f"Enter Table failed: {TABLE_ID}")

        # Step 1. 設定免傭開關
        set_switch_result = await set_nocomm_switch(
            player_connection, 0
        )
        if set_switch_result is False:
            pytest.fail("Set nocomm switch failed")

        # 等待0.5s, 確保開關已經生效, 因core server也是採用非同步的方式處理
        # 有可能client已經收到切換開關的response, 但server端還沒處理完, 故加入等待
        # await asyncio.sleep(0.5)

        # Step 2. 下注
        # 注單金額與下注玩法
        betinfos = []
        for play_type in all_play_types_with_nocomm:
            play_type_name = play_type.name.lower()
            if play_type_name == "banker_nocommission":
                play_type_name = "banker_nocomm"
            bet_amounts = getattr(bac_bet_amounts, play_type_name)
            betinfos.append(BetInfo(play_type=play_type, credit=bet_amounts))

        # Expected: 下注失敗且bet_resp_code為13
        bet_result = await place_bet(player_connection, betinfos, GAME_TYPE, TABLE_ID)
        assert (
            bet_result["result"] is False and bet_result["bet_resp_code"] == 13
        ), f"Expected bet to fail with code 13, got result={bet_result['result']}, code={bet_result['bet_resp_code']}"

    async def test_bac_bet_single_playtype_0_with_nocomm_switch_1(
        self, module_player_connection, bac_bet_amounts
    ):
        """百家樂_開免傭_下注一般莊(預期失敗_error=13)"""
        # Pre-condition 1. 直接拿已登入的狀態, 不再重新登入一次
        player_connection, player_init_balance = module_player_connection
        if player_connection is None:
            pytest.fail("Player connection object should not be None")
        # 直接重新進桌一次, 避免因為局數被踢離桌
        enter_table_result = await enter_table(player_connection, TABLE_ID)
        if not enter_table_result:
            pytest.fail(f"Enter Table failed: {TABLE_ID}")
        
        # Setp 1. 開啟免傭開關
        set_switch_result = await set_nocomm_switch(
            player_connection, 1
        )
        if set_switch_result is False:
            pytest.fail("Set nocomm switch failed")

        # 等待0.5s, 確保開關已經生效, 因core server也是採用非同步的方式處理
        # 有可能client已經收到切換開關的response, 但server端還沒處理完, 故加入等待
        # await asyncio.sleep(0.5)

        # Step 2. 下注
        # 注單金額與下注玩法
        betinfos = [
            BetInfo(
                play_type=BacPlayType.BANKER,
                credit=bac_bet_amounts.banker,
            ),
        ]

        # Expected: 下注失敗且bet_resp_code為13
        bet_result = await place_bet(player_connection, betinfos, GAME_TYPE, TABLE_ID)
        assert (
            bet_result["result"] is False and bet_result["bet_resp_code"] == 13
        ), f"Expected bet to fail with code 13, got result={bet_result['result']}, code={bet_result['bet_resp_code']}"

        # 下注完成, 且符合預期, 再次關閉免傭開關, 以免影響後續重複的測試
        set_switch_result = await set_nocomm_switch(
            player_connection, 0
        )
        if set_switch_result is False:
            pytest.fail("Set nocomm switch failed")

    @pytest.mark.parametrize(
        "all_regular_play_types",
        multi_play_types_all,    # 因為不是測試組合, 而是全玩法下注
        ids=["all regular play types with banker(0/2/3/4/5/8/9/12/24/25)"],
    )
    async def test_bac_bet_banker_all_playtypes_with_nocomm_switch_1(
        self, module_player_connection, bac_bet_amounts, all_regular_play_types
    ):
        """百家樂_開免傭_下注一般莊全玩法(預期失敗_error=13)"""
        # Pre-condition 1. 直接拿已登入的狀態, 不再重新登入一次
        player_connection, player_init_balance = module_player_connection
        if player_connection is None:
            pytest.fail("Player connection object should not be None")
        # 直接重新進桌一次, 避免因為局數被踢離桌
        enter_table_result = await enter_table(player_connection, TABLE_ID)
        if not enter_table_result:
            pytest.fail(f"Enter Table failed: {TABLE_ID}")
        
        # Step 1. 開啟免傭開關
        set_switch_result = await set_nocomm_switch(
            player_connection, 1
        )
        if set_switch_result is False:
            pytest.fail("Set nocomm switch failed")

        # 等待0.5s, 確保開關已經生效, 因core server也是採用非同步的方式處理
        # 有可能client已經收到切換開關的response, 但server端還沒處理完, 故加入等待
        # await asyncio.sleep(0.5)

        # Step 2. 下注
        # 注單金額與下注玩法
        betinfos = []
        for play_type in all_regular_play_types:
            bet_amounts = getattr(bac_bet_amounts, play_type.name.lower())
            betinfos.append(BetInfo(play_type=play_type, credit=bet_amounts))
        
        # Expected: 下注失敗且bet_resp_code為13
        bet_result = await place_bet(player_connection, betinfos, GAME_TYPE, TABLE_ID)
        assert (
            bet_result["result"] is False and bet_result["bet_resp_code"] == 13
        ), f"Expected bet to fail with code 13, got result={bet_result['result']}, code={bet_result['bet_resp_code']}"

        # 下注完成, 且符合預期, 再次關閉免傭開關, 以免影響後續重複的測試
        set_switch_result = await set_nocomm_switch(
            player_connection, 0
        )
        if set_switch_result is False:
            pytest.fail("Set nocomm switch failed")

    @pytest.mark.skip(reason="CoreServer does not block the switch in this scenario, it's only block by live-ui.")
    async def test_bac_bet_enable_nocomm_after_bet(
        self, module_player_connection, bac_bet_amounts
    ):
        """[skip]下注後開啟免傭開關(目前只有UI有限制)"""
        # Pre-condition 1. 直接拿已登入的狀態, 不再重新登入一次
        player_connection, player_init_balance = module_player_connection
        if player_connection is None:
            pytest.fail("Player connection object should not be None")
        # 直接重新進桌一次, 避免因為局數被踢離桌
        enter_table_result = await enter_table(player_connection, TABLE_ID)
        if not enter_table_result:
            pytest.fail(f"Enter Table failed: {TABLE_ID}")
        # Pre-condition 2. 關閉免傭開關
        set_switch_result = await set_nocomm_switch(
            player_connection, 0
        )
        if set_switch_result is False:
            pytest.fail("Set nocomm switch failed")

        # 等待0.5s, 確保開關已經生效, 因core server也是採用非同步的方式處理
        # 有可能client已經收到切換開關的response, 但server端還沒處理完, 故加入等待
        # await asyncio.sleep(0.5)

        # Step 1. 下注
        # 注單金額與下注玩法
        betinfos = [
            BetInfo(
                play_type=BacPlayType.BANKER,
                credit=bac_bet_amounts.banker,
            ),
        ]

        # Expected: 下注成功且bet_resp_code為0
        bet_result = await place_bet(player_connection, betinfos, GAME_TYPE, TABLE_ID)
        assert (
            bet_result["result"] is True and bet_result["bet_resp_code"] == 0
        ), f"Expected bet to succeed, got result={bet_result['result']}, code={bet_result['bet_resp_code']}"

        # Step 2. 開啟免傭開關
        set_switch_result = await set_nocomm_switch(player_connection, 1)
        # Expected: 開啟免傭開關失敗
        assert set_switch_result is False, "can't set nocomm switch after bet"

    @pytest.mark.skip(reason="CoreServer does not block the switch in this scenario, it's only block by live-ui.")
    async def test_bac_bet_disable_nocomm_after_bet(
        self, module_player_connection, bac_bet_amounts
    ):
        """[skip]下注後關閉免傭開關(目前只有UI有限制)"""
        # Pre-condition 1. 直接拿已登入的狀態, 不再重新登入一次
        player_connection, player_init_balance = module_player_connection
        if player_connection is None:
            pytest.fail("Player connection object should not be None")
        # 直接重新進桌一次, 避免因為局數被踢離桌
        enter_table_result = await enter_table(player_connection, TABLE_ID)
        if not enter_table_result:
            pytest.fail(f"Enter Table failed: {TABLE_ID}")
        # Pre-condition 2. 開啟免傭開關
        set_switch_result = await set_nocomm_switch(
            player_connection, 1
        )
        if set_switch_result is False:
            pytest.fail("Set nocomm switch failed")

        # Step 1. 下注
        # 注單金額與下注玩法
        betinfos = [
            BetInfo(
                play_type=BacPlayType.BANKER_NOCOMMISSION,
                credit=bac_bet_amounts.banker_nocomm,
            ),
        ]

        # Expected: 下注成功且bet_resp_code為0
        bet_result = await place_bet(player_connection, betinfos, GAME_TYPE, TABLE_ID)
        assert (
            bet_result["result"] is True and bet_result["bet_resp_code"] == 0
        ), f"Expected bet to succeed, got result={bet_result['result']}, code={bet_result['bet_resp_code']}"

        # Step 2. 開啟免傭開關
        set_switch_result = await set_nocomm_switch(player_connection, 0)
        # Expected: 開啟免傭開關失敗
        assert set_switch_result is False, "can't set nocomm switch after bet"

        # 測試完成, 且符合預期, 再次關閉免傭開關, 以免影響後續重複的測試
        set_switch_result = await set_nocomm_switch(
            player_connection, 0
        )
        if set_switch_result is False:
            pytest.fail("Set nocomm switch failed")


# BacGameServer移除多寶Flag驗證, 但仍保留相關測試用例, 加上skip marker, 以便處理未來可能的需求變更
# Server端不看多寶Flag(0,1,2,3,4)做為能否下注多寶玩法的判斷, 但UI端仍然會有相關限制
# REL Release Note: https://wiki.star-link-oa.com/pages/viewpage.action?pageId=156679266
@pytest.mark.bac_bet
@pytest.mark.single_table
@pytest.mark.skip(reason="Bac GameServer removed duobao flag validation")
@pytest.mark.asyncio(loop_scope="module")
class TestBacDuobaoFlagBetting:
    """多寶Flag下注測試"""

    # 定義多寶相關的玩法組合
    regular_play_types_with_duobao = [
        item
        for item in play_types
        if item != (BacPlayType.BANKER_NOCOMMISSION)
    ]
    multi_play_types_13_all_with_duobao = list(combinations(regular_play_types_with_duobao, 13))  # 13個玩法的組合(全取)

    @pytest.mark.parametrize(
            "duobao_flag", 
            [0, 1, 2, 4], 
            ids=[f"duobao_flag: {i}" for i in [0, 1, 2, 4]]
    )
    async def test_bac_bet_single_playtype_23_with_duobaoflag_off(
        self, module_player_connection, bac_bet_amounts, duobao_flag
    ):
        """百家樂_未開多寶flag_下注多寶(預期失敗_error=13)"""
        # Pre-Condition: 直接拿已登入的狀態, 不會再重新登入一次
        player_connection, player_init_balance = module_player_connection
        if player_connection is None:
            pytest.fail("Player connection object should not be None")
        # 直接重新進桌一次, 避免因為局數被踢離桌
        enter_table_result = await enter_table(player_connection, TABLE_ID)
        if not enter_table_result:
            pytest.fail(f"Enter Table failed: {TABLE_ID}")
        # 設定多寶flag為0/1/2/4 - 關閉多寶
        duobao_switch_result = await set_duobao_switch(player_connection, duobao_flag)
        if duobao_switch_result is False:
            pytest.fail("Set duobao switch failed")

        # 等待0.5s, 確保開關已經生效, 因core server也是採用非同步的方式處理
        # 有可能client已經收到切換開關的response, 但server端還沒處理完, 故加入等待
        # await asyncio.sleep(0.5)

        # Step 1. 直接下注
        # 注單金額與下注玩法
        betinfos = [
            BetInfo(play_type=BacPlayType.DUO_BAO, credit=bac_bet_amounts.duo_bao),
        ]

        # Expected: 下注失敗且bet_resp_code為13
        bet_result = await place_bet(player_connection, betinfos, GAME_TYPE, TABLE_ID)
        assert (
            bet_result["result"] is False and bet_result["bet_resp_code"] == 13
        ), f"Expected bet to fail with code 13, got result={bet_result['result']}, code={bet_result['bet_resp_code']}"

        # 下注完成, 且符合預期, 再次切換多寶flag為原本的default值, 以免影響後續重複的測試
        duobao_switch_result = await set_duobao_switch(player_connection, 4)
        if duobao_switch_result is False:
            pytest.fail("Set duobao switch failed")
            
    @pytest.mark.parametrize(
            "duobao_flag", 
            [0, 1, 2, 4], 
            ids=[f"duobao_flag: {i}" for i in [0, 1, 2, 4]]
    )
    @pytest.mark.parametrize(
        "duobao_play_types_combo",
        multi_play_types_13_all_with_duobao,
        ids=[f"{'/'.join(pt.name for pt in combo)}" for combo in multi_play_types_13_all_with_duobao],
        # ids=["all regular play types with duobao(0/2/3/4/5/8/9/12/24/25/23)"],
    )
    async def test_bac_bet_all_playtypes_23_with_duobaoflag_off(
        self, module_player_connection, bac_bet_amounts, duobao_flag, duobao_play_types_combo
    ):
        """百家樂_未開多寶_下注含多寶的全玩法(預期失敗_error=13)"""
        # Pre-Condition: 直接拿已登入的狀態, 不會再重新登入一次
        player_connection, player_init_balance = module_player_connection
        if player_connection is None:
            pytest.fail("Player connection object should not be None")
        # 直接重新進桌一次, 避免因為局數被踢離桌
        enter_table_result = await enter_table(player_connection, TABLE_ID)
        if not enter_table_result:
            pytest.fail(f"Enter Table failed: {TABLE_ID}")
        # 設定多寶flag為0/1/2/4 - 關閉多寶
        duobao_switch_result = await set_duobao_switch(player_connection, duobao_flag)
        if duobao_switch_result is False:
            pytest.fail("Set duobao switch failed")

        # 等待0.5s, 確保開關已經生效, 因core server也是採用非同步的方式處理
        # 有可能client已經收到切換開關的response, 但server端還沒處理完, 故加入等待
        # await asyncio.sleep(0.5)

        # Step 1. 直接下注
        # 注單金額與下注玩法
        betinfos = []
        for play_type in duobao_play_types_combo:
            bet_amounts = getattr(bac_bet_amounts, play_type.name.lower())
            betinfos.append(BetInfo(play_type=play_type, credit=bet_amounts))

        # Expected: 下注失敗且bet_resp_code為13
        bet_result = await place_bet(player_connection, betinfos, GAME_TYPE, TABLE_ID)
        assert (
            bet_result["result"] is False and bet_result["bet_resp_code"] == 13
        ), f"Expected bet to fail with code 13, got result={bet_result['result']}, code={bet_result['bet_resp_code']}"

        # 下注完成, 且符合預期, 再次切換多寶flag為原本的default值, 以免影響後續重複的測試
        duobao_switch_result = await set_duobao_switch(player_connection, 4)
        if duobao_switch_result is False:
            pytest.fail("Set duobao switch failed")


@pytest.mark.bac_bet
@pytest.mark.single_table
@pytest.mark.asyncio(loop_scope="module")
class TestBacRaiseBet:
    """百家樂加注測試"""

    @pytest.mark.basic
    @pytest.mark.parametrize(
        "play_types",
        regular_play_types,
        ids=[f"{pt.name}" for pt in regular_play_types],
    )
    async def test_bac_bet_raise_bet_single_playtype(
        self, module_player_connection, bac_bet_amounts, play_types
    ):
        """百家樂單一玩法加注_一般莊與其他玩法"""
        # Pre-Condition: 直接拿已登入的狀態, 不會再重新登入一次
        player_connection, player_init_balance = module_player_connection
        if player_connection is None:
            pytest.fail("Player connection object should not be None")
        # 直接重新進桌一次, 避免因為局數被踢離桌
        enter_table_result = await enter_table(player_connection, TABLE_ID)
        if not enter_table_result:
            pytest.fail(f"Enter Table failed: {TABLE_ID}")

        # Step 1. 直接下注
        # 注單金額與下注玩法
        bet_amounts = getattr(bac_bet_amounts, play_types.name.lower())
        betinfos = [
            BetInfo(play_type=play_types, credit=bet_amounts),
        ]
        bet_result = await place_bet(player_connection, betinfos, GAME_TYPE, TABLE_ID)

        # 取gmcode
        bet_resp_gmcode = bet_result["bet_resp_gmcode"]

        # Step 2. 同一gmcode加注
        raise_bet_result = await raise_bet(
            player_connection,
            betinfos,
            GAME_TYPE,
            TABLE_ID,
            bet_resp_gmcode,
        )

        # Expected: 下注成功且bet_resp_code為0
        assert (
            raise_bet_result == 0
        ), f"Expected bet to succeed, got code={raise_bet_result}"

    @pytest.mark.basic
    async def test_bac_bet_raise_bet_single_playtype_1(
        self, module_player_connection, bac_bet_amounts
    ):
        """百家樂單一玩法加注_免傭莊"""
        # Pre-Condition 1. 直接拿已登入的狀態, 不會再重新登入一次
        player_connection, player_init_balance = module_player_connection
        if player_connection is None:
            pytest.fail("Player connection object should not be None")
        # 直接重新進桌一次, 避免因為局數被踢離桌
        enter_table_result = await enter_table(player_connection, TABLE_ID)
        if not enter_table_result:
            pytest.fail(f"Enter Table failed: {TABLE_ID}")
        # Pre-Condition 2. 開啟免傭開關
        set_switch_result = await set_nocomm_switch(
            player_connection, 1
        )  
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

        # 取gmcode
        bet_resp_gmcode = bet_result["bet_resp_gmcode"]

        # Step 2. 同一gmcode加注
        raise_bet_result = await raise_bet(
            player_connection,
            betinfos,
            GAME_TYPE,
            TABLE_ID,
            bet_resp_gmcode,
        )

        # Expected: 下注成功且bet_resp_code為0
        assert (
            raise_bet_result == 0
        ), f"Expected bet to succeed, got code={raise_bet_result}"

        # 下注完成, 且符合預期, 再次關閉免傭開關, 以免影響後續重複的測試
        set_switch_result = await set_nocomm_switch(player_connection, 0)
        if set_switch_result is False:
            pytest.fail("Set nocomm switch failed")

    @pytest.mark.basic
    async def test_bac_bet_raise_bet_single_playtype_23(
        self, module_player_connection, bac_bet_amounts
    ):
        """百家樂單一玩法加注_多寶"""
        # Pre-Condition 1. 直接拿已登入的狀態, 不會再重新登入一次
        player_connection, player_init_balance = module_player_connection
        if player_connection is None:
            pytest.fail("Player connection object should not be None")
        # 直接重新進桌一次, 避免因為局數被踢離桌
        enter_table_result = await enter_table(player_connection, TABLE_ID)
        if not enter_table_result:
            pytest.fail(f"Enter Table failed: {TABLE_ID}")
        #  Pre-Condition 2. 設定多寶flag為3 - 幸運六
        duobao_switch_result = await set_duobao_switch(player_connection, 3)
        if duobao_switch_result is False:
            pytest.fail("Set duobao switch failed")

        # 等待0.5s, 確保開關已經生效, 因core server也是採用非同步的方式處理
        # 有可能client已經收到切換開關的response, 但server端還沒處理完, 故加入等待
        # await asyncio.sleep(0.5)

        # Step 1. 直接下注
        # 注單金額與下注玩法
        betinfos = [
            BetInfo(play_type=BacPlayType.DUO_BAO, credit=bac_bet_amounts.duo_bao),
        ]
        bet_result = await place_bet(player_connection, betinfos, GAME_TYPE, TABLE_ID)

        # 取gmcode
        bet_resp_gmcode = bet_result["bet_resp_gmcode"]

        # Step 2. 同一gmcode加注
        raise_bet_result = await raise_bet(
            player_connection,
            betinfos,
            GAME_TYPE,
            TABLE_ID,
            bet_resp_gmcode,
        )

        # Expected: 下注成功且bet_resp_code為0
        assert (
            raise_bet_result == 0
        ), f"Expected bet to succeed, got code={raise_bet_result}"

        # 下注完成, 且符合預期, 再次關閉多寶開關, 以免影響後續重複的測試
        duobao_switch_result = await set_duobao_switch(player_connection, 4)
        if duobao_switch_result is False:
            pytest.fail("Set duobao switch failed")

    @pytest.mark.parametrize(
        "play_types_combo",
        regular_all_combos,
        ids=[f"{'/'.join(pt.name for pt in combo)}" for combo in regular_all_combos],
    )
    async def test_bac_bet_raise_bet_multi_playtypes(
        self, module_player_connection, bac_bet_amounts, play_types_combo
    ):
        """百家樂全玩法加注_一般莊與其他玩法"""
        # Pre-Condition: 直接拿已登入的狀態, 不會再重新登入一次
        player_connection, player_init_balance = module_player_connection
        if player_connection is None:
            pytest.fail("Player connection object should not be None")
        # 直接重新進桌一次, 避免因為局數被踢離桌
        enter_table_result = await enter_table(player_connection, TABLE_ID)
        if not enter_table_result:
            pytest.fail(f"Enter Table failed: {TABLE_ID}")

        # Step 1. 直接下注
        # 注單金額與下注玩法
        betinfos = []
        for play_type in play_types_combo:
            bet_amounts = getattr(bac_bet_amounts, play_type.name.lower())
            betinfos.append(BetInfo(play_type=play_type, credit=bet_amounts))

        bet_result = await place_bet(player_connection, betinfos, GAME_TYPE, TABLE_ID)

        # 取gmcode
        bet_resp_gmcode = bet_result["bet_resp_gmcode"]

        # Step 2. 同一gmcode加注
        raise_bet_result = await raise_bet(
            player_connection,
            betinfos,
            GAME_TYPE,
            TABLE_ID,
            bet_resp_gmcode,
        )

        # Expected: 下注成功且bet_resp_code為0
        assert (
            raise_bet_result == 0
        ), f"Expected bet to succeed, got code={raise_bet_result}"

    @pytest.mark.parametrize(
        "play_types_combo_nocomm",
        nocomm_all_combos,
        ids=[f"{'/'.join(pt.name for pt in combo)}" for combo in nocomm_all_combos],
    )
    async def test_bac_bet_raise_bet_multi_playtypes_nocomm(
        self, module_player_connection, bac_bet_amounts, play_types_combo_nocomm
    ):
        """百家樂全玩法加注_免傭莊"""
        # Pre-Condition 1. 直接拿已登入的狀態, 不會再重新登入一次
        player_connection, player_init_balance = module_player_connection
        if player_connection is None:
            pytest.fail("Player connection object should not be None")
        # 直接重新進桌一次, 避免因為局數被踢離桌
        enter_table_result = await enter_table(player_connection, TABLE_ID)
        if not enter_table_result:
            pytest.fail(f"Enter Table failed: {TABLE_ID}")
        # Pre-Condition 2. 開啟免傭開關
        set_switch_result = await set_nocomm_switch(
            player_connection, 1
        )  
        if set_switch_result is False:
            pytest.fail("Set nocomm switch failed")

        # 等待0.5s, 確保開關已經生效, 因core server也是採用非同步的方式處理
        # 有可能client已經收到切換開關的response, 但server端還沒處理完, 故加入等待
        # await asyncio.sleep(0.5)

        # Step 1. 直接下注
        # 注單金額與下注玩法
        betinfos = []
        for play_type in play_types_combo_nocomm:
            play_type_name = play_type.name.lower()
            # 因config中, 參數命名為banker_nocomm, 故需對取下注金額的部分特別轉換
            if play_type_name == "banker_nocommission":
                play_type_name = "banker_nocomm"
            bet_amounts = getattr(bac_bet_amounts, play_type_name)
            betinfos.append(BetInfo(play_type=play_type, credit=bet_amounts))
        bet_result = await place_bet(player_connection, betinfos, GAME_TYPE, TABLE_ID)

        # 取gmcode
        bet_resp_gmcode = bet_result["bet_resp_gmcode"]

        # Step 2. 同一gmcode加注
        raise_bet_result = await raise_bet(
            player_connection,
            betinfos,
            GAME_TYPE,
            TABLE_ID,
            bet_resp_gmcode,
        )

        # Expected: 下注成功且bet_resp_code為0
        assert (
            raise_bet_result == 0
        ), f"Expected bet to succeed, got code={raise_bet_result}"
        # 下注完成, 且符合預期, 再次關閉免傭開關, 以免影響後續重複的測試
        set_switch_result = await set_nocomm_switch(player_connection, 0)
        if set_switch_result is False:
            pytest.fail("Set nocomm switch failed")


# 此類別中所有測項都直接使用config中所設定的玩家投注金額直接x1000使其超過個人限紅
@pytest.mark.bac_bet
@pytest.mark.single_table
@pytest.mark.asyncio(loop_scope="module")
class TestBacBetOverPersonalLimit:
    """百家樂下注超出個人限紅"""

    @pytest.mark.parametrize(
        "play_types",
        regular_play_types,
        ids=[f"{pt.name}" for pt in regular_play_types],
    )
    async def test_bac_bet_single_playtypes_over_personal_limit(
        self, module_player_connection, bac_bet_amounts, play_types
    ):
        """百家樂下注超出個人限紅_一般莊與其他玩法(預期失敗_error=10)"""
        # Pre-Condition: 直接拿已登入的狀態, 不會再重新登入一次
        player_connection, player_init_balance = module_player_connection
        if player_connection is None:
            pytest.fail("Player connection object should not be None")
        # 直接重新進桌一次, 避免因為局數被踢離桌
        enter_table_result = await enter_table(player_connection, TABLE_ID)
        if not enter_table_result:
            pytest.fail(f"Enter Table failed: {TABLE_ID}")

        # Step 1. 下注
        # 注單金額與下注玩法
        bet_overlimit_amounts = getattr(bac_bet_amounts, play_types.name.lower()) * 1000
        betinfos = [
            BetInfo(play_type=play_types, credit=bet_overlimit_amounts),
        ]

        # Expected: 下注失敗且bet_resp_code為10
        bet_result = await place_bet(player_connection, betinfos, GAME_TYPE, TABLE_ID)
        assert (
            bet_result["result"] is False and bet_result["bet_resp_code"] == 10
        ), f"Expected bet to fail with code 10, got result={bet_result['result']}, code={bet_result['bet_resp_code']}" 

    async def test_bac_bet_single_playtype_1_over_personal_limit(
        self, module_player_connection, bac_bet_amounts
    ):
        """百家樂下注超出個人限紅_免傭莊(預期失敗_error=10)"""
       # Pre-condition 1. 直接拿已登入的狀態, 不再重新登入一次
        player_connection, player_init_balance = module_player_connection
        if player_connection is None:
            pytest.fail("Player connection object should not be None")
        # 直接重新進桌一次, 避免因為局數被踢離桌
        enter_table_result = await enter_table(player_connection, TABLE_ID)
        if not enter_table_result:
            pytest.fail(f"Enter Table failed: {TABLE_ID}")
        # Pre-condition 2. 開啟免傭開關
        set_switch_result = await set_nocomm_switch(
            player_connection, 1
        )
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
                credit=bac_bet_amounts.banker_nocomm * 1000,
            ),
        ]

        # Expected: 下注失敗且bet_resp_code為10
        bet_result = await place_bet(player_connection, betinfos, GAME_TYPE, TABLE_ID)
        assert (
            bet_result["result"] is False and bet_result["bet_resp_code"] == 10
        ), f"Expected bet to fail with code 10, got result={bet_result['result']}, code={bet_result['bet_resp_code']}"

        # 下注完成, 且符合預期, 再次關閉免傭開關, 以免影響後續重複的測試
        set_switch_result = await set_nocomm_switch(player_connection, 0)
        if set_switch_result is False:
            pytest.fail("Set nocomm switch failed")

    async def test_bac_bet_single_playtype_23_over_personal_limit(
        self, module_player_connection, bac_bet_amounts
    ):
        """百家樂下注超出個人限紅_多寶(預期失敗_error=10)"""
        # Pre-Condition: 直接拿已登入的狀態, 不會再重新登入一次
        player_connection, player_init_balance = module_player_connection
        if player_connection is None:
            pytest.fail("Player connection object should not be None")
        # 直接重新進桌一次, 避免因為局數被踢離桌
        enter_table_result = await enter_table(player_connection, TABLE_ID)
        if not enter_table_result:
            pytest.fail(f"Enter Table failed: {TABLE_ID}")
        # 設定多寶flag為3 - 開啟多寶
        duobao_switch_result = await set_duobao_switch(player_connection, 3)
        if duobao_switch_result is False:
            pytest.fail("Set duobao switch failed")

        # 等待0.5s, 確保開關已經生效, 因core server也是採用非同步的方式處理
        # 有可能client已經收到切換開關的response, 但server端還沒處理完, 故加入等待
        # await asyncio.sleep(0.5)

        # Step 1. 直接下注
        # 注單金額與下注玩法
        betinfos = [
            BetInfo(play_type=BacPlayType.DUO_BAO, credit=bac_bet_amounts.duo_bao * 1000),
        ]

        # Expected: 下注失敗且bet_resp_code為10
        bet_result = await place_bet(player_connection, betinfos, GAME_TYPE, TABLE_ID)
        assert (
            bet_result["result"] is False and bet_result["bet_resp_code"] == 10
        ), f"Expected bet to fail with code 10, got result={bet_result['result']}, code={bet_result['bet_resp_code']}"

        # 下注完成, 且符合預期, 再次切換多寶flag為原本的default值, 以免影響後續重複的測試
        duobao_switch_result = await set_duobao_switch(player_connection, 4)
        if duobao_switch_result is False:
            pytest.fail("Set duobao switch failed")

    @pytest.mark.parametrize(
        "play_types_combo",
        regular_all_combos,
        ids=[f"{'/'.join(pt.name for pt in combo)}" for combo in regular_all_combos],
    )
    async def test_bac_bet_playtypes_combo_over_personal_limit(
        self, module_player_connection, bac_bet_amounts, play_types_combo
    ):
        """百家樂下注超出個人限紅_一般莊與其他玩法組合_至少一個玩法超出限紅(預期失敗_error=10)"""
        # Pre-Condition: 直接拿已登入的狀態, 不會再重新登入一次
        player_connection, player_init_balance = module_player_connection
        if player_connection is None:
            pytest.fail("Player connection object should not be None")
        # 直接重新進桌一次, 避免因為局數被踢離桌
        enter_table_result = await enter_table(player_connection, TABLE_ID)
        if not enter_table_result:
            pytest.fail(f"Enter Table failed: {TABLE_ID}")

        # Step 1. 建立下注資訊
        betinfos = []
        # 決定哪些玩法將使用超過限紅的下注金額
        # 隨機選擇"至少一個玩法"一定會超過限紅
        # play_types_list = list(play_types_combo)
        # guaranteed_overlimit = random.choice(play_types_list)
        guaranteed_overlimit = random.choice(play_types_combo)
        
        # for play_type in play_types_list:
        for play_type in play_types_combo:
            play_type_name = play_type.name.lower()
            base_amount = getattr(bac_bet_amounts, play_type_name)
            
            # 判斷是否使用超過限紅的下注金額, 如果是前面random選擇的玩法, 就一定會超過限紅, 或是透過random選擇為True的也會使用超過限紅的投注金額(50%機率)
            if play_type == guaranteed_overlimit or random.choice([True, False]):
                bet_amount = base_amount * 1000  # 超限
            else:
                bet_amount = base_amount  # 正常額度
                
            betinfos.append(BetInfo(play_type=play_type, credit=bet_amount))
        
        # Expected: 下注失敗且bet_resp_code為10（因為至少有一個玩法超限）
        bet_result = await place_bet(player_connection, betinfos, GAME_TYPE, TABLE_ID)
        assert (
            bet_result["result"] is False and bet_result["bet_resp_code"] == 10
        ), f"Expected bet to fail with code 10, got result={bet_result['result']}, code={bet_result['bet_resp_code']}"

    @pytest.mark.parametrize(
        "play_types_combo_nocomm",
        nocomm_all_combos,
        ids=[f"{'/'.join(pt.name for pt in combo)}" for combo in nocomm_all_combos],
    )
    async def test_bac_bet_playtypes_combo_nocomm_over_personal_limit(
        self, module_player_connection, bac_bet_amounts, play_types_combo_nocomm
    ):
        """百家樂下注超出個人限紅_免傭莊_至少一個玩法超出限紅(預期失敗_error=10)"""
        # Pre-Condition 1. 直接拿已登入的狀態, 不會再重新登入一次
        player_connection, player_init_balance = module_player_connection
        if player_connection is None:
            pytest.fail("Player connection object should not be None")
        # 直接重新進桌一次, 避免因為局數被踢離桌
        enter_table_result = await enter_table(player_connection, TABLE_ID)
        if not enter_table_result:
            pytest.fail(f"Enter Table failed: {TABLE_ID}")
        # Pre-Condition 2. 開啟免傭開關
        set_switch_result = await set_nocomm_switch(
            player_connection, 1
        )
        if set_switch_result is False:
            pytest.fail("Set nocomm switch failed")

        # 等待0.5s, 確保開關已經生效, 因core server也是採用非同步的方式處理
        # 有可能client已經收到切換開關的response, 但server端還沒處理完, 故加入等待
        # await asyncio.sleep(0.5)

        # Step 1. 建立下注資訊
        betinfos = []
        # 決定哪些玩法將使用超過限紅的下注金額
        # 隨機選擇"至少一個玩法"一定會超過限紅
        # play_types_list = list(play_types_combo_nocomm)
        # guaranteed_overlimit = random.choice(play_types_list)
        guaranteed_overlimit = random.choice(play_types_combo_nocomm)
        
        # for play_type in play_types_list:
        for play_type in play_types_combo_nocomm:
            play_type_name = play_type.name.lower()
            if play_type_name == "banker_nocommission":
                play_type_name = "banker_nocomm"
            base_amount = getattr(bac_bet_amounts, play_type_name)
            
            # 判斷是否使用超過限紅的下注金額, 如果是前面random選擇的玩法, 就一定會超過限紅, 或是透過random選擇為True的也會使用超過限紅的投注金額(50%機率)
            if play_type == guaranteed_overlimit or random.choice([True, False]):
                bet_amount = base_amount * 1000
            else:
                bet_amount = base_amount
            betinfos.append(BetInfo(play_type=play_type, credit=bet_amount))
        # Expected: 下注失敗且bet_resp_code為10（因為至少有一個玩法超限）
        bet_result = await place_bet(player_connection, betinfos, GAME_TYPE, TABLE_ID)
        assert (
            bet_result["result"] is False and bet_result["bet_resp_code"] == 10
        ), f"Expected bet to fail with code 10, got result={bet_result['result']}, code={bet_result['bet_resp_code']}"
    
        # 下注完成, 且符合預期, 再次關閉免傭開關, 以免影響後續重複的測試
        set_switch_result = await set_nocomm_switch(player_connection, 0)
        if set_switch_result is False:
            pytest.fail("Set nocomm switch failed")