import asyncio
import json

from packet.packet_handler import PacketHandler
from utils.logger import logger
from game.game_result_parser import parse_game_result
from game.card_parser import BacCardParser, DTBCardParser

# 常數定義
packet_handler = PacketHandler()
GAME_RESULT_CMD = hex(packet_handler.PROTOCOLS["game_result"]["cmd"])  # 假設協議名稱為 "game_result"

async def recv_game_result(gate_handler, table_id="BC51", expected_gmcode=None, timeout=30):
    """接收遊戲開牌結果
    
    Args:
        gate_handler: Gate Server 連線處理器
        table_id: 桌台ID
        timeout: 等待超時時間（秒）
    
    Returns:
        tuple[bool, dict]: (成功與否, 完整解析後的開牌結果數據)
        完整數據格式: {
            "json_raw_data": {...},         # 原始協議數據
            "game_type": "bac",             # 遊戲類型
            "table_id": "BC51",             # 桌台ID
            "game_code": "12345",           # 遊戲局號
            "parsed_result": {...},         # bitmap解析結果 (中獎判斷)
            "card_analysis": {...},         # 牌型解析結果 (賠率計算用)
            "raw_bitmap": 123456,           # 原始bitmap值
            "raw_json": {...}               # 原始JSON數據
        }
    """
    try:
        game_result_queue = await gate_handler.packet_handler.register_handler(GAME_RESULT_CMD)
        
        # 記錄開始等待的時間
        start_time = asyncio.get_event_loop().time()
        
        while True:  # 持續等待，直到收到正確桌台的結果或超時
            remaining_timeout = timeout - (asyncio.get_event_loop().time() - start_time)
            
            # 檢查是否已超時
            if remaining_timeout <= 0:
                logger.warning(f"Game result timeout after {timeout}s")
                return False, None
            
            try:
                # 使用剩餘超時時間等待
                response = await asyncio.wait_for(game_result_queue.get(), timeout=remaining_timeout)
                logger.debug(f"Game result: {response}")

                protocol_data = response.get("data", {})   # 實際協議內容
                vid = protocol_data.get("vid")             # 桌台ID
                gmtype = protocol_data.get("gmtype")       # 遊戲類型
                game_result_json = protocol_data.get("json", "{}")  # 前一局開牌結果的json字串, 根據不同遊戲類型, 該json內容會不同, 為不定長度
                gmcode = game_result_json.get("gmcode")  # 遊戲局號
                res_decimal = game_result_json.get("res", 0)  # 開牌結果的十進位數值
                
                if vid != table_id:
                    # 桌台不匹配，記錄但不返回，繼續等待
                    logger.debug(f"Received game result for wrong table: {vid}, expected: {table_id}. Continuing to wait...")
                    continue  # 繼續下一輪等待
                
                if gmcode != expected_gmcode:
                    # 遊戲局號不匹配，記錄但不返回，繼續等待
                    logger.debug(f"Received game result for wrong game code: {gmcode}, expected: {expected_gmcode}. Continuing to wait...")
                    continue

                else:
                    # ===== 完成所有解析工作 =====  
                    # 1. 解析res內的bitmap
                    bitmap_parsed_result = parse_game_result(gmtype, res_decimal)
                    logger.debug(f"bitmap_parsed_result: {bitmap_parsed_result}")

                    # 2. 依據遊戲類型, 解析牌型
                    card_analysis = None
                    # 百家樂牌型解析
                    if gmtype.lower() == "bac":
                        cards_data = game_result_json.get("cards", [])
                        dragon_bonus_info = {
                            "type": game_result_json.get("dragontype", 999),    # 龍寶類型
                            "odds": game_result_json.get("dragonodd", 999),     # 龍寶賠率
                        }
                        duobao_type = game_result_json.get("duobaotype", 999)  # 多寶牌型

                        lucky6_info = {
                            "lucky6": bitmap_parsed_result.get("lucky6", None),  
                            "lucky6_2": bitmap_parsed_result.get("lucky6_2", None),
                            "lucky6_3": bitmap_parsed_result.get("lucky6_3", None),
                        }
                        lucky7_info = {
                            "lucky7": bitmap_parsed_result.get("lucky7", None),  
                            "super_lucky7": bitmap_parsed_result.get("super_lucky7", None),
                        }
                        res_data = {
                            "res_decimal": res_decimal,  # 原始res值
                            "res_binary": bitmap_parsed_result.get("raw_binary", ""),  # 原始bitmap二進位字串
                        }

                        base_card_analysis = BacCardParser.analyze_bac_result(cards_data, dragon_bonus_info, duobao_type)
                        card_analysis = {**base_card_analysis, **lucky6_info, **lucky7_info, **res_data}
                    
                    # 龍虎牌型解析
                    elif gmtype.lower() == "dtb":
                        tiger_value = bitmap_parsed_result.get("tiger_value", 999)
                        dragon_value = bitmap_parsed_result.get("dragon_value", 999)
                        base_card_analysis = DTBCardParser.analyze_dtb_result(tiger_value, dragon_value)
                        card_analysis = {**bitmap_parsed_result, **base_card_analysis}  # 合併解析結果


                    # 3. 整合解析結果 + 統一格式
                    game_result_data = {
                        "protocol_data": protocol_data,  # 原始協議數據
                        "game_type": gmtype,  # 遊戲類型
                        "table_id": vid,  # 桌台ID
                        "game_code": gmcode,  # 遊戲局號
                        # "parsed_result": parsed_result,  # bitmap解析結果
                        "card_analysis": card_analysis,  # 牌型解析結果, 含各玩法輸贏(True/False), 開牌牌型, res_decimal, res_binary
                        # "raw_decimal": res_decimal,  # 原始bitmap值
                    }

                    logger.info(f"Game result received for table: {vid}, gmcode: {gmcode}")
                    logger.debug(f"Game result data after processed: {game_result_data}")
                    
                    return True, game_result_data
                    
            except asyncio.TimeoutError:
                logger.warning(f"Game result timeout after {timeout}s from table {table_id}")
                return False, None
            
            except Exception as e:
                logger.error(f"Exception occurred while handling game result: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return False, None
                
    except Exception as e:
        logger.error(f"Error registering game result handler: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False, None
    