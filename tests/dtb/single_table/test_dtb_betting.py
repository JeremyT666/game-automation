import pytest
import random
from itertools import combinations

from src.game.playtype_enums import DtbPlayType
from src.game.bet import BetInfo, place_bet, raise_bet
from src.user.enter_table import enter_table

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



@pytest.mark.dtb_bet
@pytest.mark.single_table
@pytest.mark.asyncio(loop_scope="module")
class TestDtbSingleTypeBetting:
    """龍虎單一玩法下注測試"""

    @pytest.mark.parametrize(
        "play_types",
        dtb_play_types,
        ids=[f"{pt.name}" for pt in dtb_play_types],  # 透過comprhension取出每個play_type的名稱, 放至ids中供html report使用
    )
    async def test_dtb_bet_single_playtype(
        self, module_player_connection, dtb_bet_amounts, play_types
    ):
        """龍虎單一玩法下注"""
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
        bet_amounts = getattr(dtb_bet_amounts, play_types.name.lower())
        betinfos = [
            BetInfo(play_type=play_types, credit=bet_amounts),
        ]

        # Expected: 下注成功且bet_resp_code為0
        bet_result = await place_bet(player_connection, betinfos, GAME_TYPE, TABLE_ID)
        assert (
            bet_result["result"] is True and bet_result["bet_resp_code"] == 0
        ), f"Expected bet to succeed, got result={bet_result['result']}, code={bet_result['bet_resp_code']}"


@pytest.mark.dtb_bet
@pytest.mark.single_table
@pytest.mark.asyncio(loop_scope="module")
class TestDtbMultiTypeBetting:
    """龍虎多玩法組合下注測試"""

    @pytest.mark.parametrize(
        "play_types_combo",
        regular_all_combos,
        ids=[f"{'/'.join(pt.name for pt in combo)}" for combo in regular_all_combos],   # 透過comprhension取出每個play_type的名稱, 放至ids中供html report使用
    )
    async def test_dtb_bet_multi_playtypes(
        self, module_player_connection, dtb_bet_amounts, play_types_combo
    ):
        """龍虎多玩法組合下注_一般莊與其他玩法組合"""
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
            bet_amounts = getattr(dtb_bet_amounts, play_type.name.lower())
            betinfos.append(BetInfo(play_type=play_type, credit=bet_amounts))

        # Expected: 下注成功且bet_resp_code為0
        bet_result = await place_bet(player_connection, betinfos, GAME_TYPE, TABLE_ID)
        assert (
            bet_result["result"] is True and bet_result["bet_resp_code"] == 0
        ), f"Expected bet to succeed, got result={bet_result['result']}, code={bet_result['bet_resp_code']}"


@pytest.mark.dtb_bet
@pytest.mark.single_table
@pytest.mark.asyncio(loop_scope="module")
class TestDtbRaiseBet:
    """龍虎加注測試"""

    @pytest.mark.parametrize(
        "play_types",
        dtb_play_types,
        ids=[f"{pt.name}" for pt in dtb_play_types],
    )
    async def test_dtb_bet_raise_bet_single_playtype(
        self, module_player_connection, dtb_bet_amounts, play_types
    ):
        """龍虎單一玩法加注"""
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
        bet_amounts = getattr(dtb_bet_amounts, play_types.name.lower())
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

    @pytest.mark.parametrize(
        "play_types_combo",
        regular_all_combos,
        ids=[f"{'/'.join(pt.name for pt in combo)}" for combo in regular_all_combos],
    )
    async def test_dtb_bet_raise_bet_multi_playtypes(
        self, module_player_connection, dtb_bet_amounts, play_types_combo
    ):
        """龍虎全玩法加注"""
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
            bet_amounts = getattr(dtb_bet_amounts, play_type.name.lower())
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


# 此類別中所有測項都直接使用config中所設定的玩家投注金額直接x1000使其超過個人限紅
@pytest.mark.dtb_bet
@pytest.mark.single_table
@pytest.mark.asyncio(loop_scope="module")
class TestDtbBetOverPersonalLimit:
    """龍虎下注超出個人限紅"""

    @pytest.mark.parametrize(
        "play_types",
        dtb_play_types,
        ids=[f"{pt.name}" for pt in dtb_play_types],
    )
    async def test_dtb_bet_single_playtypes_over_personal_limit(
        self, module_player_connection, dtb_bet_amounts, play_types
    ):
        """龍虎下注超出個人限紅_一般莊與其他玩法(預期失敗_error=10)"""
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
        bet_overlimit_amounts = getattr(dtb_bet_amounts, play_types.name.lower()) * 1000
        betinfos = [
            BetInfo(play_type=play_types, credit=bet_overlimit_amounts),
        ]

        # Expected: 下注失敗且bet_resp_code為10
        bet_result = await place_bet(player_connection, betinfos, GAME_TYPE, TABLE_ID)
        assert (
            bet_result["result"] is False and bet_result["bet_resp_code"] == 10
        ), f"Expected bet to fail with code 10, got result={bet_result['result']}, code={bet_result['bet_resp_code']}" 

    @pytest.mark.parametrize(
        "play_types_combo",
        regular_all_combos,
        ids=[f"{'/'.join(pt.name for pt in combo)}" for combo in regular_all_combos],
    )
    async def test_dtb_bet_playtypes_combo_over_personal_limit(
        self, module_player_connection, dtb_bet_amounts, play_types_combo
    ):
        """龍虎下注超出個人限紅_至少一個玩法超出限紅(預期失敗_error=10)"""
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
            base_amount = getattr(dtb_bet_amounts, play_type_name)
            
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