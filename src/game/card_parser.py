from utils.logger import logger

class Card:
    """撲克牌類"""
    
    def __init__(self, rank, suit):
        self.rank = rank  # 牌值 (1-13, A=1, J=11, Q=12, K=13)
        self.suit = suit  # 花色 (0=方塊, 1=梅花, 2=黑桃, 3=紅心)
    
    def __str__(self):
        """定義物件可讀字符串表示(for print(obj) or str(obj))"""
        rank_names = {1: "A", 11: "J", 12: "Q", 13: "K", 0: "0"}
        suit_names = {0: "♦", 1: "♣", 2: "♠", 3: "♥"}
        
        rank_display = rank_names.get(self.rank, str(self.rank))    # 將牌值1, 11~13轉換為字符串 (A, J, Q, K)
        suit_display = suit_names.get(self.suit, f"?{self.suit}")   # 將花色0~3轉換為符號 (♦, ♣, ♠, ♥)，其他則顯示為 "?{suit}"
        
        return f"{suit_display}{rank_display}"
    
    def __repr__(self):
        """定義物件的正式字符串表示"""
        rank_names = {1: "A", 11: "J", 12: "Q", 13: "K", 0: "0"}
        suit_names = {0: "Diamonds", 1: "Clubs", 2: "Spades", 3: "Hearts"}

        rank_display = rank_names.get(self.rank, str(self.rank))    # 將牌值1, 11~13轉換為字符串 (A, J, Q, K)
        suit_display = suit_names.get(self.suit, f"Unknown({self.suit})")  # 將花色0~3轉換為名稱 (Diamonds, Clubs, Spades, Hearts)，其他則顯示為 "Unknown({suit})"

        return f"{suit_display}{rank_display}"

    @property
    def bac_value(self):
        """百家樂點數 (A=1, 2-9=面值, 10/J/Q/K=0)"""
        if self.rank == 1:  # A
            return 1
        elif 2 <= self.rank <= 9:
            return self.rank
        else:  # 10, J, Q, K
            return 0
    
    @property
    def dtb_value(self):
        """龍虎點數 (A=1, 2-10=面值, J=11, Q=12, K=13)"""
        return self.rank
    
    @property
    def is_red(self):
        """是否為紅色牌 (方塊、紅心)"""
        return self.suit in [0, 3]
    
    @property
    def is_black(self):
        """是否為黑色牌 (梅花、黑桃)"""
        return self.suit in [1, 2]

