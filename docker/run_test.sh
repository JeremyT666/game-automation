#!/bin/bash
# filepath: /game-automation/docker/run_test.sh

set -e  # 遇到錯誤立即停止

# =============================================================================
# Game Automation Test Runner
# =============================================================================

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 配置變數
IMAGE_NAME="game-automation"
DOCKERFILE_PATH="./Dockerfile"          # 相對於docker路徑
BUILD_CONTEXT="../"                     # 專案根目錄作為構建上下文
DEFAULT_PLAYER_ID="rel_usd_trans_player"
DEFAULT_TEST_MARKER="bac_balancecheck"
DEFAULT_CONTAINER_NAME="jt-autotest-runner"

# =============================================================================
# 函數定義
# =============================================================================

# 顯示橫幅
show_banner() {
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║                 Game Automation Runner                     ║"
    echo "║                      Docker Version                       ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# 顯示使用說明
show_usage() {
    show_banner
    echo -e "${CYAN}使用方式:${NC}"
    echo "  $0 [選項] [PLAYER_ID] [TEST_MARKER] [CONTAINER_NAME]"
    echo ""
    echo -e "${CYAN}選項:${NC}"
    echo "  -h, --help          顯示此說明"
    echo "  -b, --build         強制重新構建映像"
    echo "  -c, --clean         執行前清理舊容器"
    echo "  -l, --logs          顯示日誌目錄內容"
    echo "  -s, --shell         進入容器 shell"
    echo "  -n, --name          指定容器名稱"
    echo ""
    echo -e "${CYAN}參數:${NC}"
    echo "  PLAYER_ID           玩家ID (預設: $DEFAULT_PLAYER_ID)"
    echo "  TEST_MARKER         測試標記 (預設: $DEFAULT_TEST_MARKER)"
    echo "  CONTAINER_NAME      容器名稱 (預設: $DEFAULT_CONTAINER_NAME)"
    echo ""
    echo -e "${CYAN}可用的測試標記 (Pytest Markers):${NC}"
    echo "  • login             - 登入功能測試 (2 cases)"
    echo "  • table             - 進桌功能測試 (52 cases)"
    echo "  • bac_bet           - 百家樂投注測試 (2,496 cases, 包含 bac_balancecheck)"
    echo "  • bac_balancecheck  - 百家樂餘額檢查 (718 cases)"
    echo "  • bac_odds          - 百家樂賠率驗證 (14 cases, 涵蓋所有玩法的輸贏情境)"
    echo "  • dtb_bet           - 龍虎投注測試 (928 cases, 包含 dtb_balancecheck)"
    echo "  • dtb_balancecheck  - 龍虎餘額檢查 (232 cases)"
    echo "  • dtb_odds          - 龍虎賠率驗證 (11 cases, 涵蓋所有玩法的輸贏情境)"
    echo "  • single_table      - 單桌測試 (2,474 cases, 包含所有遊戲類型投注標記)"
    echo ""
    echo -e "${CYAN}組合標記範例:${NC}"
    echo "  • \"login or table\"     - 執行登入和進桌測試"
    echo "  • \"bac_bet and not bac_balancecheck\" - 執行百家樂投注但排除餘額檢查"
    echo "  • \"bac_odds or dtb_odds\" - 執行所有賠率驗證測試"
    echo ""
    echo -e "${CYAN}使用範例:${NC}"
    echo "  $0                                              # 使用預設參數"
    echo "  $0 rel_usd_trans_player login                  # 執行登入測試"
    echo "  $0 rel_usd_trans_player \"login or table\"       # 執行多個標記"
    echo "  $0 rel_usd_trans_player bac_odds               # 執行百家樂賠率驗證"
    echo "  $0 rel_usd_trans_player \"bac_odds or dtb_odds\" # 執行所有賠率驗證"
    echo "  $0 -n my-test-container                         # 指定容器名稱"
    echo "  $0 --name custom-name player1 single_table     # 完整指定"
    echo "  $0 -b another_player dtb_bet my-container       # 重新構建並自訂名稱"
    echo "  $0 --logs                                       # 查看日誌"
    echo "  $0 --shell                                      # 進入容器調試"
    echo ""
    echo -e "${YELLOW}注意事項:${NC}"
    echo "  • 使用組合標記時請用引號包圍，例如: \"login or table\""
    echo "  • single_table 測試耗時較長，建議確保環境穩定"
    echo "  • odds 標記用於賠率驗證，涵蓋各種輸贏情境"
    echo "  • 某些測試需要特定的玩家ID，請確認帳號設定正確"
}

# 檢查依賴
check_dependencies() {
    # 檢查 Docker 是否安裝
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}錯誤: Docker 未安裝${NC}"
        echo "請先安裝 Docker: https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    # 檢查 Docker 是否運行
    if ! docker info >/dev/null 2>&1; then
        echo -e "${RED}錯誤: Docker 未運行${NC}"
        echo "請啟動 Docker 服務"
        exit 1
    fi
    
    echo -e "${GREEN}Docker 檢查通過${NC}"
}

