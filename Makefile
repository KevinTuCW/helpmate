.PHONY: install test gate ci

install:          ## install the package with dev extras
	pip install -e ".[dev]"

test:             ## run the unit-test suite (the CI gate)
	pytest -q

gate:             ## run the golden-set eval gate (needs live DB + API keys)
	python -m eval.run_eval

ci: test          ## what CI runs
