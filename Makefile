.PHONY: install run test gate ci

install:          ## install the package with dev extras
	pip install -e ".[dev]"

run:              ## start the dev server on :8000 (needs live DB + .env)
	.venv/bin/uvicorn helpmate.app:app --reload --port 8000

test:             ## run the unit-test suite (the CI gate)
	pytest -q

gate:             ## run the golden-set eval gate (needs live DB + API keys)
	python -m eval.run_eval

ci: test          ## what CI runs
