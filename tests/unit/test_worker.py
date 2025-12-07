# tests/unit/test_worker.py
from unittest.mock import MagicMock, patch

from apps.worker.main import process_message


def test_worker_handles_unknown_exception_by_nacking() -> None:
    """
    測試當發生未知錯誤時，Worker 是否會發送 NACK 並拒絕 Requeue (送入 DLQ)
    """

    # 1. Mock RabbitMQ 的 channel
    mock_channel = MagicMock()
    mock_method = MagicMock()
    mock_method.delivery_tag = 1  # 假裝這是第一筆訊息

    # 2. 準備測試資料
    body = b'{"order_id": "TEST_FAIL", "amount": 100, "status": "PENDING"}'

    # 3. 【關鍵】Mock 掉 DB Session，讓它故意報錯！
    # 我們不改 source code，而是用 patch 把 Session 替換成一個會爆炸的假物件
    with patch("apps.worker.main.Session") as mock_session:
        # 設定：當程式呼叫 session.commit() 時，拋出 Exception
        mock_session.return_value.__enter__.return_value.commit.side_effect = Exception(
            "DB Is Dead"
        )

        # 4. 執行被測函式
        process_message(mock_channel, mock_method, None, body)

        # 5. 驗證結果 (Assert)
        # 驗證 basic_nack 是否被呼叫
        mock_channel.basic_nack.assert_called_once()

        # 驗證參數是否正確：requeue=False (這代表會進 DLQ)
        mock_channel.basic_nack.assert_called_with(delivery_tag=1, requeue=False)

        print("\n✅ Test Passed: Worker correctly NACKed the failed message.")
