import asyncio
import struct
from dataclasses import dataclass
from typing import List

from packet.packet_handler import PacketHandler
from game.playtype_enums import PlayTypeFactory
from utils.logger import logger

# 常數定義
packet_handler = PacketHandler()
TABLE_STATUS_CMD = hex(packet_handler.PROTOCOLS["table_status"]["cmd"])
REQ_BET_CMD = packet_handler.PROTOCOLS["req_bet"]["cmd"]
BET_RESP_CMD = hex(packet_handler.PROTOCOLS["bet_resp"]["cmd"])
STOP_BET_CMD = hex(packet_handler.PROTOCOLS["stop_bet"]["cmd"])
SET_NO_COMM_SWITCH_REQ_CMD = packet_handler.PROTOCOLS["set_no_commission_req"]["cmd"]
SET_NO_COMM_SWITCH_RESP_CMD = hex(
    packet_handler.PROTOCOLS["set_no_commission_resp"]["cmd"]
)
SET_DUOBAO_REQ_CMD = packet_handler.PROTOCOLS["set_duobao_switch_req"]["cmd"]
SET_DUOBAO_RESP_CMD = hex(packet_handler.PROTOCOLS["set_duobao_switch_resp"]["cmd"])


@dataclass
class BetInfo:
    """投注資訊結構"""

    play_type: int  # 玩法類型
    credit: int  # 投注金額

    def pack(self) -> bytes:
        """打包投注資訊為二進制格式
        >BQ: > 表示大端序, B 表示 unsigned char (1 byte), Q 表示 unsigned long long (8 bytes)
        """
        return struct.pack(">BQ", self.play_type, self.credit)


def construct_bet_packet(
    packet_handler, vid: str, gmcode: str, bet_infos: List[BetInfo]
) -> bytes:
    """構建投注請求封包

    Args:
        vid: 桌台ID
        gmcode: 遊戲代碼
        bet_infos: 投注資訊
    """
    # 1. 打包所有投注資訊
    bet_data = b""
    for bet_info in bet_infos:
        bet_data += bet_info.pack()

    # 2. 構建基本資料
    data = packet_handler.pack_data(
        "req_bet",
        vid=vid,
        gmcode=gmcode,
        UIType=1,
    )

    # 在資料後面添加bet_data
    data += bet_data

    # 3. 添加header
    header = packet_handler.pack_header(REQ_BET_CMD, size=len(data), seq=0)
    return header + data


async def wait_for_betting_phase(
    gate_handler, table_id
) -> tuple[bool, str, str]:  # 限制return value的型別
    """
    等待進入投注階段, 這邊單獨寫function, 不使用packet_handler.wait_for_response()的原因是
    這邊需要同時監聽桌台狀態和停止下注信號, 並在任一事件發生時返回

    Args:
        gate_handler: Gate Server 連線處理器
        table_id: 桌台ID
    """

    # 獲取當前事件循環引用
    current_loop = asyncio.get_running_loop()

    status_queue = await gate_handler.packet_handler.register_handler(TABLE_STATUS_CMD)
    stop_bet_queue = await gate_handler.packet_handler.register_handler(STOP_BET_CMD)

    while True:
        try:

            # 明確創建任務
            status_task = current_loop.create_task(status_queue.get())
            stop_bet_task = current_loop.create_task(stop_bet_queue.get())

            # 同時監聽桌台狀態和停止下注信號
            # 使用隱性等待 (Implicit Waiting) - asyncio.wait() 接收協程列表 [status_queue.get(), stop_bet_queue.get()]
            # 內部自動將每個協程轉換為 asyncio.Task 對象
            # 並行執行這些任務
            # 當任一任務完成時，wait() 返回
            # done 集合包含已完成的 Task，pending 集合包含未完成的 Task
            done, pending = await asyncio.wait(
                [status_task, stop_bet_task],
                return_when=asyncio.FIRST_COMPLETED,
                timeout=30,
            )

            # 取消未完成的任務
            for task in pending:
                task.cancel()

            # 處理完成的任務
            try:
                response = done.pop().result()
                cmd = response.get("cmd")

                if cmd == TABLE_STATUS_CMD:
                    status = response.get("data", {}).get("status")
                    vid = response.get("data", {}).get("vid")

                    if vid == table_id and status == 1:  # 等待下注狀態
                        gmcode = response.get("data", {}).get("gmcode")
                        logger.info(f"Table {vid} is ready for betting")
                        return True, gmcode, vid
                    # 減少debug log數量, 暫時註解掉
                    # if vid == table_id:
                    #     logger.debug(f"Table: {vid}, current status: {status}")

                elif cmd == STOP_BET_CMD:
                    vid = response.get("data", {}).get("vid")
                    if vid == table_id:
                        logger.info(f"Table: {vid} received stop bet")
                        return False, None, None

            except Exception as e:
                logger.error(f"Error getting task result: {e}")
                import traceback

                logger.error(traceback.format_exc())
                return False, None, None

        except Exception as e:
            logger.error(f"Error waiting for betting phase: {e}")
            return False, None, None


