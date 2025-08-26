# Sensitive Information, 以下協議格式已經處理, 為了展示範例, 內容並非真實協議

import struct

from protocols.generate_protocol_format import generate_format_string

# 定義header格式
HEADER_FORMAT = ">III"  # cmd (4 bytes), size (4 bytes), seq (4 bytes)
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

# 封包協議格式
"""
Ref. https://docs.python.org/3.13/library/struct.html
Ref2. https://docs.python.org/zh-tw/3.8/library/struct.html
協議定義要跟core team確認，確保每個協議的格式都是正確的
每個參數有三個值，分別是參數名稱、大小和類型。
C Type         Standard Size (bytes)            Python Type              
char            實際大小看文件確認                 's' (string)             
uint8_t            1                            'B' (unsigned char)      
uint16_t           2                            'H' (unsigned short)     
uint32_t           4                            'I' (unsigned int)       
uint64_t           8                            'Q' (unsigned long long)
float              4                            'f' (float)(應該是沒有這個型態)
double             8                            'd' (double)
"""
# 演示用協議定義 - 展示常見的網路遊戲協議模式
DEMO_PROTOCOLS = {
    # 演示：認證協議
    "auth_request": {
        "cmd": 0x100001,
        "fields": [
            ("username", 64, "s"),
            ("password_hash", 64, "s"),
            ("client_version", 4, "I"),
            ("device_info", 32, "s"),
        ],
    },
    
    "auth_response": {
        "cmd": 0x200001,
        "fields": [
            ("status", 4, "I"),
            ("session_token", 128, "s"),
            ("server_time", 8, "Q"),
        ],
    },
    
    # 演示：心跳協議
    "heartbeat": {
        "cmd": 0x000001,
        "fields": []
    },
    
    # 演示：加密協議
    "encryption_setup": {
        "cmd": 0x000003,
        "fields": [
            ("encryption_type", 2, "H"),
            ("key_seed", 8, "Q"),
            ("iv_seed", 8, "Q"),
        ]
    },
    
    # 演示：遊戲房間協議
    "join_room_request": {
        "cmd": 0x100010,
        "fields": [
            ("room_id", 4, "I"),
            ("player_data", 256, "s"),
        ]
    },
    
    "join_room_response": {
        "cmd": 0x200010,
        "fields": [
            ("status", 4, "I"),
            ("room_info", 512, "s"),
            ("player_count", 4, "I"),
        ]
    },
    
    # 演示：遊戲狀態協議
    "game_state_update": {
        "cmd": 0x200020,
        "fields": [
            ("room_id", 4, "I"),
            ("game_phase", 1, "B"),
            ("round_id", 8, "Q"),
            ("state_data", 0, "s"),  # 變長度 JSON 數據
        ]
    },
    
    # 演示：玩家操作協議
    "player_action": {
        "cmd": 0x100030,
        "fields": [
            ("action_type", 2, "H"),
            ("action_data", 128, "s"),
            ("timestamp", 8, "Q"),
        ]
    },
    
    "action_result": {
        "cmd": 0x200030,
        "fields": [
            ("status", 4, "I"),
            ("result_data", 256, "s"),
        ]
    },
    
    # 演示：遊戲結果協議
    "game_result": {
        "cmd": 0x200040,
        "fields": [
            ("round_id", 8, "Q"),
            ("winner_info", 64, "s"),
            ("result_details", 0, "s"),  # 變長度結果數據
        ]
    },
    
    # 演示：餘額更新協議
    "balance_update": {
        "cmd": 0x200050,
        "fields": [
            ("player_id", 8, "Q"),
            ("new_balance", 30, "s"),  # 使用字串避免精度問題
            ("transaction_id", 8, "Q"),
        ]
    },
}


# 為每個協議生成格式字串
for protocol in PROTOCOLS.values():
    protocol["format"] = generate_format_string(protocol["fields"])
