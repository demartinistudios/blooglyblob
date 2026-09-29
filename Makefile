.PHONY: help pi-check pi-payload pi-provision pi-update pi-ssh pi-run pi-logs pi-start pi-stop pi-restart pi-status pi-check-audio pi-test-audio pi-test-mic pi-test-neopixels dev-setup dev-test dev-lint dev-typecheck dev-check dev-format dev-format-check dev-setup-ring dev-setup-roku

# .env is parsed as data by deploy.py; never include it as Make/shell code.
# Command-line Make assignments already outrank exported environment variables.
ifneq ($(origin PI_HOST),undefined)
export PI_HOST
endif
ifneq ($(origin PI_USER),undefined)
export PI_USER
endif
ifneq ($(origin BLOOGLYBLOB_ENV_FILE),undefined)
export BLOOGLYBLOB_ENV_FILE
endif
DEV_PYTHON ?= .venv/bin/python
HOST_PYTHON ?= python3
GUIDE_SYSTEM_DEPS ?= 0

help:
	@echo "Blooglyblob: one Pi application"
	@echo "  pi-check            Read-only SSH identity / supported OS check"
	@echo "  pi-payload          List the exact runtime payload without connecting"
	@echo "  pi-provision        Complete installation or repair (safe to rerun)"
	@echo "  pi-update           Update application and Python dependencies only"
	@echo "  pi-status / pi-logs Inspect the application service"
	@echo "  pi-start / pi-stop / pi-restart / pi-ssh"
	@echo "  pi-run              Foreground application; restores prior service state"
	@echo "  pi-servo-fit        Hold the assembly fit pose; leave application stopped"
	@echo "  pi-check-audio / pi-test-audio / pi-test-mic"
	@echo "  pi-test-neopixels"
	@echo "  dev-setup / dev-check / dev-test / dev-lint / dev-typecheck / dev-format"
	@echo "  check               Complete offline contributor checks (after setup)"
	@echo "  publication-check   Check indexed files for private paths and credentials"
	@echo "  dev-format-check / dev-coverage / dev-install-hook (optional)"
	@echo "  guide-setup         Install locked browser dependencies (network required)"
	@echo "  dev-setup-ring / dev-setup-roku"
	@echo "  hardware-test / hardware-check / guide-build / guide-browser (offline)"

.PHONY: pi-servo-fit
pi-check pi-payload pi-provision pi-update pi-ssh pi-run pi-logs pi-start pi-stop pi-restart pi-status pi-check-audio pi-test-audio pi-test-mic pi-test-neopixels pi-servo-fit:
	@$(HOST_PYTHON) scripts/deploy.py $(@:pi-%=%)

dev-setup:
	$(HOST_PYTHON) -m venv .venv
	$(DEV_PYTHON) -m pip install -c requirements/dev.txt -r requirements-dev.txt
	$(DEV_PYTHON) -m pip install --no-deps --no-build-isolation -e .

dev-test dev-lint dev-typecheck dev-format dev-format-check:
	@DEV_PYTHON="$(DEV_PYTHON)" ./scripts/check.sh $(@:dev-%=%)

dev-check:
	@DEV_PYTHON="$(DEV_PYTHON)" ./scripts/check.sh

.PHONY: check publication-check dev-coverage dev-install-hook guide-setup hardware-test
# Keep stages sequential even with make -j; the browser target builds once.
check:
	@$(MAKE) publication-check
	@$(MAKE) dev-check
	@$(MAKE) hardware-test
	@$(MAKE) hardware-check
	@$(MAKE) guide-browser

publication-check:
	$(HOST_PYTHON) scripts/check_publication.py

dev-coverage:
	@DEV_PYTHON="$(DEV_PYTHON)" ./scripts/check.sh coverage

dev-install-hook:
	$(DEV_PYTHON) scripts/pre_commit.py install

guide-setup:
	@GUIDE_SYSTEM_DEPS="$(GUIDE_SYSTEM_DEPS)" sh hardware/tools/guide/setup.sh

dev-setup-ring:
	$(DEV_PYTHON) scripts/setup_ring.py

dev-setup-roku:
	$(DEV_PYTHON) scripts/setup_roku.py

# Offline hardware checks never connect to Fusion, the printer or the Pi.
.PHONY: hardware-check guide-build guide-browser
hardware-test:
	$(HOST_PYTHON) -m unittest discover -s hardware/cad/design-control -p 'test_*.py'
	$(HOST_PYTHON) -m unittest discover -s hardware/tools/validation -p 'test_*.py'
	$(HOST_PYTHON) -m unittest discover -s hardware/tools/printing -p 'test_*.py'
	$(HOST_PYTHON) -m unittest discover -s hardware/tools/guide -p 'test_*.py'

hardware-check:
	$(HOST_PYTHON) hardware/tools/validation/check.py

guide-build:
	$(HOST_PYTHON) hardware/tools/guide/build.py

guide-browser: guide-build
	@command -v node >/dev/null 2>&1 || { echo "Install Node.js 22+ and run make guide-setup." >&2; exit 2; }
	@test -x hardware/tools/guide/node_modules/.bin/playwright || { echo "Run make guide-setup before browser checks." >&2; exit 2; }
	$(HOST_PYTHON) hardware/tools/guide/browser.py
