import asyncio
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from renderctl.cache import ResultCache
from renderctl.cli import _demo, _fixture
from renderctl.client import GenerateRequest, JobStatus, RenderEngine
from renderctl.config import RenderConfig
from renderctl.costs import CostTracker
from renderctl.jobs import JobQueue
from renderctl.pipelines.engine import Pipeline, PipelineEngine, PipelineStep
from renderctl.storage import AssetStore
from renderctl.webhooks import WebhookDispatcher, WebhookEvent


class FakeTransport:
    def __init__(self) -> None:
        self.calls = 0

    async def submit(self, request: GenerateRequest) -> dict[str, object]:
        self.calls += 1
        await asyncio.sleep(0.01)
        return {"model": request.model_id, "params": request.params}


class CandidateTests(unittest.TestCase):
    def test_sqlite_connections_are_closed(self) -> None:
        class TrackingConnection(sqlite3.Connection):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.was_closed = False

            def close(self):
                self.was_closed = True
                super().close()

        original_connect = sqlite3.connect
        connections = []

        def connect(*args, **kwargs):
            connection = original_connect(*args, factory=TrackingConnection, **kwargs)
            connections.append(connection)
            return connection

        with tempfile.TemporaryDirectory() as tmp, patch("sqlite3.connect", side_effect=connect):
            root = Path(tmp)
            cache = ResultCache(root / "cache.sqlite")
            key = cache.make_key("fixture/image-basic", {"prompt": "shape"})
            cache.put(key, {"url": "fixture://result"})
            cache.get(key)
            cache.cleanup()

            queue = JobQueue(root / "jobs.sqlite")
            job_id = queue.enqueue("fixture/image-basic", {"prompt": "shape"})
            queue.claim()
            queue.finish(job_id, {"url": "fixture://result"})

            tracker = CostTracker(root / "costs.sqlite", daily=1.0)
            tracker.record("one", "fixture/image-basic", 0.25)
            tracker.check_budget()

        self.assertGreater(len(connections), 0)
        self.assertTrue(all(connection.was_closed for connection in connections))

    def test_engine_deduplicates_identical_inflight_work(self) -> None:
        async def exercise() -> tuple[int, list[JobStatus]]:
            transport = FakeTransport()
            engine = RenderEngine(transport, RenderConfig(requests_per_second=100, burst=10))
            request = GenerateRequest("fixture/image-basic", {"prompt": "shape"})
            jobs = await asyncio.gather(engine.generate(request), engine.generate(request))
            return transport.calls, [job.status for job in jobs]

        calls, statuses = asyncio.run(exercise())
        self.assertEqual(calls, 1)
        self.assertEqual(statuses, [JobStatus.COMPLETED, JobStatus.COMPLETED])

    def test_cache_queue_and_contained_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = ResultCache(root / "cache.sqlite")
            key = cache.make_key("fixture/image-basic", {"prompt": "shape"})
            cache.put(key, {"url": "fixture://result"})
            self.assertEqual(cache.get(key), {"url": "fixture://result"})

            queue = JobQueue(root / "jobs.sqlite")
            job_id = queue.enqueue("fixture/image-basic", {"prompt": "shape"})
            self.assertEqual(queue.claim()["id"], job_id)

            store = AssetStore(root / "assets")
            self.assertTrue(store.write("runs/a.bin", b"ok").is_file())
            with self.assertRaises(ValueError):
                store.write("../escape.bin", b"bad")

    def test_pipeline_rejects_cycles(self) -> None:
        async def noop(context, params):
            return {}

        pipeline = Pipeline(
            "cycle",
            (
                PipelineStep("a", noop, ("b",)),
                PipelineStep("b", noop, ("a",)),
            ),
        )
        with self.assertRaises(ValueError):
            asyncio.run(PipelineEngine().run(pipeline))

    def test_retry_budget_webhook_and_offline_fixtures(self) -> None:
        class FlakyTransport:
            def __init__(self):
                self.calls = 0

            async def submit(self, request):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("synthetic failure")
                return {"ok": True}

        async def exercise():
            transport = FlakyTransport()
            engine = RenderEngine(
                transport,
                RenderConfig(requests_per_second=100, burst=2, max_retries=1, retry_base_seconds=0),
            )
            job = await engine.generate(GenerateRequest("fixture/image-basic", {"prompt": "shape"}))
            received = []
            dispatcher = WebhookDispatcher()

            async def broken(event):
                raise RuntimeError("isolated callback failure")

            async def working(event):
                received.append(event.job_id)

            dispatcher.register(broken)
            dispatcher.register(working)
            errors = await dispatcher.dispatch(WebhookEvent.from_mapping({"event": "done", "job_id": job.id}))
            return transport.calls, job, received, errors

        calls, job, received, errors = asyncio.run(exercise())
        self.assertEqual(calls, 2)
        self.assertEqual(job.status, JobStatus.COMPLETED)
        self.assertEqual(received, [job.id])
        self.assertEqual(len(errors), 1)
        self.assertEqual(_fixture("models.json")["models"][0]["id"], "fixture/image-basic")
        self.assertEqual(asyncio.run(_demo())["status"], JobStatus.COMPLETED)

        with tempfile.TemporaryDirectory() as tmp:
            tracker = CostTracker(Path(tmp) / "costs.sqlite", daily=1.0, monthly=2.0)
            tracker.record("one", "fixture/image-basic", 0.75)
            self.assertTrue(tracker.check_budget(0.2)[0])
            self.assertFalse(tracker.check_budget(0.3)[0])


if __name__ == "__main__":
    unittest.main()
