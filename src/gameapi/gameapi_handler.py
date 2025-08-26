import json
import uuid

import requests as rq

from utils.config_manager import ConfigManager
from utils.encryption import sha256_encrypt
from utils.logger import logger
from utils.random_string import generate_random_string


class GAMEAPI_Connection():
    """
    連接GameApi, 並發送登入請求
    Args:
        player_id (str): 指定要使用的玩家資訊
        seamless (bool): 發何種錢包類型的gameapi請求
            True: 發單一錢包的GameApi登入請求
            False: 發轉帳錢包的GameApi登入請求
        currency (str): 幣別代碼，如 "JPY", "USD", "CNY"，None 表示使用當前設置的幣別
    """

    def __init__(self, player_id="player", seamless=False, currency="JPY"):
        self.config_manager = ConfigManager()
        # config_data = self.config_manager.load_config(currency)
        
        # 從配置中獲取 gameapi 相關信息
        game_config = self.config_manager.load_file("config.yaml")
        self.gameapi_url = game_config["gameapi"]["domain"]
        
        # 獲取玩家資訊
        player_info = self.config_manager.get_player_info(player_id)
        if not player_info or player_id not in player_info:
            raise ValueError(f"Player info not found for player_id: {player_id}")
        
        player_data = player_info[player_id]
        self.headers = {"Content-Type": "application/json"}
        # 這邊要轉成實例變數, 這樣才能在其他function中使用
        self.seamless = seamless
        self.player_id = player_id
        self.username = player_data["username"]
        self.pid = player_data["pid"]
        self.key = player_data["key"]

    def send_request(self):
        """發送gameapi login請求"""
        # 單一錢包
        if self.seamless == True:
            self.update_vendorapi_credit()
            full_url = self.gameapi_url + "/api/v2/seamless/user-login"
            data = {
                "uuid": str(uuid.uuid4()),
                "username": self.username,
                "platform-id": self.pid,
                "key": sha256_encrypt(self.username, self.key),
            }
            logger.info(f"[Player Info] - pid: {self.pid}, username: {self.username}")
        # 轉帳錢包
        elif self.seamless == False:
            full_url = self.gameapi_url + "/api/v2/user-login"
            credit = "100000000"
            transaction_id = generate_random_string()
            data = {
                "credit": credit,
                "key": sha256_encrypt(self.username, credit, transaction_id, self.key),
                "uuid": str(uuid.uuid4()),
                "platform-id": self.pid,
                "username": self.username,
                "transaction-id": transaction_id,
            }
            logger.info(f"[Player Info] - pid: {self.pid}, username: {self.username}")
        else:
            raise Exception(f"Invalid single_wallet value: {self.seamless}")

        json_data = json.dumps(data)
        response = rq.post(full_url, headers=self.headers, data=json_data)
        # 使用 raise_for_status 檢查請求的狀態碼
        try:
            response.raise_for_status()
        except rq.exceptions.HTTPError as e:
            raise Exception(
                f"Request failed with status code {response.status_code}: {response.text}"
            ) from e

        response_json = response.json()
        error_code = response_json["error"]["code"]
        response_message = response_json["error"]["msg"]
        # 添加對gameapi非預期response的處理
        if error_code == 0:
            gameapi_token = response_json["redirect-url"].split("token=")[1]
            logger.debug(f"gameapi_token: {gameapi_token}")
            return gameapi_token
        elif error_code == 41:
            logger.error(f"Wrong wallet type, error code: {error_code} message: {response_message}")
            # HACK: 比較髒的做法, 直接return 41, 讓外層可以接到, 並判斷登入錯誤是因為錢包類型錯誤
            return 41
        else:
            logger.error(f"Error occurred during GameApi process, error code: {error_code} message: {response_message}")
            # raise Exception()

    def update_vendorapi_credit(self):
        """
        Call VendorApi, 更新callback key, 同時給予玩家100000000額度
        """
        # 使用 ConfigManager 獲取 VendorApi 信息
        game_config = self.config_manager.load_file("config.yaml")
        vendorapi_url = game_config["gameapi"]["vendorapi_domain"]
        
        # 獲取玩家 callback_key
        player_data = self.config_manager.get_player_info(self.player_id)[self.player_id]
        callback_key = player_data["callback_key"]
        
        req_url = f"{vendorapi_url}/update-credit"
        data = {
            "name": self.pid + self.username,
            "credit": "100000000",
            "pid": self.pid,
            "key": callback_key,
        }
        resp = rq.get(req_url, data)
        try:
            resp.raise_for_status()
        except rq.exceptions.HTTPError as e:
            raise Exception(
                f"Vendorapi request failed with status code {resp.status_code}: {resp.text}"
            ) from e
        update_key_resp = json.loads(resp.content)
        resp_code = update_key_resp["code"]
        if resp_code == 0:
            logger.info(f"Vendor updated successfully")
            logger.debug(f"Player current balance: ${update_key_resp['credit']}")
            return True
        else:
            raise ValueError(f"Failed to update vendorapi, Response: {update_key_resp}")