# 檢查映像是否存在
check_image_exists() {
    if docker image inspect "$IMAGE_NAME:latest" >/dev/null 2>&1; then
        echo -e "${GREEN}映像 '$IMAGE_NAME:latest' 已存在${NC}"
        return 0
    else
        echo -e "${YELLOW}映像 '$IMAGE_NAME:latest' 不存在${NC}"
        return 1
    fi
}

# 構建映像
# 構建映像
build_image() {
    local current_date=$(date +%Y%m%d)
    local dated_image="$IMAGE_NAME:$current_date"
    local latest_image="$IMAGE_NAME:latest"
    
    echo -e "${YELLOW}構建 Docker 映像...${NC}"
    echo -e "${CYAN}日期標籤:${NC} $dated_image"
    echo -e "${CYAN}最新標籤:${NC} $latest_image"
    echo -e "${CYAN}建置上下文:${NC} $(realpath $BUILD_CONTEXT)"
    
    # 檢查 Dockerfile 是否存在
    if [[ ! -f "$DOCKERFILE_PATH" ]]; then
        echo -e "${RED}錯誤: 找不到 Dockerfile: $DOCKERFILE_PATH${NC}"
        exit 1
    fi
    
    # 檢查建置上下文是否存在
    if [[ ! -d "$BUILD_CONTEXT" ]]; then
        echo -e "${RED}錯誤: 建置上下文目錄不存在: $BUILD_CONTEXT${NC}"
        exit 1
    fi
    
    # 構建映像 (使用專案根目錄作為上下文)
    if docker build -f "$DOCKERFILE_PATH" -t "$dated_image" -t "$latest_image" "$BUILD_CONTEXT"; then
        echo -e "${GREEN}映像構建成功:${NC}"
        echo -e "${GREEN}  • $dated_image${NC}"
        echo -e "${GREEN}  • $latest_image${NC}"
    else
        echo -e "${RED}映像構建失敗${NC}"
        exit 1
    fi
}

# 檢查並構建映像
check_and_build_image() {
    local force_build=$1
    
    if [[ "$force_build" == "true" ]]; then
        echo -e "${YELLOW}強制重新構建映像...${NC}"
        build_image
    else
        if ! check_image_exists; then
            echo -e "${YELLOW}映像不存在，開始構建...${NC}"
            build_image
        else
            echo -e "${GREEN}使用現有映像，跳過構建${NC}"
        fi
    fi
}

# 準備環境
prepare_environment() {
    echo -e "${YELLOW}準備執行環境...${NC}"
    
    # 創建 logs 目錄
    if mkdir -p logs; then
        echo -e "${GREEN}日誌目錄已準備: $(pwd)/logs${NC}"
    else
        echo -e "${RED}無法創建日誌目錄${NC}"
        exit 1
    fi
}

# 清理舊容器
clean_containers() {
    echo -e "${YELLOW}清理舊容器...${NC}"
    
    # 停止並刪除名稱包含 jt-autotest 的容器
    local containers=$(docker ps -a --filter "name=jt-autotest" --format "{{.Names}}" 2>/dev/null | head -10)
    
    if [[ -n "$containers" ]]; then
        echo "發現舊容器，正在清理..."
        echo "$containers" | xargs docker rm -f 2>/dev/null || true
        echo -e "${GREEN}舊容器已清理${NC}"
    else
        echo -e "${GREEN}沒有需要清理的容器${NC}"
    fi
}

