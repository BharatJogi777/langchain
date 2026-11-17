import asyncio
import unittest

from resilience import invoke_read_with_retry


class RetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_success_first_attempt(self):
        async def operation():
            return "ok"

        result = await invoke_read_with_retry(operation)
        self.assertEqual(result, "ok")

    async def test_transient_error_then_success(self):
        calls = 0

        async def operation():
            nonlocal calls
            calls += 1
            if calls < 3:
                raise ConnectionError("temporary")
            return "recovered"

        result = await invoke_read_with_retry(
            operation,
            max_attempts=3,
            base_delay_seconds=0,
            max_delay_seconds=0,
        )
        self.assertEqual(result, "recovered")
        self.assertEqual(calls, 3)

    async def test_exhaustion_raises(self):
        calls = 0

        async def operation():
            nonlocal calls
            calls += 1
            raise ConnectionError("still unavailable")

        with self.assertRaises(ConnectionError):
            await invoke_read_with_retry(
                operation,
                max_attempts=2,
                base_delay_seconds=0,
                max_delay_seconds=0,
            )
        self.assertEqual(calls, 2)

    async def test_timeout_is_retried_then_raises(self):
        calls = 0

        async def operation():
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.05)
            return "late"

        with self.assertRaises(TimeoutError):
            await invoke_read_with_retry(
                operation,
                timeout_seconds=0.001,
                max_attempts=2,
                base_delay_seconds=0,
                max_delay_seconds=0,
            )
        self.assertEqual(calls, 2)

    async def test_non_retryable_error_fails_immediately(self):
        calls = 0

        async def operation():
            nonlocal calls
            calls += 1
            raise ValueError("invalid input")

        with self.assertRaises(ValueError):
            await invoke_read_with_retry(
                operation,
                max_attempts=4,
                base_delay_seconds=0,
                max_delay_seconds=0,
            )
        self.assertEqual(calls, 1)

    async def test_invalid_configuration(self):
        async def operation():
            return "unused"

        with self.assertRaises(ValueError):
            await invoke_read_with_retry(operation, max_attempts=0)


if __name__ == "__main__":
    unittest.main()
