from enum import IntEnum

class BacPlayType(IntEnum):
    """百家樂玩法枚舉
    
    定義了所有百家樂遊戲中可用的下注玩法及其對應代碼。
    
    - BANKER: 一般莊
    - BANKER_NOCOMMISSION: 免傭莊 (需要開啟免傭開關)
    - PLAYER: 閒
    - TIE: 和局
    - BANKER_PAIR: 莊對
    - PLAYER_PAIR: 閒對
    - BANKER_DRAGON_BONUS: 莊龍寶
    - PLAYER_DRAGON_BONUS: 閒龍寶
    - LUCKY6: 幸運6
    - DUO_BAO: 多寶
    - LUCKY6_2: 兩張6
    - LUCKY6_3: 三張6
    - 
    """
    BANKER = 0                # 一般莊
    BANKER_NOCOMMISSION = 1   # 免傭莊 (需要開啟免傭開關)
    PLAYER = 2                # 閒
    TIE = 3                   # 和局
    BANKER_PAIR = 4           # 莊對
    PLAYER_PAIR = 5           # 閒對
    ANY_PAIR = 6              # 任意對子, 目前WT不支援(遊戲端ui不支援, 但實際協議跟後台都可以正常)
    PERFECT_PAIR = 7          # 完美對子, 目前WT不支援(遊戲端ui不支援, 但實際協議跟後台都可以正常)
    BANKER_DRAGON_BONUS = 8   # 莊龍寶
    PLAYER_DRAGON_BONUS = 9   # 閒龍寶
    BIG = 10                  # 大, 目前WT不支援
    SMALL = 11                # 小, 目前WT不支援
    LUCKY6 = 12               # 幸運6
    # 超和玩法 (13-22) 目前WT不支援
    SUPER_TIE_0 = 13
    SUPER_TIE_1 = 14
    SUPER_TIE_2 = 15
    SUPER_TIE_3 = 16
    SUPER_TIE_4 = 17
    SUPER_TIE_5 = 18
    SUPER_TIE_6 = 19
    SUPER_TIE_7 = 20
    SUPER_TIE_8 = 21
    SUPER_TIE_9 = 22
    DUO_BAO = 23              # 多寶
    LUCKY6_2 = 24             # 兩張6
    LUCKY6_3 = 25             # 三張6
    LUCKY7 = 26               # 幸運7
    SUPER_LUCKY7 = 27         # 超級幸運7

    @classmethod
    def get_name(cls, value):
        """根據數值獲取玩法名稱"""
        try:
            return cls(value).name
        except ValueError:
            return f"UNKNOWN_PLAY_TYPE_{value}"
        
class DtbPlayType(IntEnum):
    """DTB玩法枚舉
    
    定義了所有DTB遊戲中可用的下注玩法及其對應代碼。
    """
    TIGER = 1             # 虎
    DRAGON = 2            # 龍
    TIE = 3               # 和局
    TIGER_ODD = 4         # 虎單
    TIGER_EVEN = 5        # 虎雙
    DRAGON_ODD = 6        # 龍單
    DRAGON_EVEN = 7       # 龍雙
    TIGER_RED = 8         # 虎紅
    TIGER_BLACK = 9       # 虎黑
    DRAGON_RED = 10       # 龍紅
    DRAGON_BLACK = 11     # 龍黑

    @classmethod
    def get_name(cls, value):
        """根據數值獲取玩法名稱"""
        try:
            return cls(value).name
        except ValueError:
            return f"UNKNOWN_PLAY_TYPE_{value}"
        
class PlayTypeFactory:
    """玩法類型工廠函數，用於根據遊戲類型獲取對應的玩法枚舉類"""
    
    _registry = {}  # 初始化為空字典

    @classmethod
    def register(cls, game_type_code, play_type_class):
        """註冊新的遊戲類型和對應的玩法枚舉類"""
        cls._registry[game_type_code.lower()] = play_type_class
    
    @classmethod
    def get(cls, game_type):
        """獲取遊戲類型對應的玩法枚舉類"""
        game_type = str(game_type).lower()
        if game_type in cls._registry:
            return cls._registry[game_type]
        raise ValueError(f"Unsupported game type: {game_type}")

PlayTypeFactory.register("bac", BacPlayType)
PlayTypeFactory.register("dtb", DtbPlayType)