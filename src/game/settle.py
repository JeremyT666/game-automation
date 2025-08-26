import asyncio

from packet.packet_handler import PacketHandler
from utils.logger import logger

# 常數定義
packet_handler = PacketHandler()
SETTLE_RESP_CMD = hex(packet_handler.PROTOCOLS["settle_resp"]["cmd"])

async def recv_settle_resp(gate_handler, table_id="BC51", return_details=False):
    """接收結算協議
    Args:
        gate_handler: Gate Server 連線處理器
        table_id: 桌台ID
        return_details: 是否返回詳細的派彩資訊
    Returns:
        if return_details is True:
            tuple[bool, dict]: (成功與否, 完整解析後的結算結果數據)
            完整數據格式: {
                "total_payout": float,          # 總派彩金額
                "order_detail": list,           # 派彩詳細資訊
                "table_id": str,                # 桌台ID
                "game_code": str,               # 遊戲局號
            }
        else:
            bool, float: (成功與否, 總派彩金額)
    """
    try:
        settle_resp_queue = await gate_handler.packet_handler.register_handler(SETTLE_RESP_CMD)
        try:
            response = await asyncio.wait_for(settle_resp_queue.get(), timeout=30)  # 先設定30秒超時, 目前REL設定一局是20s
            logger.debug(f"settle resp: {response}")

            data = response.get("data")
            vid = data.get("vid")               # table id
            gmcode = data.get("gmcode")         # game code
            res = data.get("res")               # 總派彩金額(玩家總輸贏), float
            count = data.get("count")           # 玩法總數
            # seat = data.get("seat")             # 座位編號, 目前暫時沒用到
            # order_detail = data.get("detail_items") # 派彩詳細資訊

            # 20250729 - 調整order_detail的資料型態, 原始raw data是list, 但需要一個dict來方便查詢
            order_detail = {}
            for item in data.get("detail_items", []):
                playtype = item.get("playtype")
                winlose = item.get("winlose", 0.0)
                order_detail[playtype] = winlose


            if vid != table_id:
                logger.warning(f"Received settle response for wrong table: {vid}")
                return False, None
            else:
                logger.info(f"Settle response received: vid: {vid}, gmcode: {gmcode}, player winlose: {res}, count: {count}")
                # logger.info(f"Settle detail: {order_detail}")
                if return_details:
                    settle_data = {
                        "total_payout": res,          # 總派彩金額
                        "order_detail": order_detail, # 派彩詳細資訊 {玩法(數值): 輸贏金額}
                        "table_id": vid,              # 桌台ID
                        "game_code": gmcode,          # 遊戲局號
                    }
                    return True, settle_data
                else:
                    return True, res
                
        except asyncio.TimeoutError:
            logger.warning(f"Settle response timeout")
            return False, None
        except Exception as e:
            logger.error(f"Error getting settle response: {e}")
            return False, None
    except Exception as e:
        logger.error(f"Error registering settle response handler: {e}")
        return False, None
