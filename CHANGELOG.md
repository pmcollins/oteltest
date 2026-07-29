# Changelog

## 0.48.1 (2026-07-29)

- Close the `HttpSink` server socket on shutdown so its port can be reused
  immediately

## 0.48.0 (2026-07-23)

- Add OpAMP remote configuration support, including JSON and properties formats
- Add behavioral regression scenarios, golden-file tooling, and nightly upstream
  regression tests
- Ignore service instance IDs when comparing behavioral regression results
- Publish releases to PyPI through trusted publishing

## 0.47.0 (2026-04-24)

- Fix Windows venv executable path (`Scripts/` instead of `bin/`)
- Drop EOL Python 3.8 and 3.9; add Python 3.13 and 3.14 to CI

## 0.46.0

- Fix port reuse after sink shutdown
- Add JSON over HTTP support to `HttpSink`
- Add unit tests for JSON over HTTP parsing

## 0.45.0

- Install pip requirements in a single batch instead of individually

## 0.44.0

- Fix HTTP sink shutdown on macOS
