<div align="center">
  <img src="docs/cover.png" alt="renderctl" width="100%">
  <p><strong>Local orchestration primitives for provider-backed media jobs.</strong></p>
  <p>
    <a href="#why-renderctl">Why</a> ·
    <a href="#system-map">System map</a> ·
    <a href="#quick-start">Quick start</a> ·
    <a href="#verification">Verification</a> ·
    <a href="#project-boundaries">Boundaries</a>
  </p>
  <p>
    <img alt="Status: pre-1.0" src="https://img.shields.io/badge/status-pre--1.0-64748b">
    <img alt="Python 3.11 or newer" src="https://img.shields.io/badge/python-3.11%2B-3776AB">
    <img alt="Runtime: standard library" src="https://img.shields.io/badge/runtime-standard_library-475569">
    <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-16a34a">
  </p>
</div>

`renderctl` is a provider-neutral Python library for applications that submit media-generation jobs. The application owns the provider transport; `renderctl` handles the local mechanics around it: concurrency, request rate, retries, identical in-flight work, job state, storage helpers, callbacks, and dependency-aware pipelines.

The pieces are intentionally independent. An application can adopt the request engine without the SQLite cache, use the pipeline executor without the queue, or add a cost ledger without accepting a bundled service architecture.

## Why renderctl

Provider integrations usually begin as one request function and quickly accumulate unrelated concerns. Rate limits, retry behavior, duplicate work, local artifacts, spend records, queues, and callbacks end up coupled to one vendor's payload format. Replacing a provider then means rewriting the operational layer as well as the transport.

`renderctl` keeps that boundary explicit. A transport implements one asynchronous `submit(request)` method and returns a result dictionary. The orchestration core does not know how credentials are stored, how a provider names a model, or which moderation rules apply. Those decisions remain visible in the integrating application.

Use it when the missing piece is a small local control layer, not another hosted platform.

## System map

| Layer | Responsibility | Persistence |
| --- | --- | --- |
| `RenderEngine` | Concurrency, token-bucket rate limiting, retries, batch submission, and in-flight coalescing | Process-local |
| Transport contract | Provider authentication, wire format, error mapping, and response normalization | Caller-defined |
| `ResultCache` | Reusable result records with retention cleanup | SQLite |
| `JobQueue` | Enqueue, claim, and finish lifecycle for local jobs | SQLite |
| `CostTracker` | Caller-supplied amounts and daily/monthly limit checks | SQLite |
| `AssetStore` | Contained writes under a configured local root | Filesystem |
| `WebhookDispatcher` | Fan-out to registered asynchronous callbacks while isolating failures | Process-local |
| `PipelineEngine` | Dependency ordering, parallel ready-step execution, and cycle rejection | Process-local |
| Storyboard helpers | Small scene, template, batch, and comparison structures | In memory |

Nothing in the library silently connects these layers. A caller that wants cached generation, queued execution, and callback delivery must compose those pieces deliberately.

## Implemented capabilities

- Asynchronous provider transport protocol.
- Configurable concurrency semaphore.
- Token-bucket request limiting with burst capacity.
- Bounded retries with exponential delay.
- SHA-256 identity for normalized model and parameter requests.
- Coalescing of identical work while one engine instance has that work in flight.
- Batch generation through the same engine controls.
- SQLite cache with explicit retention cleanup.
- SQLite queue with enqueue, claim, completion, result, and error state.
- SQLite cost records with caller-supplied daily and monthly checks.
- Local asset writes that reject attempts to escape the configured root.
- Callback dispatch that reports individual failures without preventing other callbacks.
- Dependency-aware pipelines that reject duplicate names, cycles, and missing dependencies.
- Offline model and prompt fixtures plus a synthetic demonstration transport.

## Quick start

`renderctl` requires Python 3.11 or newer and has no runtime dependencies outside the standard library.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .

