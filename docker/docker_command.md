# docker build command
```bash
docker build -f ./docker/Dockerfile -t wt-game-automation:$(date +%Y%m%d) .
```

# docker run command
```bash
docker run --rm \
  -v /etc/localtime:/etc/localtime:ro \
  -v $(pwd)/logs:/app/reports/logs:rw \
  --name jt-test \
  wt-game-automation \
  -v --player-id=rel_usd_trans_player -m "bac_balancecheck"
```

# run_test.sh
```bash
# 使用預設容器名稱
./run_test.sh

# 使用 -n 選項指定容器名稱
./run_test.sh -n my-custom-container

# 完整指定所有參數
./run_test.sh --name test-container-001 rel_usd_trans_player bac_bet

# 位置參數方式指定容器名稱
./run_test.sh rel_usd_trans_player bac_bet my-container

# 進入指定名稱的容器 shell
./run_test.sh --shell --name debug-container
```