async def place_bet(
    gate_handler, bet_infos: List[BetInfo], game_type="bac", table_id="BC51", max_retries: int = 5
) -> bool:
    """執行投注
    1. 等待投注階段
    2. 發送投注請求
    3. 等待回應

    投注邏輯：
    - 投注前收到 stop bet：等待下一個投注階段
    - 投注後收到 stop bet：繼續等待 bet_resp

    Args:
        gate_handler: Gate Server 連線處理器
        bet_infos: 投注資訊列表
        game_type: 遊戲類型 (預設為 "bac")
        table_id: 桌台ID
        max_retries: 最大重試次數 (預設為 5)

    Returns:
        dict: 包含投注結果和回應碼的字典
            - result: bool, 投注是否成功
            - bet_resp_code: int, 投注回應碼
            - bet_resp_gmcode: str, 投注回應的gmcode
    """
    retry_count = 0

    try:
        # 使用工廠類獲取對應的玩法枚舉
        PlayType = PlayTypeFactory.get(game_type)
    except ValueError as e:
        logger.warning(f"{e} - Will use numeric play type codes")
        PlayType = None

    while retry_count < max_retries:
        # 等待投注階段
        betting_available, gmcode, vid = await wait_for_betting_phase(
            gate_handler, table_id
        )
        if not betting_available:
            logger.info("Waiting for new game round...")
            retry_count += 1
            continue  # 繼續等待下一個投注階段

        try:
            # 註冊投注回應處理
            bet_resp_queue = await gate_handler.packet_handler.register_handler(
                BET_RESP_CMD
            )

            # 發送投注請求
            packet = construct_bet_packet(
                gate_handler.packet_handler, vid, gmcode, bet_infos
            )
            # 顯示下注玩法資訊
            try:
                # 記錄下注詳情
                bet_details = []
                for bet in bet_infos:
                    if PlayType:
                        # 如果能導入玩法枚舉，則顯示名稱
                        play_type_name = PlayType.get_name(bet.play_type)
                    else:
                        # 如果無法導入玩法枚舉，則顯示數字代碼
                        play_type_name = f"UNKNOWN_PLAY_TYPE_{bet.play_type}"

                    bet_details.append(
                        f"{play_type_name}({bet.play_type}) - ${bet.credit}"
                    )

                # log_and_print(f"Betting on table {table_id} with: {', '.join(bet_details)}", level=logging.INFO)
            except ImportError:
                # 如果無法導入玩法枚舉，則顯示數字代碼
                logger.info(f"Betting with raw play types: {[f'{b.play_type}: {b.credit}' for b in bet_infos]}")

            await gate_handler.send(packet, "Bet Request")
            logger.info(f"Betting on {table_id} / {gmcode} with: {', '.join(bet_details)}")

            try:
                response = await asyncio.wait_for(bet_resp_queue.get(), timeout=15)
                # 處理投注回應
                bet_resp_code = response.get("data", {}).get("code")
                bet_resp_vid = response.get("data", {}).get("vid")  # 先取table id備用
                bet_resp_gmcode = response.get("data", {}).get(
                    "gmcode"
                )  # 先取gmcode備用
                logger.debug(
                    f"bet_resp_code: {bet_resp_code}, bet_resp_vid: {bet_resp_vid}, bet_resp_gmcode: {bet_resp_gmcode}"
                )

                # 定義func return的資料
                bet_result = {}

                # 針對各種不同response code做對應處理
                if bet_resp_code == 0:
                    logger.info(f"Table: {vid}, Bet placed successfully")
                    bet_result["result"] = True
                    bet_result["bet_resp_code"] = bet_resp_code
                    bet_result["bet_resp_gmcode"] = bet_resp_gmcode
                    return bet_result

                elif bet_resp_code == 10:
                    logger.warning(
                        f"Bet Failed with code {bet_resp_code}, bet exceeds allowed personal limit."
                    )
                    bet_result["result"] = False
                    bet_result["bet_resp_code"] = bet_resp_code
                    bet_result["bet_resp_gmcode"] = bet_resp_gmcode
                    return bet_result

                elif bet_resp_code == 11:
                    logger.warning(
                        f"Bet Failed with code {bet_resp_code}, bet exceeds allowed table limit."
                    )
                    bet_result["result"] = False
                    bet_result["bet_resp_code"] = bet_resp_code
                    bet_result["bet_resp_gmcode"] = bet_resp_gmcode
                    return bet_result
                    
                elif bet_resp_code == 13:
                    logger.warning(
                        f"Bet Failed with code {bet_resp_code}, Invalid playtype"
                    )
                    bet_result["result"] = False
                    bet_result["bet_resp_code"] = bet_resp_code
                    bet_result["bet_resp_gmcode"] = bet_resp_gmcode
                    return bet_result

                elif bet_resp_code == 18:
                    logger.warning(
                        f"Bet Failed with code {bet_resp_code}, gmcode expired."
                    )
                    bet_result["result"] = False
                    bet_result["bet_resp_code"] = bet_resp_code
                    bet_result["bet_resp_gmcode"] = bet_resp_gmcode
                    return bet_result

                elif bet_resp_code == 25:
                    logger.warning(
                        f"Bet Failed with code {bet_resp_code}, Betting time has expired."
                    )
                    bet_result["result"] = False
                    bet_result["bet_resp_code"] = bet_resp_code
                    bet_result["bet_resp_gmcode"] = bet_resp_gmcode
                    return bet_result
                
                elif bet_resp_code == 641:
                    logger.warning(
                        f"Bet successed with code {bet_resp_code}, Slow deduction, gameserver will patch reckon for player."
                    )
                    bet_result["result"] = True
                    bet_result["bet_resp_code"] = bet_resp_code
                    bet_result["bet_resp_gmcode"] = bet_resp_gmcode
                    return bet_result

                else:
                    logger.error(f"Bet Failed with code {bet_resp_code}")
                    logger.debug(f"Raw bet response: {response}")
                    bet_result["result"] = False
                    bet_result["bet_resp_code"] = bet_resp_code
                    bet_result["bet_resp_gmcode"] = bet_resp_gmcode
                    return bet_result
                    # return False, bet_resp_code, bet_resp_gmcode

            except asyncio.TimeoutError:
                retry_count += 1
                logger.warning("Bet response timeout")

                if retry_count > max_retries:
                    logger.error(
                        f"Max retries reached {max_retries}. Stopping betting attempts."
                    )
                    bet_result["result"] = False
                    bet_result["bet_resp_code"] = -1
                    bet_result["bet_resp_gmcode"] = None
                    return bet_result
                    # return False, -1, None
                continue

        except Exception as e:
            retry_count += 1
            logger.error(f"Error placing bet: {e}")

            if retry_count > max_retries:
                logger.error(
                    f"Max retries reached {max_retries}. Stopping betting attempts."
                )
                bet_result["result"] = False
                bet_result["bet_resp_code"] = -1
                bet_result["bet_resp_gmcode"] = None
                return bet_result
                # return False
            continue

    bet_result = {
        "result": False,
        "bet_resp_code": -1,
        "bet_resp_gmcode": None,
    }
    logger.error(f"Max retries reached {max_retries}. Stopping betting attempts.")
    return bet_result

