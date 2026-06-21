.PHONY: test

test:
	python -m pip install -e '.[dev]'
	pytest -q
