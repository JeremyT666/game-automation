import asyncio
import struct

from protocols.protocols import HEADER_FORMAT, HEADER_SIZE, PROTOCOLS
from protocols.descriptors import PROTOCOL_DESCRIPTORS
from utils.logger import logger

# Define skip commands list at class level
# 用於跳過不需要解析的指令, 0x030005有點奇怪, 看起來仍是會收到這個指令
SKIP_PARSE_CMD = [0x030005]
class PacketHandler:
    """
    PacketHandler 負責處理封包的打包和解包。

    方法:
    - pack_header(cmd, size, seq): 打包封包的header。
    - unpack_header(header_data): 解包封包的header。
    - pack_data(protocol_name, **kwargs): 根據協議名稱打包封包數據。
    - unpack_data(protocol_name, data): 根據協議名稱解包封包數據。
    - start_processor(): 啟動封包處理器。
    - stop_processor(): 停止封包處理器。
    - _process_packets(): 持續處理接收到的封包。
    - register_handler(cmd): 註冊一個命令處理器，返回與當前循環綁定的隊列。
    - wait_for_response(cmd, timeout=30): 等待特定指令的回應。
    - unpack_variable_data(data, offset=53, count=0): 解析不定長度的數據字段, 目前用於 settle_resp 協議的 data 字段。
    """
    
    def __init__(self, ws_client=None):
        self.HEADER_FORMAT = HEADER_FORMAT
        self.HEADER_SIZE = HEADER_SIZE
        self.PROTOCOLS = PROTOCOLS

        # 新增屬性
        self.ws_client = ws_client
        self.cmd_queues = {}        # 指令佇列 {cmd: Queue}
        self._loop_queues = {}      # 格式: {loop_id: {cmd: Queue}}
        self.running = True         # 處理器運行狀態
        self.processor_task = None  # 處理器任務

    def pack_header(self, cmd, size, seq):
        """打包header
        參數:
        - cmd (int): 協議號
        - size (int): 封包大小
        - seq (int): 序列號, 皆為0

        返回:
        - bytes: 打包後的header。
        """
        # 添加對傳入cmd的判斷, 如果cmd是str, 則轉換成int, 避免因為資料型態錯誤導致packing失敗
        if isinstance(cmd, str):
            cmd = int(cmd, 16)
        else:
            pass
        
        size = size + self.HEADER_SIZE # 封包資料大小加上header大小 (header size 固定 12 bytes)
        return struct.pack(self.HEADER_FORMAT, cmd, size, seq)

    def unpack_header(self, header_data):
        """
        解包封包的header。

        參數:
        - header_data (bytes): header數據。

        返回:
        - tuple: 解包後的header數據。分別會return cmd, size, seq。
        """
        if len(header_data) != self.HEADER_SIZE:
            raise ValueError(f"Invalid header size: expected {self.HEADER_SIZE}, got {len(header_data)}")
        # struct.unpack() 返回的是一個tuple, python標準庫中用來處理二進制數據的函數
        # 這裡的HEADER_FORMAT是一個字符串, 用來定義如何解讀binary data, 數值應為">III"
        # 這裡的header_data是一個bytes對象, 要解析的binary data
        # 會return一個tuple, 分別為cmd, size, seq
        unpacked_data = struct.unpack(self.HEADER_FORMAT, header_data)
        # print(f"DEBUG unpack_header (Hex): {(unpacked_data[0].to_bytes(4, byteorder='big')).hex()}")
        # print(f"DEBUG unpack_header: {unpacked_data}")
        return unpacked_data

    def pack_data(self, protocol_name, **kwargs):
        """
        根據協議名稱打包封包數據。

        參數:
        - protocol_name (str): 協議名稱。
        - **kwargs: 封包數據。

        返回:
        - bytes: 打包後的封包數據。
        """
        protocol = self.PROTOCOLS[protocol_name]
        format_string = protocol["format"]
        values = []
        for field, size, field_type in protocol["fields"]:
            value = kwargs.get(field, b"\x00" * size if field_type == "s" else 0)
            if field_type == "s":  # 字串處理
                value = value.encode("utf-8").ljust(size, b"\x00")[:size]  # 把後續的空字串補為 \0, 否則c++ server無法解析正確資訊
            elif field_type in ("I", "Q", "B", "H"):  # 整數、浮點數處理
                if not isinstance(value, (int, float)):
                    raise ValueError(f"Field '{field}' must be of type {field_type}.")
            values.append(value)

        # print(f"DEBUG - format_string: {format_string}")
        # print(f"DEBUG - values: {[repr(v) for v in values]}")

        try:
            return struct.pack(format_string, *values)
        except struct.error as e:
            raise ValueError(f"Error packing data with format '{format_string}': {e}")

    # HACK: 新增解析不定長度的封包資料, 用於解析 settle_resp 協議 20250314
    def unpack_data(self, protocol_name, data):
        """
        根據協議名稱解包封包數據
        參數:
        - protocol_name (str): 協議名稱。
        - data (bytes): 封包數據。 傳入的封包資料預期已經切割掉header的部分(12 bytes), 只剩下封包資料本體

        返回:
        - dict: 解包後的封包數據。
        """
        protocol = self.PROTOCOLS[protocol_name]

        if protocol_name in PROTOCOL_DESCRIPTORS:
            try:
                descriptor = PROTOCOL_DESCRIPTORS[protocol_name]
                return descriptor.parse(data)
            except Exception as e:
                # 如果描述器解析失敗，嘗試使用傳統方式
                logger.error(f"Error parsing protocol {protocol_name} with descriptor: {e}")
                
        # 一般協議處理
        format_string = protocol["format"]
        if len(data) < struct.calcsize(format_string):
            raise ValueError(f"Data size {len(data)} is too small for format '{format_string}'")
        
        unpacked_data = struct.unpack(format_string, data)
        result = {}
        # 遊歷所有fields, 並將解析後的資料放入result dict
        # unpacked_data是一個tuple, 內容是解析後的資料
        # 最後的dict結構為: {field: value}
        for (field, size, field_type), value in zip(protocol["fields"], unpacked_data):
            if field_type == "s":   # 針對解析出來的字串做處理, 去掉前後的空白字元
                value = value.decode("utf-8").strip()
            result[field] = value
        return result
    
    # 新增封包處理相關方法
    async def start_processor(self):
        """啟動封包處理器"""

        try:
            # 設置運行狀態
            self.running = True
            # 創建處理器任務
            self.processor_task = asyncio.create_task(self._process_packets())
            logger.info("Success: Packet processor started")

            # 檢查處理器任務狀態
            if self.processor_task.done():
                logger.error("Error: Processor task ended immediately")
                return False

            # 添加清理任務
            self.cleanup_task = asyncio.create_task(self._periodic_cleanup())

            return True
        

        except Exception as e:
            logger.error(f"Error: Failed to start processor - {str(e)}")
            self.running = False
            return False

    # HACK: 嘗試處理event loop binding問題 20250307
    async def stop_processor(self):
        """停止封包處理器並清理資源"""
        self.running = False
        
        tasks_to_cancel = []
        if hasattr(self, 'processor_task') and self.processor_task:
            tasks_to_cancel.append(self.processor_task)
        
        if hasattr(self, 'cleanup_task') and self.cleanup_task:
            tasks_to_cancel.append(self.cleanup_task)
        
        # 取消所有任務
        for task in tasks_to_cancel:
            if not task.done():
                task.cancel()
        
        # 等待所有任務完成
        if tasks_to_cancel:
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
        
        # 清理隊列引用
        self.cmd_queues.clear()
        self._loop_queues.clear()
        
        self.processor_task = None
        self.cleanup_task = None
        logger.info("Packet processor stopped and resources cleaned up")

    # HACK: 嘗試處理event loop binding問題 20250307
    async def _process_packets(self):
        """持續處理接收到的封包"""
        while self.running:
            try:
                # 檢查 WebSocket client
                if not self.ws_client:
                    logger.error("WebSocket client not initialized")
                    self.running = False
                    break

                # 確認 WebSocket 連線狀態
                if not hasattr(self.ws_client, 'websocket') or not self.ws_client.websocket:
                    logger.error("WebSocket connection not established")
                    self.running = False
                    break
                
                # 1. 接收原始資料
                raw_data = await self.ws_client.recv_raw()
                if not raw_data:
                    continue
                
                # 2. 解析所有協議 (使用指針移動方式)
                current_position = 0
                while current_position < len(raw_data):
                    # 2.1 解析標頭 檢查是否有足夠的資料解析header
                    if current_position + self.HEADER_SIZE > len(raw_data):
                        break # 等待更多資料

                    # 這邊用slicing語法, 直接切割出整個raw data的前12 bytes(header)
                    # slicing 語法: [start:stop:step]
                    # start: 起始位置, stop: 結束位置, step: 步長
                    # 如果 start 為空, 則默認為 0
                    # 如果 stop 為空, 則默認為最後一個元素
                    # 如果 step 為空, 則默認為 1
                    header = self.unpack_header(raw_data[current_position:current_position + self.HEADER_SIZE])
                    cmd, size, seq = header
                    # 減少debug log數量, 暫時註解掉
                    # log_and_print(f"Header parsed - CMD: {hex(cmd)}, Size: {size}, Seq: {seq}", 
                    #             level=logging.DEBUG)

                    # 2.2 取得當前協議的內容
                    body_start = current_position + self.HEADER_SIZE    # header結束位置, 實際封包資料起始點
                    body_end = current_position + size                  # 封包資料結束位置, 透過解析header得到的協議size取得
                    # 假如封包資料結束的位置大於raw data的長度, 則跳出迴圈
                    if body_end > len(raw_data):
                        break

                    # 再次slicing一次, 取得該協議對應的封包本體內容    
                    body = raw_data[body_start:body_end]

                    # 2.3 尋找對應協議並解析
                    parsed_data = None
                    for protocol_name, protocol in self.PROTOCOLS.items():  # 遊歷所有protocol, 取出protocol_name和其對應內容
                        if protocol['cmd'] == cmd:
                            # log_and_print(f"SKIP_CMD type : {type(SKIP_PARSE_CMD)}", level=logging.DEBUG)

                            # 如果該協議在SKIP_PARSE_CMD中, 則跳過解析, 原先預期把心跳包放進去, 但因為資料型態轉換上碰到一點問題, 所以只放0x030005下注協議
                            # 0x030005下注協議有點奇怪, 看起來實作時模擬的client端仍會收到這個協議, 其實預期應該是不會收到
                            if protocol['cmd'] in SKIP_PARSE_CMD:
                                logger.debug(f"Skipping parsing for CMD: {hex(cmd)}")
                                continue
                            try:
                                body_data = self.unpack_data(protocol_name, body)
                                parsed_data = {
                                    'cmd': hex(cmd),
                                    'size': size,
                                    'seq': seq,
                                    'protocol': protocol_name,
                                    'data': body_data
                                }
                                # 減少debug log數量, 暫時註解掉
                                # logger.debug(f"Parsed protocol: {protocol_name}, CMD: {hex(cmd)}")
                                # logger.debug(f"Parsed data: {parsed_data}")
                                break
                            except Exception as e:
                                logger.warning(f"Failed to parse protocol {protocol_name}: {e}")
                                continue

                    # 2.4 如果有對應的佇列，放入解析結果
                    # logger.debug(f"Queues: {self.cmd_queues}")
                    if hex(cmd) in self.cmd_queues:
                        # logger.debug (f"cmd: {cmd}")
                        # 減少debug log數量, 暫時註解掉
                        # logger.debug (f"put hex(cmd) in self.cmd_queues: {hex(cmd)}")
                        # logger.debug (f"self.cmd_queues: {self.cmd_queues}")

                        # 向所有循環的隊列發送數據
                        data_to_queue = parsed_data or {
                            'cmd': hex(cmd),
                            'size': size,
                            'seq': seq,
                            'raw_body': body_data
                        }

                        # # 打印實際分發前的數據
                        # logger.debug(f"Preparing to dispatch data for CMD: {hex(cmd)}")
                        # logger.debug(f"Current loops: {list(self._loop_queues.keys())}")
    
                        # # 打印每個循環的隊列情況
                        # for loop_id, loop_queues in self._loop_queues.items():
                        #     logger.debug(f"Loop {loop_id} has commands: {list(loop_queues.keys())}")

                        dispatch_count = 0
                        for loop_id, loop_queues in self._loop_queues.items():
                            if hex(cmd) in loop_queues:
                                try:
                                    await loop_queues[hex(cmd)].put(data_to_queue)
                                    dispatch_count += 1
                                except Exception as e:
                                    logger.warning(f"Failed to dispatch to loop {loop_id}: {e}")
                        
                        if dispatch_count > 0:
                            logger.debug(f"Dispatched data for CMD: {hex(cmd)} to {dispatch_count} loops")
                        else:
                            logger.warning(f"No active loops for CMD: {hex(cmd)}")

                    # 2.5 移動到下一個協議
                    current_position += size
                    # 減少debug log數量, 暫時註解掉
                    # log_and_print(f"Moving to next protocol position: {current_position}", 
                    #             level=logging.DEBUG)

            except Exception as e:
                logger.error(f"Packet processing error: {str(e)}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                await asyncio.sleep(1)

    # HACK: 嘗試處理event loop binding問題, 待觀察是否有其他問題 20250307
    async def _periodic_cleanup(self):
        """定期清理未使用的循環隊列"""
        while self.running:
            try:
                await asyncio.sleep(300)  # 每5分鐘執行一次
                
                # 獲取當前循環ID
                try:
                    current_loop = asyncio.get_running_loop()
                    current_id = id(current_loop)
                except RuntimeError:
                    continue  # 不在事件循環中
                
                # 清理不再使用的循環
                removed_loops = []
                for loop_id in list(self._loop_queues.keys()):
                    if loop_id != current_id:
                        try:
                            # 檢查循環是否仍在運行
                            is_active = False
                            for cmd, queue in self._loop_queues[loop_id].items():
                                if not queue.empty():
                                    is_active = True
                                    break
                            
                            if not is_active:
                                del self._loop_queues[loop_id]
                                removed_loops.append(loop_id)
                        except Exception:
                            pass
                
                if removed_loops:
                    logger.info(f"Cleaned up {len(removed_loops)} unused loop queues")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")

    async def register_handler(self, cmd):
        """註冊一個命令處理器，返回與當前循環綁定的隊列"""
        # HACK: 嘗試修復當前event loop綁定問題 20250307
        current_loop = asyncio.get_running_loop()
        loop_id = id(current_loop)
        # 減少debug log數量, 暫時註解掉
        logger.debug(f"Register handler for cmd {cmd} on loop {loop_id}")
        
        # 初始化此循環的字典
        if loop_id not in self._loop_queues:
            self._loop_queues[loop_id] = {}
        
        # 為這個循環創建命令隊列
        if cmd not in self._loop_queues[loop_id]:
            self._loop_queues[loop_id][cmd] = asyncio.Queue()
            
        # 向後兼容
        self.cmd_queues[cmd] = self._loop_queues[loop_id][cmd]

        # 減少debug log數量, 暫時註解掉
        # log_and_print(f"self.cmd_queues: {self.cmd_queues}", level=logging.DEBUG)
        
        return self._loop_queues[loop_id][cmd]

    async def wait_for_response(self, cmd, timeout=30):
        """等待特定指令的回應
        
        Args:
            cmd: 指令碼
            timeout: 超時時間(秒)
            
        Returns:
            dict or None: 回應封包或超時返回None
        """
        queue = await self.register_handler((cmd))
        
        try:
            response = await asyncio.wait_for(queue.get(), timeout)
            if 'data' in response:
                logger.debug(f"Received parsed data for CMD: {cmd}")
                return response['data']
            return response
        except asyncio.TimeoutError:
            logger.error(f"Response timeout: cmd={hex(cmd)}")
            return None
    
    # 解析不定長度的數據字段 (目前用於 settle_resp 協議的 data 字段)
    def unpack_variable_data(self, data, offset=53, count=0):   # 前面固定資料長度應該都是53 bytes, 所以直接給offset default值
        """解析變長數據字段，用於 settle_resp 協議的 data 字段
        Args:
            data (bytes): 封包數據。
            offset (int): 起始解析位置, 預設為53 bytes, 因為前面固定資料長度應該都是53 bytes, 4s14sI30sB(4+14+4+30+1=53 bytes)
            count (int): 玩法筆數, 用於決定要解析多少組資料
        
        每條詳細信息包含:
        - playtype (1 byte): 玩法類型, unit8
        - winlose (30 bytes): 輸贏金額, 30 bytes string
        """
        results = []            # 存放解析結果
        current_offset = offset # 起始解析位置
        
        # 透過迴圈解析每一組玩法+輸贏資料, count是玩法筆數
        for _ in range(count):
            if current_offset + 31 > len(data):  # 1 + 30 = 31 bytes per item, 一組玩法+輸贏資料長度固定為31 bytes
                logger.warning(f"Data truncated, expected more items but reached end of data")
                break
                
            # 解析玩法 playtype (1 byte)
            # 未指定unpack長度, 則預設為1 byte
            playtype = struct.unpack(">B", data[current_offset:current_offset+1])[0]    # slicing語法, 往後取得1 byte為playtype
            current_offset += 1
            
            # 解析玩家輸贏 winlose (30 bytes)
            # 長度是30 bytes, 所以這邊指定unpack長度為30 bytes >>> ">30s"
            winlose = struct.unpack(">30s", data[current_offset:current_offset+30])[0]  # slicing語法, 再往後取得30 bytes為winlose
            current_offset += 30
            # 這邊unpack的資料型態是 bytes string, 需要轉換成 float
            # decode("utf-8") 會將 bytes string 轉換成 utf-8 string
            # strip() 會移除字串前後的空白字元, 這邊是移除\x00
            # 最後再轉換成 float, 才是實際玩家輸贏
            winlose_str = winlose.decode("utf-8").strip("\x00")
            winlose_value = float(winlose_str)
            
            results.append({"playtype": playtype, "winlose": winlose_value})    # 將每一輪迴圈解包結果append到results list
        
        return results