# 執行測試
run_test() {
    local player_id="$1"
    local test_marker="$2"
    local container_name="$3"
    local timestamp=$(date +%Y%m%d-%H%M%S)
    
    echo -e "${PURPLE}════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}開始執行測試${NC}"
    echo -e "${CYAN}Player ID:${NC} $player_id"
    echo -e "${CYAN}Test Marker:${NC} $test_marker"
    echo -e "${CYAN}Container Name:${NC} $container_name"
    echo -e "${CYAN}Timestamp:${NC} $timestamp"
    echo -e "${PURPLE}════════════════════════════════════════════${NC}"
    
    # 執行 Docker 容器 (使用 latest 標籤)
    if docker run --rm \
        -v /etc/localtime:/etc/localtime:ro \
        -v "$(pwd)/logs:/app/reports/logs:rw" \
        --name "$container_name" \
        -e TZ=Asia/Taipei \
        -e PYTHONUNBUFFERED=1 \
        "$IMAGE_NAME:latest" \
        -v --player-id="$player_id" -m "$test_marker"; then
        
        echo -e "${GREEN}測試執行完成！${NC}"
        echo -e "${CYAN}日誌已保存到: $(pwd)/logs${NC}"
        
        # 顯示最新的日誌檔案
        if [[ -d "logs" ]] && [[ "$(ls -A logs 2>/dev/null)" ]]; then
            echo -e "${YELLOW}最新日誌檔案:${NC}"
            ls -lt logs/ | head -3
        fi
    else
        echo -e "${RED}測試執行失敗${NC}"
        echo -e "${YELLOW}建議檢查:${NC}"
        echo "   1. 網路連線是否正常"
        echo "   2. 玩家ID是否正確"
        echo "   3. 測試標記是否有效"
        echo "   4. 查看容器日誌: docker logs $container_name"
        exit 1
    fi
}

# 進入容器 shell
enter_shell() {
    local container_name="$1"
    
    echo -e "${YELLOW}進入容器 shell...${NC}"
    echo -e "${CYAN}Container Name:${NC} $container_name"
    echo "在容器內可以執行："
    echo "  • ls -la /app/reports/logs"
    echo "  • pytest --help"
    echo "  • python -m pytest -v --collect-only"
    echo "  • python -m pytest -v -m \"login\" --collect-only"
    echo "  • python -m pytest -v -m \"bac_odds\" --collect-only"
    echo "  • python -m pytest --markers  # 查看所有可用標記"
    echo "輸入 'exit' 離開容器"
    echo ""
    
    docker run --rm -it \
        -v /etc/localtime:/etc/localtime:ro \
        -v "$(pwd)/logs:/app/reports/logs:rw" \
        --name "$container_name" \
        -e TZ=Asia/Taipei \
        -e PYTHONUNBUFFERED=1 \
        "$IMAGE_NAME:latest" \
        /bin/bash
}