renderctl demo
renderctl models
renderctl prompts
```

`renderctl demo` runs one request through an in-process synthetic transport. It does not contact a provider, require credentials, or create an account. The other commands print bundled fixture data that is safe to use while wiring an integration.

## Practical usage

Start with the transport boundary. Normalize a provider response inside the application, return a dictionary from `submit`, and pass that transport to `RenderEngine`. A `GenerateRequest` contains the model identifier, provider parameters, priority, and tags. The resulting `Job` records lifecycle status, result or error, timestamps, and a caller-populated cost estimate.

The request engine returns failed jobs instead of raising the final provider exception. Always inspect `job.status` before consuming `job.result`. Retry attempts are limited by `RenderConfig`; the final error string includes the exception type and message produced by the transport.

The main configuration surface is small:

| Setting | Default | Meaning |
| --- | ---: | --- |
| `concurrency` | `4` | Maximum provider submissions active at once |
| `requests_per_second` | `5.0` | Token refill rate |
| `burst` | `8` | Maximum immediately available request tokens |
| `max_retries` | `3` | Retries after the first failed attempt |
| `retry_base_seconds` | `0.05` | Base delay before exponential growth |
| `cache_retention_hours` | `168` | Retention used by the cache helper |
| `budget_daily` / `budget_monthly` | unset | Optional values available to integrating code |

Identical request coalescing lasts only while one `RenderEngine` is running. Reuse across restarts requires the cache to be called explicitly. Likewise, `CostTracker` checks amounts already recorded by the caller; it does not fetch provider prices or reconcile an invoice.

Pipelines execute every step whose dependencies are satisfied, allowing independent ready steps to run together. A step receives the accumulated context and its own parameter copy. If the graph cannot make progress, the engine rejects it instead of leaving a partial workflow running.

## Verification

```bash
python -m unittest discover -s tests -v
python -m compileall -q src tests
renderctl demo
```

The current tests exercise closed SQLite connections, identical in-flight request coalescing, cache and queue behavior, contained asset writes, dependency-cycle rejection, retry recovery, budget checks, callback failure isolation, bundled fixtures, and the offline demo. They use temporary directories and synthetic transports; no provider request is made.

## Repository map

| Path | Responsibility |
| --- | --- |
| `src/renderctl/client.py` | Requests, jobs, transport contract, rate limiting, retries, and in-flight coalescing |
| `src/renderctl/config.py` | Validated local configuration |
| `src/renderctl/cache.py` | SQLite result cache and cleanup |
| `src/renderctl/jobs.py` | SQLite queue lifecycle |
| `src/renderctl/costs.py` | Local cost records and limit checks |
| `src/renderctl/storage.py` | Contained filesystem asset writes |
| `src/renderctl/webhooks.py` | In-process callback dispatch |
| `src/renderctl/pipelines/` | Pipeline execution, batches, comparisons, steps, and storyboards |
| `src/renderctl/cli.py` | Offline demonstration and fixture commands |
| `tests/test_candidate.py` | Integration-oriented tests across the public surface |

## Project boundaries

`renderctl` is not a provider SDK, hosted worker, HTTP listener, credential store, account system, moderation service, or billing system. It contains no live provider adapter. Authentication, authorization, request validation, provider-specific errors, content policy, retention, and deployment controls belong to the application around it.

The queue uses SQLite but does not run workers. The callback dispatcher invokes registered functions but does not expose a webhook endpoint or verify remote signatures. The asset store writes bytes under a local root but does not download remote results. Storyboards describe scenes; they do not render or edit media.

These limits are part of the package boundary. They keep the orchestration core testable and prevent provider policy from being hidden inside a generic helper.

## Documentation and support

- [Changelog](CHANGELOG.md) — current pre-release capability summary.
- [Security](SECURITY.md) — integration responsibilities and reporting guidance.
- [Contributing](CONTRIBUTING.md) — local development expectations.
- [`src/renderctl/cli.py`](src/renderctl/cli.py) — smallest complete transport and engine flow.

Interfaces may change before 1.0. Open an issue with a minimal synthetic transport and the verification output when reporting a defect.

## Contributing, security, and license

Keep provider-specific behavior outside the core, add focused tests for concurrency or persistence changes, and avoid fixtures containing credentials or private endpoints. Security reports should use GitHub's private advisory channel.

`renderctl` is available under the [MIT License](LICENSE).
