# Contributing to TraceZero

Contributions, bug reports, and new detector/extractor adapters are welcome.

## Development Setup

```bash
pip install -e ".[dev]"
pytest -v
```

## Guidelines

- Keep model weights out of Git (`models/` is gitignored).
- Add unit tests under `tests/` that run fast without requiring large downloads (mock heavy `transformers` models in unit tests).
- Keep functions focused and well-typed with concise docstrings.
