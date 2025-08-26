from game.payout.payout_calculator import PayoutCalculator
from utils.logger import logger

class PayoutVerifier:
    """派彩驗證器"""

    @staticmethod
    async def verify_game_payout(game_type, game_result, bet_details, settle_data=None):
        """驗證遊戲派彩
        Args:
            game_type: 遊戲類型 (例如 "bac" 或 "dtb")
            game_result: 遊戲結果數據
            bet_details: 投注詳情列表，包含玩法和金額

        Returns:
            tuple[bool, dict]: (驗證結果, 詳細信息)

        Note:
            - 派彩計算允許 0.01 的浮點數誤
            - 這邊驗證的派彩, 不含"本金"(投注額), 也就是僅驗證玩家的輸贏值
        """
        try:
            if game_type.lower() == "bac":
                return await PayoutVerifier._verify_bac_payout(game_result, bet_details, settle_data)
            elif game_type.lower() == "dtb":
                return await PayoutVerifier._verify_dtb_payout(game_result, bet_details, settle_data)
            else:
                return False, {"error": f"Unsupported game type: {game_type}"}
                
        except Exception as e:
            logger.error(f"Error verifying payout: {e}")
            return False, {"error": str(e)}
    
    @staticmethod
    async def _verify_bac_payout(game_result, bet_details, settle_data):
        """驗證百家樂派彩
        Args:
            game_result: 遊戲結果數據
            bet_details: 投注詳情列表，包含玩法和金額
            settle_data: 結算數據，包含實際派彩

        Returns:
            tuple[bool, dict]: (驗證結果, 詳細信息)
        """
        try:
            # 解析牌型
            card_analysis = game_result.get("card_analysis", {})
            gmcode = game_result.get("game_code", "")
            verification_results = []
            # total_expected_payout = 0.0

            for bet in bet_details:
                play_type = bet.play_type
                bet_amount = bet.credit
                # 從系統獲得的實際派彩, 直接使用play_type的數值來查詢會查不到, 因play_type是Enum物件, 需要使用play_type.value來獲取對應的int值, 才能正確取值
                actual_payout = settle_data["order_detail"][play_type.value]

                expected_payout, reason = PayoutCalculator.calculate_bac_payout(
                    play_type, bet_amount, card_analysis
                )
                
                logger.info(f"Expected payout: {expected_payout}, Actual payout: {actual_payout}")
                is_correct = abs(expected_payout - actual_payout) < 0.01  # 允許小數點誤差
                
                # 每個驗證結果資料都是dict, 而最後verification_results是一個list
                # 原先預期是會驗證同一局下多筆注單, 所以使用list內放dict的資料結構, 主要是為了用來存放每個投注的驗證結果
                # TODO: 但實際測試上, 目前每局只會有一筆注單, 所以這邊的結構可以簡化成dict
                verification_results.append({
                    "game_code": gmcode,
                    "play_type": play_type,
                    "bet_amount": bet_amount,
                    "expected_payout": expected_payout,
                    "actual_payout": actual_payout,
                    "is_correct": is_correct,
                    "reason": reason
                })
                
                # total_expected_payout += expected_payout
            
            all_correct = all(result["is_correct"] for result in verification_results)

            if all_correct:
                logger.info("Payouts verified successfully")
            else:
                logger.warning("Payouts did not match expected values")
            
            return all_correct, {
                "game_type": "bac",
                "card_analysis": card_analysis,
                "verification_results": verification_results,
                # "total_expected_payout": total_expected_payout
            }
            
        except Exception as e:
            logger.error(f"Failed verifying BAC payout: {e}")
            return False, {"error": str(e)}
    
    @staticmethod
    async def _verify_dtb_payout(game_result, bet_details, settle_data):
        """驗證龍虎派彩"""
        try:
            # 解析牌型 (從bitmap數據)
            # 此處與bac做法不同, 因為server協議廣播的raw data也不同格式, 資料處理與解析已經在recv_game_result中完成, 故直接從game_result中獲取
            parsed_result = game_result.get("card_analysis", {})    # 這裡直接取牌型解析資料, 因為在recv_game_result中已經完成了bitmap解析 

            gmcode = game_result.get("game_code", "")

            verification_results = []
            # total_expected_payout = 0.0
            
            for bet in bet_details:
                play_type = bet.play_type
                bet_amount = bet.credit
                actual_payout = settle_data["order_detail"][play_type.value]
                
                expected_payout, reason = PayoutCalculator.calculate_dtb_payout(
                    play_type, bet_amount, parsed_result
                )
                
                logger.info(f"Expected payout: {expected_payout}, Actual payout: {actual_payout}")
                is_correct = abs(expected_payout - actual_payout) < 0.01
                
                verification_results.append({
                    "game_code": gmcode,
                    "play_type": play_type,
                    "bet_amount": bet_amount,
                    "expected_payout": expected_payout,
                    "actual_payout": actual_payout,
                    "is_correct": is_correct,
                    "reason": reason
                })
                
                # total_expected_payout += expected_payout
            
            all_correct = all(result["is_correct"] for result in verification_results)

            if all_correct:
                logger.info("Payouts verified successfully")
            else:
                logger.warning("Payouts did not match expected values")

            return all_correct, {
                "game_type": "dtb",
                "card_analysis": parsed_result,
                "verification_results": verification_results,
                # "total_expected_payout": total_expected_payout
            }
            
        except Exception as e:
            logger.error(f"Error verifying DTB payout: {e}")
            return False, {"error": str(e)}