### Feat
1.  20022 force quit handle
2.  betting behavior
    1.  Hedge caluate
    2.  good trend
    3.  multi table
3.  handle get 641 while bet resp
4.  餘額確認retry
    - 主要是單一錢包, 因單一錢包在投注扣款時, 都是單筆單筆注單去錢包對接方請求, 若錢包對接方回傳時給的timestamp相同, 但順序錯誤, 這會導致在餘額確認的相關Case判斷為Fail
      - >目前已有在餘額驗證的相關參數內添加了wait 5s, 取5s內最後拿到的餘額作為判斷
      - >但在7/25測試時, 有發生兩筆注單的派彩請求timestamp相同, 但順序是錯的, 導致測試上有出現Fail
      - **暫定** 預計讓餘額確認的方法做fail retry, 若該次失敗, wait 5s後再次確認餘額?
    - 轉帳錢包通常不會有這問題, 因單次下注多筆注單時, 轉帳錢包是整筆批次給lobby做計算, 故不會有順序的問題, 會是當局所有注單直接發一筆餘額更新
5.  測項Fail retry
6.  連線重連 retry

### Refactor


### fix


### pytest command
1. pytest tests/test_betting.py -vs
2. pytest tests/ --alluredir=./reports/allure-results  # 執行測試並產生 allure 結果
3. allure serve ./reports/allure-results  # 查看報告
4. allure generate ./reports/allure-results -o ./reports/allure-report  # 產生靜態報告
5. pytest -m marker --collect-only -v # 計算符合特定標記的測試數量, 但不執行