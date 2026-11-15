.PHONY: venv lint test coverage package audit secrets run emulator demo aero clean

PY := venv/bin/python
# make venv PYTHON_VERSION=3.15 (CI: the latest stable); else .python-version
PYTHON_VERSION ?= $(shell cat .python-version)

venv:
	uv venv venv --python "$(PYTHON_VERSION)"
	uv pip install --python $(PY) -r pip_requirements.txt

lint:
	venv/bin/ruff check .
	venv/bin/ruff format --check .

test:
	$(PY) -m pytest

# Tests with line coverage of kta16 (coverage.xml, read by .github/coverage-badge.sh)
coverage:
	$(PY) -m pytest --cov=kta16 --cov-report=term --cov-report=xml

# Wheel and source archive build; the wheel installs in a fresh venv and starts
package:
	rm -rf build/pkg build/pkg-venv
	uv build --out-dir build/pkg
	uv venv build/pkg-venv --python "$(PYTHON_VERSION)"
	uv pip install --python build/pkg-venv/bin/python build/pkg/*.whl
	build/pkg-venv/bin/kta16 --help >/dev/null
	build/pkg-venv/bin/python -c "import kta16.aero as a; assert a.load(), 'aero.json missing'"

# Known vulnerabilities in the dependencies (pip-audit)
audit:
	sh .github/audit.sh

# Secrets in the git history (gitleaks, through podman when not installed)
secrets:
	sh .github/secrets.sh

# make run (real radio: the adapter list opens) ; make run PORT=/dev/ttyUSB0 (no list)
# Any target takes the language: make run LANG_OPT="--lang en" (else the locale decides)
run:
	$(PY) -m kta16 $(if $(PORT),--port $(PORT)) $(LANG_OPT)

# Emulated radio, no cable needed
emulator:
	$(PY) -m kta16 --emulator $(LANG_OPT)

# Emulated radio with demo channels (for screenshots): make demo LANG_OPT="--lang en"
demo:
	PYTHONPATH=. $(PY) docs/make_demo_image.py demo.img
	$(PY) -m kta16 --emulator $(LANG_OPT) demo.img

# Rebuild kta16/aero.json from the SIA eAIP of the current AIRAC cycle (every 28 days)
aero:
	$(PY) -m kta16.aero

clean:
	rm -rf venv .pytest_cache .ruff_cache demo.img build/pkg build/pkg-venv dist coverage.xml .coverage
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