# 顯示日誌
show_logs() {
    echo -e "${BLUE}日誌目錄內容${NC}"
    echo -e "${PURPLE}════════════════════════════════════════════${NC}"
    
    if [[ -d "logs" ]]; then
        if [[ "$(ls -A logs 2>/dev/null)" ]]; then
            echo -e "${CYAN}目錄位置:${NC} $(pwd)/logs"
            echo -e "${CYAN}檔案數量:${NC} $(ls logs | wc -l)"
            echo ""
            echo -e "${YELLOW}檔案列表:${NC}"
            ls -lah logs/
            echo ""
            
            # 顯示最新的日誌檔案內容預覽
            local latest_log=$(ls -t logs/*.log 2>/dev/null | head -1)
            if [[ -n "$latest_log" ]]; then
                echo -e "${YELLOW}最新日誌預覽 ($latest_log):${NC}"
                echo -e "${PURPLE}────────────────────────────────────────────${NC}"
                tail -10 "$latest_log" 2>/dev/null || echo "無法讀取檔案內容"
                echo -e "${PURPLE}────────────────────────────────────────────${NC}"
            fi
        else
            echo -e "${YELLOW}WARNING: 日誌目錄為空${NC}"
            echo "執行測試後會在此目錄生成日誌檔案"
        fi
    else
        echo -e "${YELLOW}WARNING: 日誌目錄不存在${NC}"
        echo "執行測試時會自動創建"
    fi
}

# 驗證參數
validate_parameters() {
    local player_id="$1"
    local test_marker="$2"
    
    # 檢查 player_id 是否為空
    if [[ -z "$player_id" ]]; then
        echo -e "${RED}錯誤: Player ID 不能為空${NC}"
        return 1
    fi
    
    # 檢查 test_marker 是否為有效值 (支援組合標記)
    local valid_markers=("login" "table" "bac_bet" "bac_balancecheck" "bac_odds" "dtb_bet" "dtb_balancecheck" "dtb_odds" "single_table")
    
    # 如果包含邏輯運算子，則跳過詳細驗證 (交給 pytest 處理)
    if [[ "$test_marker" =~ (or|and|not|\(|\)) ]]; then
        echo -e "${YELLOW}檢測到組合標記，將由 pytest 進行驗證${NC}"
        return 0
    fi
    
    # 檢查單一標記是否有效
    local is_valid=false
    for marker in "${valid_markers[@]}"; do
        if [[ "$test_marker" == "$marker" ]]; then
            is_valid=true
            break
        fi
    done
    
    if [[ "$is_valid" == "false" ]]; then
        echo -e "${RED}錯誤: 無效的測試標記 '$test_marker'${NC}"
        echo -e "${YELLOW}有效的測試標記:${NC}"
        for marker in "${valid_markers[@]}"; do
            echo "  • $marker"
        done
        echo ""
        echo -e "${YELLOW}組合標記範例:${NC}"
        echo "  • \"login or table\""
        echo "  • \"bac_odds or dtb_odds\""
        echo "  • \"bac_bet and not bac_balancecheck\""
        return 1
    fi
    
    return 0
}

# 驗證容器名稱
validate_container_name() {
    local container_name="$1"
    
    # 檢查容器名稱是否符合 Docker 命名規則
    if [[ ! "$container_name" =~ ^[a-zA-Z0-9][a-zA-Z0-9_.-]*$ ]]; then
        echo -e "${RED}錯誤: 容器名稱 '$container_name' 不符合 Docker 命名規則${NC}"
        echo -e "${YELLOW}容器名稱規則:${NC}"
        echo "  • 只能包含字母、數字、底線、點號、連字號"
        echo "  • 必須以字母或數字開頭"
        echo "  • 不能包含空格或特殊符號"
        return 1
    fi
    
    return 0
}

# =============================================================================
# 主程式
# =============================================================================

main() {
    # 解析參數
    local force_build=false
    local clean_before=false
    local show_logs_only=false
    local enter_shell_only=false
    local player_id=""
    local test_marker=""
    local container_name=""
    local custom_name_flag=false
    
    # 處理選項
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_usage
                exit 0
                ;;
            -b|--build)
                force_build=true
                shift
                ;;
            -c|--clean)
                clean_before=true
                shift
                ;;
            -l|--logs)
                show_logs_only=true
                shift
                ;;
            -s|--shell)
                enter_shell_only=true
                shift
                ;;
            -n|--name)
                custom_name_flag=true
                if [[ -n "$2" && "$2" != -* ]]; then
                    container_name="$2"
                    shift 2
                else
                    echo -e "${RED}錯誤: --name 選項需要指定容器名稱${NC}"
                    exit 1
                fi
                ;;
            -*)
                echo -e "${RED}未知選項: $1${NC}"
                show_usage
                exit 1
                ;;
            *)
                if [[ -z "$player_id" ]]; then
                    player_id="$1"
                elif [[ -z "$test_marker" ]]; then
                    test_marker="$1"
                elif [[ -z "$container_name" && "$custom_name_flag" == "false" ]]; then
                    container_name="$1"
                else
                    echo -e "${RED}太多參數${NC}"
                    show_usage
                    exit 1
                fi
                shift
                ;;
        esac
    done
    
    # 設定預設值
    player_id="${player_id:-$DEFAULT_PLAYER_ID}"
    test_marker="${test_marker:-$DEFAULT_TEST_MARKER}"
    container_name="${container_name:-$DEFAULT_CONTAINER_NAME}"
    
    # 顯示橫幅
    show_banner
    
    # 只顯示日誌
    if [[ "$show_logs_only" == "true" ]]; then
        show_logs
        exit 0
    fi
    
    # 檢查依賴
    check_dependencies
    
    # 只進入 shell
    if [[ "$enter_shell_only" == "true" ]]; then
        check_and_build_image "$force_build"
        prepare_environment
        enter_shell "$container_name"
        exit 0
    fi
    
    # 驗證參數
    if ! validate_parameters "$player_id" "$test_marker"; then
        exit 1
    fi

    # 驗證容器名稱
    if ! validate_container_name "$container_name"; then
        exit 1
    fi
    
    # 清理舊容器（如果要求）
    if [[ "$clean_before" == "true" ]]; then
        clean_containers
    fi
    
    # 檢查並構建映像
    check_and_build_image "$force_build"
    
    # 準備環境
    prepare_environment
    
    # 執行測試
    run_test "$player_id" "$test_marker" "$container_name"
    
    echo -e "${GREEN}腳本執行完成！${NC}"
}

# 執行主程式
main "$@"