import asyncio
from user.enter_table import enter_table
from gateserver.gateserver_handler import GateServerHandler
from utils.logger import logger
from heartbeat.heartbeat import start_heartbeat
from game.bet import BetInfo, place_bet, set_nocomm_switch, set_duobao_switch
from game.settle import recv_settle_resp
from user.balance import fetch_player_balance, receive_balance_update
from src.utils.balance_checker import BalanceChecker
from game.playtype_enums import BacPlayType, DtbPlayType
from game.get_result import recv_game_result
from game.payout.payout_verifier import PayoutVerifier

async def main():
    # 初始化 GateServer Handler
    gate_connection = GateServerHandler()
    # heartbeat_handler = None

    try:
        # 嘗試登入 Gate Server
        player_id = "rel_usd_trans_player"
        seamless = False
        currency = "USD"
        gate_connection_result, player_balance = await gate_connection.gate_server_connection(player_id=player_id, seamless=seamless, currency=currency)
        if gate_connection_result:
            balance_checker = BalanceChecker(gate_connection)
            await balance_checker.initialize(player_balance)

            heartbeat_task = asyncio.create_task(start_heartbeat(gate_connection))

            try:
                # await asyncio.sleep(1)
                if await enter_table(gate_connection, "DT99"):
                    while True:
                        betinfos = [
                            # BetInfo(play_type=BacPlayType.BANKER, credit=1000),
                            # BetInfo(play_type=BacPlayType.BANKER_NOCOMMISSION, credit=1000),
                            # BetInfo(play_type=BacPlayType.PLAYER, credit=1000),
                            # BetInfo(play_type=BacPlayType.PLAYER_PAIR, credit=1000),
                            # BetInfo(play_type=BacPlayType.BANKER_PAIR, credit=1000),
                            # BetInfo(play_type=BacPlayType.LUCKY6, credit=1000),
                            # BetInfo(play_type=BacPlayType.LUCKY6_2, credit=1000),
                            # BetInfo(play_type=BacPlayType.LUCKY6_3, credit=300),
                            # BetInfo(play_type=BacPlayType.LUCKY7, credit=300),
                            # BetInfo(play_type=BacPlayType.SUPER_LUCKY7, credit=300),
                            # BetInfo(play_type=BacPlayType.DUO_BAO, credit=300),
                            # BetInfo(play_type=BacPlayType.BANKER_DRAGON_BONUS, credit=500),
                            # BetInfo(play_type=BacPlayType.PLAYER_DRAGON_BONUS, credit=500),
                            BetInfo(play_type=DtbPlayType.TIGER, credit=2000),
                        ]

                        bet_result = await place_bet(gate_connection, betinfos, "DTB", "DT99")
                        if bet_result["result"] is True:
                            logger.info("Bet successfully")
                            balanced, message = await balance_checker.check_after_bet(2000)
                            if balanced is True:
                                print("Balance check passed")
                            else:
                                logger.error(f"Balance check failed: {message}")

                            try:
                                # 同時等待遊戲結果和結算回應, timeout 設定為 30 秒
                                result = await asyncio.wait_for(
                                    asyncio.gather(
                                        recv_game_result(gate_connection, "DT99", bet_result["bet_resp_gmcode"]),
                                        recv_settle_resp(gate_connection, "DT99", True),
                                        return_exceptions=True  # 即便其中一個失敗也繼續
                                    ),
                                    timeout=30  # 設定一個合理的超時時間
                                )
                                game_result_data, settle_result_data = result

                                # 初始化變量
                                game_result = None
                                settle_success = False
                                win_lose = None

                                # 處理遊戲結果
                                if isinstance(game_result_data, tuple) and not isinstance(game_result_data, Exception):
                                    received, game_result = game_result_data
                                    if received:
                                        # print(f"Game result received: {game_result}")
                                        pass
                                    else:
                                        logger.error("Failed to receive game result")
                                else:
                                    logger.error(f"Game result error:: {game_result_data}")

                                # 處理結算回應
                                if isinstance(settle_result_data, tuple) and not isinstance(settle_result_data, Exception):
                                    settle_success, settle_data = settle_result_data
                                    if settle_success and settle_data is not None:
                                        # print(f"Settle Succeeded: {settle_success} Settle response received: {settle_data}")
                                        pass
                                    else:
                                        logger.error("Failed to receive settle response")
                                else:
                                    logger.error(f"Settle response error: {settle_result_data}")

                                # 只有兩個協議都成功收到後才進行後續處理
                                if game_result and settle_success:
                                    logger.info("Both game result and settle response received successfully")

                                    # 驗證賠率
                                    try:
                                        verify_result, verify_detail = await PayoutVerifier.verify_game_payout("dtb", game_result, betinfos, settle_data)
                                        print(f"Verify payout result: {verify_result}\nDetail: {verify_detail}")
                                        if verify_result is True:
                                            print("Payout verification passed")
                                        else:
                                            logger.error(f"Payout verification failed: {verify_detail}")
                                            
                                    except Exception as e:
                                        logger.error(f"Error during payout verification: {e}")
                                else:
                                    logger.error("Either game result or settle response was not received successfully")

                            except asyncio.TimeoutError:
                                logger.error("Timeout while waiting for game result or settle response")
                            except Exception as e:
                                logger.error(f"Error during game result or settle response: {e}")                        
                        else:
                            logger.error("Place bet failed")

            except Exception as e:
                logger.error(f"User operation error: {e}")
            finally:
                if heartbeat_task and not heartbeat_task.done():
                    heartbeat_task.cancel()
                    await asyncio.gather(heartbeat_task, return_exceptions=True)

    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        if hasattr(gate_connection, 'packet_handler'):
            await gate_connection.packet_handler.stop_processor()
        await gate_connection.close()
    
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program terminated by user")
    except Exception as e:
        logger.error(f"Program terminated with error: {e}")