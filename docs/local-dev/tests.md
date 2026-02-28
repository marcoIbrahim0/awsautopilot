# Testing

Pytest is the primary test runner.

## Run

```bash
pytest
pytest -v
pytest -k "health"
```

## Useful Targets

```bash
pytest tests/test_health_readiness.py
pytest tests/test_worker_main_contract_quarantine.py
pytest tests/test_control_plane_readiness.py
```

## Coverage

```bash
pytest --cov=backend --cov=backend.workers --cov-report=html
```

## Notes

- Some tests rely on mocked AWS dependencies.
- Infra/evidence tests are broader validation and may require additional local setup.

## Related

- [Backend development](/Users/marcomaher/AWS%20Security%20Autopilot/docs/local-dev/backend.md)
- [Worker development](/Users/marcomaher/AWS%20Security%20Autopilot/docs/local-dev/worker.md)