class BacCardParser:
    """百家樂牌型解析器"""
    
    @staticmethod
    def parse_cards_from_json(cards_data):
        """從JSON數據解析牌型"""
        cards = []
        for card_data in cards_data:
            card = Card(card_data["rank"], card_data["suit"])
            cards.append(card)
        return cards
    
    @staticmethod
    def calculate_hand_value(cards):
        """計算百家樂手牌點數"""
        total = sum(card.bac_value for card in cards)
        return total % 10

    @staticmethod
    def dragon_bounus_check(dragon_bonus_info):
        """龍寶檢查"""
        try:
            dragon_bonus_type = dragon_bonus_info.get("type", 999)
            dragon_bonus_odds = dragon_bonus_info.get("odds", 999)
            
            if dragon_bonus_type == 0:
                return {
                    "banker_dragon_bonus": False,  # 莊家龍寶
                    "player_dragon_bonus": False,  # 閒家龍寶
                    "dragon_bonus_odds": dragon_bonus_odds,  # 無龍寶
                }
            
            elif dragon_bonus_type > 0 and dragon_bonus_odds > 0:
                return {
                    "banker_dragon_bonus": True,  # 莊家龍寶
                    "player_dragon_bonus": False,  # 閒家龍寶
                    "dragon_bonus_odds": dragon_bonus_odds,
                }
            
            elif dragon_bonus_type < 0 and dragon_bonus_odds > 0:
                return {
                    "banker_dragon_bonus": False,  # 莊家龍寶
                    "player_dragon_bonus": True,  # 閒家龍寶
                    "dragon_bonus_odds": dragon_bonus_odds,
                }
            
            # 沒龍寶的狀況下, 仍會給值, 如果非以上判斷的type&odds, 則視為無龍寶
            else:
                # logger.warning(f"Unknown dragon bonus type: {dragon_bonus_type}, odds: {dragon_bonus_odds}")
                return {
                    "banker_dragon_bonus": None,
                    "player_dragon_bonus": None,
                    "dragon_bonus_odds": 0,
                }
            
        except Exception as e:
            logger.error(f"Failed on checking dragon bonus: {e}")
            return {
                "banker_dragon_bonus": None,
                "player_dragon_bonus": None,
                "dragon_bonus_odds": 0,
            }
        
    @staticmethod
    def duobao_check(duobao_type):
        """多寶檢查"""
        try:
            if duobao_type == 0:
                return False  # 無多寶
            elif duobao_type in [1, 2, 3, 4, 5, 6, 7]:
                return True  # 有多寶
            else:
                logger.warning(f"Unknown duobao info: {duobao_type}")
                return False  # 默認無多寶
        except Exception as e:
            logger.error(f"Failed on checking duobao: {e}")
            return False
                
    @staticmethod
    def analyze_bac_result(cards_data, dragon_bonus_info=None, duobao_type=None):
        """
        分析百家樂牌值結果
        
        Args:
            cards_data (list): 牌數據列表，每張牌包含 "rank" 和 "suit"
            dragon_bonus_info (dict, optional): 龍寶相關信息
            duobao_type (int, optional): 多寶牌型 (1-7, 0為無多寶)
        
        Returns:
            dict: 包含莊家和閒家的牌、點數、對子、勝負結果等信息
                - player_cards, banker_cards: 閒家/莊家牌型
                - player_value, banker_value: 閒家/莊家點數 (0-9)
                - player_pair, banker_pair: 是否對子
                - banker_wins, player_wins, tie: 勝負結果
                - win_margin: 勝負差距
                - banker_dragon_bonus, player_dragon_bonus: 龍寶中獎狀態
                - dragon_bonus_odds: 龍寶賠率
                - duobao, duobao_type: 是否多寶, 多寶牌型
        """
        cards = BacCardParser.parse_cards_from_json(cards_data)

        # 分配牌給莊閒 (前兩張給閒家，接下來兩張給莊家，剩餘按規則分配)
        player_cards = [cards[0], cards[2]]  # 第1、3張
        banker_cards = [cards[1], cards[3]]  # 第2、4張
        
        # 補牌邏輯 (傳入的list, 第5個位置是閒家補牌，第6個位置是莊家補牌)
        if len(cards) > 4 and cards[4].rank != 0:   # server有可能會給0, 所以多對rank判斷
            player_cards.append(cards[4])  # 閒家補牌
        if len(cards) > 5 and cards[5].rank != 0:   # server有可能會給0, 所以多對rank判斷
            banker_cards.append(cards[5])  # 莊家補牌
        
        player_value = BacCardParser.calculate_hand_value(player_cards)
        banker_value = BacCardParser.calculate_hand_value(banker_cards)
        
        # 判斷對子
        player_pair = len(player_cards) >= 2 and player_cards[0].rank == player_cards[1].rank
        banker_pair = len(banker_cards) >= 2 and banker_cards[0].rank == banker_cards[1].rank

        # 龍寶判斷
        dragon_bonus_result = {}
        if dragon_bonus_info:
            dragon_bonus_result = BacCardParser.dragon_bounus_check(dragon_bonus_info)
        else:
            dragon_bonus_result = {
                "banker_dragon_bonus": None,
                "player_dragon_bonus": None,
                "dragon_bonus_odds": None,
            }
        
        return {
            "player_cards": player_cards,
            "banker_cards": banker_cards,
            "player_value": player_value,
            "banker_value": banker_value,
            "player_pair": player_pair,
            "banker_pair": banker_pair,
            "banker": banker_value > player_value,
            "player": player_value > banker_value,
            "tie": player_value == banker_value,
            "win_margin": abs(banker_value - player_value),
            **dragon_bonus_result,  # dictionary unpacking, 直接把龍寶的key-value合併進來
            "duobao": BacCardParser.duobao_check(duobao_type) if duobao_type is not None else False,
            "duobao_type": duobao_type,
        }

class DTBCardParser:
    """龍虎牌型解析器"""

    @staticmethod
    def dtb_cards_mapping(card_value):
        """龍虎牌點數與花色mapping"""

        rank = card_value % 13 + 1 # 點數 (1-13, A=1, 2-10=面值, J=11, Q=12, K=13)
        suit = card_value // 13 # 花色 (0=方塊, 1=梅花, 2=黑桃, 3=紅心)
        
        return {
            "rank": rank,  # 點數 (1-13)
            "suit": suit   # 花色 (0=方塊, 1=梅花, 2=黑桃, 3=紅心)
        }
    
    @staticmethod
    def analyze_dtb_result(tiger_value, dragon_value):
        """
        解析龍虎牌值
        
        Args:
            tiger_value (int): 虎牌值的十進位數值
            dragon_value (int): 龍牌值的十進位數值
        Returns:
            dict: 包含虎牌和龍牌的點數、花色等信息, key包括:
                - tiger_card, dragon_card: 龍虎牌型
                - tiger_card_value, dragon_card_value: 龍虎牌點數值

        """

        tiger_card_data = DTBCardParser.dtb_cards_mapping(tiger_value)
        dragon_card_data = DTBCardParser.dtb_cards_mapping(dragon_value)


        
        tiger_card = Card(tiger_card_data["rank"], tiger_card_data["suit"])
        dragon_card = Card(dragon_card_data["rank"], dragon_card_data["suit"])

        return {
            "tiger_card": tiger_card,
            "dragon_card": dragon_card,
            "tiger_card_value": tiger_card_data['rank'],
            "dragon_card_value": dragon_card_data['rank'],
        }