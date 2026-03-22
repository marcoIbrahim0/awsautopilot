# Testing

Pytest is the primary test runner.

## Run

```bash
PYTHONPATH=. ./venv/bin/pytest
PYTHONPATH=. ./venv/bin/pytest -v
PYTHONPATH=. ./venv/bin/pytest -k "health"
```

## Useful Targets

```bash
PYTHONPATH=. ./venv/bin/pytest tests/test_health_readiness.py
PYTHONPATH=. ./venv/bin/pytest tests/test_worker_main_contract_quarantine.py
PYTHONPATH=. ./venv/bin/pytest tests/test_control_plane_readiness.py
```

## Coverage

```bash
PYTHONPATH=. ./venv/bin/pytest --cov=backend --cov=backend.workers --cov-report=html
```

## Notes

- Some tests rely on mocked AWS dependencies.
- Infra/evidence tests are broader validation and may require additional local setup.

## Related

- [Backend development](/Users/marcomaher/AWS%20Security%20Autopilot/docs/local-dev/backend.md)
- [Worker development](/Users/marcomaher/AWS%20Security%20Autopilot/docs/local-dev/worker.md)
