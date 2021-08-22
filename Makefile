checkfiles = fast_tmp/ conftest.py
black_opts = -l 100 -t py38
py_warn = PYTHONDEVMODE=1
test_settings = SETTINGS_MODULE=tests.settings

help:
	@echo "fastapi-cli development makefile"
	@echo
	@echo  "usage: make <target>"
	@echo  "Targets:"
	@echo  "    up			Updates dev/test dependencies"
	@echo  "    deps		Ensure dev/test dependencies are installed"
	@echo  "    check		Checks that build is sane"
	@echo  "    test		Runs all tests"
	@echo  "    style		Auto-formats the code"

up:
	@poetry update

deps:
	@poetry install --no-root

style: deps
	isort -src $(checkfiles)
	black $(black_opts) $(checkfiles)

check: deps
	black --check $(black_opts) $(checkfiles) || (echo "Please run 'make style' to auto-fix style issues" && false)
	flake8 $(checkfiles)
	bandit -ll -x test -r $(checkfiles)
	mypy --ignore-missing-imports $(checkfiles)


test_sqlite:
	$(py_warn) FASTAPI_SETTINGS_MODULE=tests.settings TORTOISE_TEST_DB=sqlite://:memory: pytest --cov-report=

test: deps test_sqlite
	coverage report

publish: check
	poetry publish