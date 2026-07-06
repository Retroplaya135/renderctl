# Contributing

Keep the library independent of provider SDKs and testable without network access. Install it using the steps in [README.md](README.md), then run:

```bash
python -m unittest discover -s tests -v
python -m compileall -q src tests
```

Add focused tests for changes to retries, deduplication, persistence, pipeline dependencies, or asset paths. Provider transports belong in integrating applications. Use synthetic fixtures; keep keys, private endpoints, customer media, and copied provider catalogs out of the repository.
