# src/user/game_parsers.py
from utils.bitmap_mapping import BitmapParser, decimal_to_bitmap
from utils.logger import logger

class BacResultParser(BitmapParser):
    """百家樂開牌結果解析器"""
    
    def parse(self):
        """解析百家樂開牌結果
        
        位元定義 (需要根據實際協議調整):
        位置0: 一般莊派彩
        位置1: 免佣莊派彩
        位置2: 閒派彩
        位置3: 和局派彩
        位置4: 莊對派彩
        位置5: 閒對派彩
        位置8: 莊龍寶派彩
        位置9: 閒龍寶派彩
        位置12: 幸運六派彩
        位置23: 多寶派彩
        位置24: 兩張6派彩
        位置25: 三張6派彩
        位置26: 幸運7派彩
        位置27: 超級幸運7派彩
        """
        return {
            "banker": self.get_bit(1),
            "banker_nocommission": self.get_bit(2),  # 免傭莊
            "player": self.get_bit(3),
            "tie": self.get_bit(4),
            "banker_pair": self.get_bit(5),
            "player_pair": self.get_bit(6),
            # "any_pair": self.get_bit(6),
            # "perfect_pair": self.get_bit(7),
            "banker_dragon_bonus": self.get_bit(9),
            "player_dragon_bonus": self.get_bit(10),
            "lucky6": self.get_bit(13),
            "duo_bao": self.get_bit(24),
            "lucky6_2": self.get_bit(25),
            "lucky6_3": self.get_bit(26),
            "lucky7": self.get_bit(27),
            "super_lucky7": self.get_bit(28),
            "raw_decimal": self.decimal_value,
            "raw_binary": self.binary_str
        }

class DTBResultParser(BitmapParser):
    """龍虎開牌結果解析器"""
    
    def parse(self):
        """解析龍虎開牌結果
        
        位元定義 (需要根據實際協議調整):
        位置1: 虎派彩
        位置2: 龍派彩
        位置3: 和局派彩
        位置4: 虎單派彩
        位置5: 虎雙派彩
        位置6: 龍單派彩
        位置7: 龍雙派彩
        位置8: 虎紅派彩
        位置9: 虎黑派彩
        位置10: 龍紅派彩
        位置11: 龍黑派彩
        位置12: 虎牌值, 6 bytes, 12~17位
        位置18: 龍牌值, 6 bytes, 18~23位
        """
        return {
            "tiger": self.get_bit(2),
            "dragon": self.get_bit(3),
            "tie": self.get_bit(4),
            "tiger_odd": self.get_bit(5),
            "tiger_even": self.get_bit(6),
            "dragon_odd": self.get_bit(7),
            "dragon_even": self.get_bit(8),
            "tiger_red": self.get_bit(9),
            "tiger_black": self.get_bit(10),
            "dragon_red": self.get_bit(11),
            "dragon_black": self.get_bit(12),
            "tiger_value": self.get_bits(13, 6),  # 虎牌值是6 bytes, 12~17位
            "dragon_value": self.get_bits(19, 6),  # 龍牌值是6 bytes, 18~23位
            "raw_decimal": self.decimal_value,
            "raw_binary": self.binary_str
        }

def parse_game_result(game_type, res_decimal):
    """根據遊戲類型解析開牌結果
    
    Args:
        game_type: 遊戲類型 ("bac", "dtb", "sic", 等)
        res_decimal: 開牌結果的十進位數值
        
    Returns:
        dict: 解析後的開牌結果
    """
    try:
        if game_type.lower() == "bac":
            parser = BacResultParser(res_decimal)
            return parser.parse()
        elif game_type.lower() == "dtb":
            parser = DTBResultParser(res_decimal)
            return parser.parse()
        else:
            logger.warning(f"Unsupported game type: {game_type}")
            return {
                "error": f"Unsupported game type: {game_type}",
                "raw_decimal": res_decimal,
                "raw_binary": decimal_to_bitmap(res_decimal)
            }
    except Exception as e:
        logger.error(f"Failed to parse game result for '{game_type}': {e}")
        return {
            "error": str(e),
            "raw_decimal": res_decimal
        }