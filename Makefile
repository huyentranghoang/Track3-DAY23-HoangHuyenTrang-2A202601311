.PHONY: install test lint typecheck run-scenarios grade-local demo demo-install clean web

install:
	pip install -e '.[dev,openai]'

test:
	pytest

lint:
	ruff check src tests

typecheck:
	mypy src

run-scenarios:
	python -m langgraph_agent_lab.cli run-scenarios --config configs/lab.yaml --output outputs/metrics.json

grade-local:
	python -m langgraph_agent_lab.cli validate-metrics --metrics outputs/metrics.json

demo:
	streamlit run demo_app.py

demo-install:
	pip install -e '.[ui,openai]'
	streamlit run demo_app.py

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov dist build *.egg-info outputs/*.json

web:
	python -m web