async def raise_bet(
    gate_handler, bet_infos: List[BetInfo], game_type="bac", table_id="BC51", current_gmcode=None
) -> tuple[bool, int]:
    """在當前投注階段進行加注

    與place_bet不同，raise_bet需要提供當前局的gmcode進行加注

    Args:
        gate_handler: Gate Server 連線處理器
        bet_infos: 加注資訊列表
        game_type: 遊戲類型 (預設為 "bac")
        table_id: 桌台ID
        current_gmcode: 當前局的gmcode，必須提供此參數

    Returns:
        int: 加注回應碼
    """
    try:
        # 使用工廠類獲取對應的玩法枚舉
        PlayType = PlayTypeFactory.get(game_type)
    except ValueError as e:
        logger.warning(f"{e} - Will use numeric play type codes")
        PlayType = None

    try:
        # 如果沒有提供 gmcode，直接return False
        if current_gmcode is None:
            logger.error("Error: current_gmcode is required for raise_bet")
            return -1

        # 註冊投注回應處理
        bet_resp_queue = await gate_handler.packet_handler.register_handler(
            BET_RESP_CMD
        )

        # 使用提供的 gmcode 和 table_id
        gmcode = current_gmcode
        vid = table_id

        # 構建並發送投注請求
        packet = construct_bet_packet(
            gate_handler.packet_handler, vid, gmcode, bet_infos
        )

        # 顯示加注玩法資訊
        bet_details = []
        for bet in bet_infos:
            if PlayType:
                # 如果能導入玩法枚舉，則顯示名稱
                play_type_name = PlayType.get_name(bet.play_type)
            else:
                # 如果無法導入玩法枚舉，則顯示數字代碼
                play_type_name = f"UNKNOWN_PLAY_TYPE_{bet.play_type}"

            bet_details.append(f"{play_type_name}({bet.play_type}) - ${bet.credit}")

        logger.info(f"Increasing bet on {table_id} / {gmcode} with: {', '.join(bet_details)}")
        await gate_handler.send(packet, "Increase Bet Request")

        # 等待投注回應
        response = await asyncio.wait_for(bet_resp_queue.get(), timeout=15)
        bet_resp_code = response.get("data", {}).get("code")

        # 處理回應結果
        if bet_resp_code == 0:
            logger.info(f"Table: {vid}, Bet increased successfully")
        else:
            logger.error(f"Increase bet failed with code: {bet_resp_code}")

        return bet_resp_code

    except Exception as e:
        logger.error(f"Error placing increase bet: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return -1


def construct_set_nocomm_switch_req_packet(packet_handler, flag: int) -> bytes:
    """構建設置免傭開關請求封包

    Args:
        packet_handler: 封包處理器
        flag: 免傭開關 (0: 關閉免傭, 1: 開啟免傭)

    Returns:
        bytes: 封包資料
    """
    data = packet_handler.pack_data(
        "set_no_commission_req",
        flag=flag,
    )

    header = packet_handler.pack_header(
        SET_NO_COMM_SWITCH_REQ_CMD, size=len(data), seq=0
    )

    return header + data


async def set_nocomm_switch(gate_handler, flag: int) -> bool:
    """發送設置免傭開關請求
    Args:
        gate_handler: Gate Server 連線處理器
        flag: 免傭開關 (0: 關閉免傭, 1: 開啟免傭)
    Returns:
        bool: 請求是否成功
    """
    try:
        packet = construct_set_nocomm_switch_req_packet(packet_handler, flag)
        await gate_handler.send(packet, "Set No Commission Switch Request")
        # log_and_print(f"Set No Commission Switch Request sent with flag: {flag}", level=logging.DEBUG)

        # 等待回應
        set_nocomm_resp_queue = await gate_handler.packet_handler.register_handler(
            SET_NO_COMM_SWITCH_RESP_CMD
        )
        response = await asyncio.wait_for(set_nocomm_resp_queue.get(), timeout=10)
        # log_and_print(f"Set No Commission Switch Response: {response}", level=logging.DEBUG)

        # 處理回應
        resp_code = response.get("data", {}).get("code")
        resp_flag = response.get("data", {}).get("flag")
        if resp_code == 0:
            logger.info(f"Set No Commission Switch successful with flag: {resp_flag}")
            return True
        else:
            logger.error(f"Set No Commission Switch failed with code: {resp_code}")
            return False
    except Exception as e:
        logger.error(f"Error sending Set No Commission Switch Request: {e}")
        return False


def construct_set_duobao_switch_req_packet(packet_handler, flag: int) -> bytes:
    """構建設置多寶開關請求封包

    Args:
        packet_handler: 封包處理器
        flag: 多寶開關 (0: 幸運六 1: 經典 2: 龍寶 3: 多寶 4: 幸運七(預設))

    Returns:
        bytes: 封包資料
    """
    data = packet_handler.pack_data(
        "set_duobao_switch_req",
        flag=flag,
    )

    header = packet_handler.pack_header(SET_DUOBAO_REQ_CMD, size=len(data), seq=0)

    return header + data


async def set_duobao_switch(gate_handler, flag: int) -> bool:
    """發送設置多寶開關請求
    Args:
        gate_handler: Gate Server 連線處理器
        flag: 多寶開關 (0: 幸運六 1: 經典 2: 龍寶 3: 多寶 4: 幸運七(預設))

    Returns:
        bool: 請求是否成功
    """
    try:
        packet = construct_set_duobao_switch_req_packet(packet_handler, flag)
        await gate_handler.send(packet, "Set DuoBao Switch Request")
        # log_and_print(f"Set DuoBao Switch Request sent with flag: {flag}", level=logging.DEBUG)

        # 等待回應
        set_duobao_resp_queue = await gate_handler.packet_handler.register_handler(
            SET_DUOBAO_RESP_CMD
        )
        response = await asyncio.wait_for(set_duobao_resp_queue.get(), timeout=10)
        logger.debug(f"Set DuoBao Switch Response: {response}")

        # 處理回應
        resp_code = response.get("data", {}).get("code")
        resp_flag = response.get("data", {}).get("flag")
        if resp_code == 0:
            logger.info(f"Set DuoBao Switch successful with flag: {resp_flag}")
            return True
        else:
            logger.error(f"Set DuoBao Switch failed with code: {resp_code}")
            return False
    except Exception as e:
        logger.error(f"Error sending Set DuoBao Switch Request: {e}")
        return False
