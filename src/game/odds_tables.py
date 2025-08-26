from game.playtype_enums import BacPlayType, DtbPlayType

# 百家樂賠率表
BAC_PAYOUT_TABLE = {
    BacPlayType.BANKER: {"base_odds": 0.95, "type": "fixed"},  # 1:0.95 (扣5%傭金)
    BacPlayType.BANKER_NOCOMMISSION: {"base_odds": 1.0, "type": "variable"},  # 1:1 (免傭莊) 莊非六點勝出1:1, 莊6點勝出1:0.5
    BacPlayType.PLAYER: {"base_odds": 1.0, "type": "fixed"},   # 1:1
    BacPlayType.TIE: {"base_odds": 8.0, "type": "fixed"},      # 1:8
    BacPlayType.BANKER_PAIR: {"base_odds": 11.0, "type": "fixed"},  # 1:11
    BacPlayType.PLAYER_PAIR: {"base_odds": 11.0, "type": "fixed"},  # 1:11
    BacPlayType.BANKER_DRAGON_BONUS: {"base_odds": 30.0, "type": "variable", "depends_on": "banker_natural_win_margin"},
    BacPlayType.PLAYER_DRAGON_BONUS: {"base_odds": 30.0, "type": "variable", "depends_on": "player_natural_win_margin"},
    BacPlayType.LUCKY6: {"base_odds": 12.0, "type": "variable", "depends_on": "banker_cards_count"},
    BacPlayType.DUO_BAO: {"base_odds": 88.0, "type": "variable"},
    BacPlayType.LUCKY6_2: {"base_odds": 22.0, "type": "fixed"},   # 兩張6
    BacPlayType.LUCKY6_3: {"base_odds": 50.0, "type": "fixed"},   # 三張6
    BacPlayType.LUCKY7: {"base_odds": 40.0, "type": "variable"},
    BacPlayType.SUPER_LUCKY7: {"base_odds": 120.0, "type": "variable"},
}

BANKER_NOCOMMISSION_ODDS = {
    "default": 1.0,
    "banker_6": 0.5,  # 免傭莊6點勝出1:0.5
}

# 龍寶賠率表 (根據贏牌差距)
DRAGON_BONUS_ODDS = {
    1: 1.0,   # 例牌勝 1:1
    4: 1.0,   # 非例牌贏4點 1:1
    5: 2.0,   # 非例牌贏5點 1:2
    6: 3.0,   # 非例牌贏6點 1:4
    7: 5.0,   # 非例牌贏7點 1:5
    8: 10.0,  # 非例牌贏8點 1:10
    9: 30.0,  # 非例牌贏9點 1:30
}

# 幸運六賠率表 (根據莊家牌數)
LUCKY6_ODDS = {
    2: 12.0,  # 兩張牌6點：1賠12
    3: 20.0,  # 三張牌6點：1賠20
}

# 多寶賠率表 (根據多寶牌型), 由局結果協議解析出的參數值(duobao_type)對應相對賠率
DUOBAO_ODDS = {
    0: 0.0,   # 無多寶牌型 None
    1: 100.0,   # 同花順 StraightFlush: 1:100
    2: 70.0,   # 四條 FourOfAKind: 1:70
    3: 35.0,   # 葫蘆 FullHouse: 1:35
    4: 30.0,   # 同花 Flush: 1:30
    5: 25.0,   # 順子 Straight: 1:25
    6: 10.0,   # 三條 ThreeOfAKind: 1:10
    7: 3.0,    # 兩對 TwoPair: 1:3
}

# 幸運七賠率表
LUCKY7_ODDS = {
    2: 6.0,  # 閒家2張: 1:6
    3: 15.0, # 閒家3張: 1:15
}

# 超級幸運七賠率表
SUPER_LUCKY7_ODDS = {
    4: 30.0,  # 莊閒4張: 1:30
    5: 40.0,  # 莊閒5張: 1:40
    6: 100.0, # 莊閒6張: 1:100
}

# 龍虎賠率表
DTB_PAYOUT_TABLE = {
    DtbPlayType.TIGER: {"base_odds": 1.0, "type": "fixed"},      # 1:1
    DtbPlayType.DRAGON: {"base_odds": 1.0, "type": "fixed"},     # 1:1
    DtbPlayType.TIE: {"base_odds": 8.0, "type": "fixed"},        # 1:8
    DtbPlayType.TIGER_ODD: {"base_odds": 0.75, "type": "fixed"},  # 1:0.75
    DtbPlayType.TIGER_EVEN: {"base_odds": 1.05, "type": "fixed"}, # 1:1.05
    DtbPlayType.DRAGON_ODD: {"base_odds": 0.75, "type": "fixed"}, # 1:0.75
    DtbPlayType.DRAGON_EVEN: {"base_odds": 1.05, "type": "fixed"}, # 1:1.05
    DtbPlayType.TIGER_RED: {"base_odds": 0.9, "type": "fixed"},  # 1:0.9
    DtbPlayType.TIGER_BLACK: {"base_odds": 0.9, "type": "fixed"}, # 1:0.9
    DtbPlayType.DRAGON_RED: {"base_odds": 0.9, "type": "fixed"}, # 1:0.9
    DtbPlayType.DRAGON_BLACK: {"base_odds": 0.9, "type": "fixed"}, # 1:0.9
}

# 工廠函數，用於快速獲取玩法類型枚舉
def get_play_type_enum(game_type):
    """根據遊戲類型獲取對應的玩法枚舉類"""
    from game.playtype_enums import PlayTypeFactory
    return PlayTypeFactory.get(game_type)

# 便利函數
def get_play_type_name(game_type, play_type_value):
    """獲取玩法類型名稱"""
    try:
        play_type_enum = get_play_type_enum(game_type)
        return play_type_enum.get_name(play_type_value)
    except (ValueError, AttributeError):
        return f"UNKNOWN_PLAY_TYPE_{play_type_value}"
