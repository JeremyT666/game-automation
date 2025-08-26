from game.odds_tables import *
from utils.logger import logger

class PayoutCalculator:
    """派彩計算器"""
    
    @staticmethod
    def calculate_bac_payout(play_type, bet_amount, card_analysis):
        """計算百家樂派彩
        Args:
            play_type: 玩法類型
            bet_amount: 投注金額
            card_analysis: 牌型分析結果
            
        Returns:
            tuple[float, str]: (派彩金額, 理由)
        """
        try:
            # 獲取玩法對應賠率
            payout_info = BAC_PAYOUT_TABLE.get(play_type)
            if not payout_info:
                return 0.0, f"Unknown play type: {play_type}"
            
            # 檢查玩法結果是否為贏
            is_winning = PayoutCalculator._check_bac_winning(play_type, card_analysis)
            logger.debug(f"Checking winning for {play_type}: {is_winning}")
            tie_result = card_analysis.get("tie", False)

            # 正常贏錢狀況, 直接pass, 繼續後續邏輯判斷
            if is_winning:
                pass
            else:
                # 輸錢, 檢查是否為特殊狀況(莊閒玩法退本金)
                if tie_result and play_type in [BacPlayType.BANKER, BacPlayType.BANKER_NOCOMMISSION, BacPlayType.PLAYER]:
                    # 和局退本金, 直接return 0.0
                    return 0.0, f"{get_play_type_name('bac', play_type)} is a tie, no payout"
                # 第二種特殊狀況, 龍寶在莊閒開例牌和局時, 也退本金
                elif tie_result and play_type in [BacPlayType.BANKER_DRAGON_BONUS, BacPlayType.PLAYER_DRAGON_BONUS]:
                    all_cards_count = len(card_analysis.get("player_cards", [])) + len(card_analysis.get("banker_cards", []))
                    # 莊閒合計4張牌且都是例牌
                    is_natural_tie = (
                        all_cards_count == 4 and
                        card_analysis.get("player_value", 0) in [8, 9] and
                        card_analysis.get("banker_value", 0) in [8, 9]
                        )
                    if is_natural_tie:
                        return 0.0, f"{get_play_type_name('bac', play_type)} is a natural tie, no payout"
                # 一般輸錢的狀況
                else:
                    return -bet_amount, f"{get_play_type_name('bac', play_type)} not winning"

            # 計算派彩
            if payout_info["type"] == "fixed":
                payout = bet_amount * payout_info["base_odds"]
                return payout, "Fixed odds payout"
            
            elif payout_info["type"] == "variable":
                # 判斷是否莊家6點贏, 免傭莊的特殊處理
                if play_type == BacPlayType.BANKER_NOCOMMISSION:
                    if card_analysis["banker_value"] == 6:
                        odds = BANKER_NOCOMMISSION_ODDS.get("banker_6", 0)
                        payout = bet_amount * odds
                        return payout, f"Banker no commission odds: {odds} (banker got 6)"
                    else:
                        odds = BANKER_NOCOMMISSION_ODDS.get("default", 0)
                        payout = bet_amount * odds
                        return payout, f"Banker no commission odds: {odds} (default odds, banker not 6)"
                    
                elif play_type in [BacPlayType.BANKER_DRAGON_BONUS, BacPlayType.PLAYER_DRAGON_BONUS]:
                    # 龍寶派彩 (根據贏牌差距)
                    win_margin = card_analysis.get("win_margin", 0)
                    odds = card_analysis["dragon_bonus_odds"]   # 直接從解析後的資料取賠率
                    # odds = DRAGON_BONUS_ODDS.get(win_margin, 0)
                    payout = bet_amount * odds
                    return payout, f"Dragon bonus odds: {odds} (margin: {win_margin})"
                
                elif play_type == BacPlayType.LUCKY6:
                    # 幸運六派彩 (根據莊家牌數)
                    banker_cards_count = len(card_analysis.get("banker_cards", []))
                    odds = LUCKY6_ODDS.get(banker_cards_count, 0)
                    payout = bet_amount * odds
                    return payout, f"Lucky6 odds: {odds} (banker cards count: {banker_cards_count})"
                
                elif play_type == BacPlayType.DUO_BAO:
                    # 多寶派彩
                    duobao_type = card_analysis.get("duobao_type", 0)   # 從解析後的資料取牌型
                    odds = DUOBAO_ODDS.get(duobao_type, 0)
                    logger.debug(f"Duo Bao type: {duobao_type}, odds: {odds}")
                    payout = bet_amount * odds
                    return payout, f"Duo Bao odds: {odds} (type: {duobao_type})"
                
                elif play_type == BacPlayType.LUCKY7:
                    # 幸運七派彩
                    player_cards_count = len(card_analysis.get("player_cards", []))
                    odds = LUCKY7_ODDS.get(player_cards_count, 0)
                    payout = bet_amount * odds
                    return payout, f"Lucky7 odds: {odds} (player cards count: {player_cards_count})"
                
                elif play_type == BacPlayType.SUPER_LUCKY7:
                    # 超級幸運七派彩
                    all_cards_count = len(card_analysis.get("player_cards", [])) + len(card_analysis.get("banker_cards", []))
                    # player_cards_count = len(card_analysis.get("player_cards", []))
                    odds = SUPER_LUCKY7_ODDS.get(all_cards_count, 0)
                    payout = bet_amount * odds
                    return payout, f"Super Lucky7 odds: {odds} (all cards count: {all_cards_count})"

            
            return 0.0, "Variable odds calculation failed"
            
        except Exception as e:
            logger.error(f"Failed calculating BAC payout: {e}")
            return 0.0, f"Calculation error: {e}"
    
    @staticmethod
    def calculate_dtb_payout(play_type, bet_amount, card_analysis):
        """計算龍虎派彩"""
        try:
            # 獲取玩法對應賠率
            payout_info = DTB_PAYOUT_TABLE.get(play_type)
            if not payout_info:
                return 0.0, f"Unknown play type: {play_type}"
            
            # 檢查是否中獎
            is_winning = PayoutCalculator._check_dtb_winning(play_type, card_analysis)
            logger.debug(f"Checking winning for {play_type}: {is_winning}")
            tie_result = card_analysis.get("tie", False)

            if is_winning:
                # 龍虎都是固定賠率
                payout = bet_amount * payout_info["base_odds"]
                return payout, f"Fixed odds payout: {payout_info['base_odds']}"
                # pass
            elif tie_result and play_type in [DtbPlayType.TIGER, DtbPlayType.DRAGON]:
                half_bet_amount = bet_amount / 2
                # 特別處理, 和局龍虎退一半本金
                return -half_bet_amount, "Tie result: half of the bet amount is returned"
            else:
                return -bet_amount, f"{get_play_type_name('dtb', play_type)} not winning"

            
        except Exception as e:
            logger.error(f"Error calculating DTB payout: {e}")
            return 0.0, f"Calculation error: {e}"
    
    @staticmethod
    def _check_bac_winning(play_type, card_analysis):
        """檢查百家樂是否中獎"""

        winning_checks = {
            BacPlayType.BANKER: card_analysis.get("banker", False),
            BacPlayType.BANKER_NOCOMMISSION: card_analysis.get("banker", False), # 免傭莊一樣取banker的解析結果
            BacPlayType.PLAYER: card_analysis.get("player", False),
            BacPlayType.TIE: card_analysis.get("tie", False),
            BacPlayType.BANKER_PAIR: card_analysis.get("banker_pair", False),
            BacPlayType.PLAYER_PAIR: card_analysis.get("player_pair", False),
            BacPlayType.BANKER_DRAGON_BONUS: card_analysis.get("banker_dragon_bonus", False),
            BacPlayType.PLAYER_DRAGON_BONUS: card_analysis.get("player_dragon_bonus", False),
            BacPlayType.LUCKY6: card_analysis.get("lucky6", False),
            BacPlayType.DUO_BAO: card_analysis.get("duobao", False),    # 這邊用duobao去取是因為raw data解析出來的json內就是duobao這個key
            BacPlayType.LUCKY6_2: card_analysis.get("lucky6_2", False),
            BacPlayType.LUCKY6_3: card_analysis.get("lucky6_3", False),
            BacPlayType.LUCKY7: card_analysis.get("lucky7", False),
            BacPlayType.SUPER_LUCKY7: card_analysis.get("super_lucky7", False),
        }

        # 添加檢查, 避免沒有定義到導致錯誤
        if play_type not in winning_checks:
            logger.error(f"Unknown play type: {play_type}")
        else:
            pass
        
        return winning_checks.get(play_type, False)
    
    @staticmethod
    def _check_dtb_winning(play_type, card_analysis):
        """檢查龍虎是否中獎"""
        # parsed_result = game_result.get("parsed_result", {})
        
        winning_checks = {
            DtbPlayType.TIGER: card_analysis.get("tiger", False),
            DtbPlayType.DRAGON: card_analysis.get("dragon", False),
            DtbPlayType.TIE: card_analysis.get("tie", False),
            DtbPlayType.TIGER_ODD: card_analysis.get("tiger_odd", False),
            DtbPlayType.TIGER_EVEN: card_analysis.get("tiger_even", False),
            DtbPlayType.DRAGON_ODD: card_analysis.get("dragon_odd", False),
            DtbPlayType.DRAGON_EVEN: card_analysis.get("dragon_even", False),
            DtbPlayType.TIGER_RED: card_analysis.get("tiger_red", False),
            DtbPlayType.TIGER_BLACK: card_analysis.get("tiger_black", False),
            DtbPlayType.DRAGON_RED: card_analysis.get("dragon_red", False),
            DtbPlayType.DRAGON_BLACK: card_analysis.get("dragon_black", False),
        }
        
        return winning_checks.get(play_type, False)