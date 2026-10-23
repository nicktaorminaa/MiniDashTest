# Dependency audit

Every package was looked up on the official registry (`https://pypi.org/pypi/<name>/json`) before it
was installed, on 23 Oct 2026. Checked: the exact name exists, the project links to the expected
source repository and maintainer, it has a release history (not a brand-new name), and the pinned
version is the one installed. Versions are pinned in `requirements*.txt`.

## Direct dependencies

| Package | Version | Why | Registry check |
|---|---|---|---|
| fastapi | 0.162.0 | Web framework (required stack) | https://pypi.org/project/fastapi/ — source github.com/fastapi/fastapi, author Sebastián Ramírez |
| uvicorn | 0.54.0 | ASGI server to run the app | https://pypi.org/project/uvicorn/ — uvicorn.dev, author Tom Christie |
| tzdata | 2026.5 (Windows only) | IANA time-zone data for `zoneinfo` on Windows (ADR-002) | https://pypi.org/project/tzdata/ — github.com/python/tzdata, Python Software Foundation |

## Development dependencies

| Package | Version | Why | Registry check |
|---|---|---|---|
| pytest | 9.1.1 | Test runner | https://pypi.org/project/pytest/ — docs.pytest.org, pytest-dev maintainers |
| httpx2 | 2.16.0 | HTTP client required by FastAPI's `TestClient` | https://pypi.org/project/httpx2/ — github.com/pydantic/httpx2, author Tom Christie, 22 releases. See note. |
| ruff | 0.17.2 | Linter and formatter | https://pypi.org/project/ruff/ — docs.astral.sh/ruff, Astral Software |

## Optional test dependency (customer page)

| Package | Version | Why | Registry check |
|---|---|---|---|
| playwright | 1.63.0 | Drives headless Chromium for `tests/test_web_browser.py`. Listed in `requirements-browser.txt`, not in `requirements-dev.txt`, because it needs a ~150 MB browser download; without it those tests are skipped. | https://pypi.org/project/playwright/ — Microsoft Corporation, 87 releases; pinned below the latest (1.64.1) to match the Chromium build used for verification. Pulls in `greenlet` and `pyee`. |

The page itself adds no package: it is plain HTML, CSS and JavaScript served by FastAPI's own
`StaticFiles`, and its JavaScript tests use Node's built-in test runner (`node --test`), which needs
no npm packages.

## Transitive packages worth noting

| Package | Pulled in by | Check |
|---|---|---|
| opentelemetry-api | fastapi 0.162.0 | Declared in fastapi's own `Requires`; not imported by MiniDash. |
| httpcore2 | httpx2 | https://pypi.org/project/httpcore2/ — same repository as httpx2, 22 releases |
| truststore | httpx2 | https://pypi.org/project/truststore/ — github.com/sethmlarson/truststore, 17 releases |

## Notes

- **Deviation from Appendix C.** The baseline prompt allows only fastapi, uvicorn and pytest, but its
  own request for endpoint tests needs FastAPI's `TestClient`, which needs an HTTP client package.
  An HTTP client is therefore a dev dependency.
- **httpx → httpx2.** The baseline first used `httpx 0.28.1`. Starlette 1.9 then warned
  "Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead." A name
  suggested by a warning is exactly the kind of thing to verify, so before installing it was checked
  three ways: the installed Starlette source imports `httpx2` by that name, the PyPI project links to
  the pydantic GitHub organisation with the same author as httpx, and it has a 22-release history.
- No package was added for scheduling (no APScheduler, Celery or similar). See ADR-001.
