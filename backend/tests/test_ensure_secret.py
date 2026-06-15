"""_ensure_secret 多线程安全测试

覆盖：
- 多线程并发调用只初始化一次密钥
"""

import threading
from unittest.mock import patch, call

import app.api.auth as auth_mod


class TestEnsureSecretThreadSafety:
    """_ensure_secret 在多线程下只初始化一次密钥"""

    def test_concurrent_calls_initialize_once(self):
        """N 个线程并发调用 _ensure_secret，_init_jwt_secret 只被调用一次"""
        # 重置全局状态
        auth_mod._SECRET_KEY = ""

        call_count = 0
        original_init = auth_mod._init_jwt_secret

        def counting_init():
            nonlocal call_count
            call_count += 1
            return "test-secret-key"

        with patch.object(auth_mod, "_init_jwt_secret", side_effect=counting_init):
            results = []
            barrier = threading.Barrier(10)

            def worker():
                barrier.wait()
                key = auth_mod._ensure_secret()
                results.append(key)

            threads = [threading.Thread(target=worker) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        # 所有线程拿到相同的 key
        assert all(k == "test-secret-key" for k in results)
        assert len(results) == 10
        # _init_jwt_secret 只被调用一次（double-check locking 保证）
        assert call_count == 1

    def test_subsequent_calls_return_cached_key(self):
        """首次初始化后，后续调用直接返回缓存值（不调用 _init_jwt_secret）"""
        auth_mod._SECRET_KEY = ""

        with patch.object(auth_mod, "_init_jwt_secret", return_value="cached-key") as mock_init:
            key1 = auth_mod._ensure_secret()
            key2 = auth_mod._ensure_secret()
            key3 = auth_mod._ensure_secret()

        assert key1 == key2 == key3 == "cached-key"
        assert mock_init.call_count == 1

    def test_returns_pre_existing_key(self):
        """如果 _SECRET_KEY 已有值，直接返回，不调用 _init_jwt_secret"""
        auth_mod._SECRET_KEY = "pre-existing"

        with patch.object(auth_mod, "_init_jwt_secret") as mock_init:
            key = auth_mod._ensure_secret()

        assert key == "pre-existing"
        mock_init.assert_not_called()

        # 清理
        auth_mod._SECRET_KEY = ""
