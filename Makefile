SHELL := /bin/bash

.DEFAULT_GOAL := help

UV ?= uv
CLI ?= flow-dictate
SWIFT_APP_PATH ?= macos/FlowDictateApp

BACKEND ?= api
OUTPUT ?= active-app

.PHONY: help setup sync check test lint doctor doctor-json doctor-prompt \
	hotkey-setup run run-stub run-api run-realtime daemon daemon-stub \
	build swift-build swift-test app-install app-open app-uninstall

help:
	@echo ""
	@echo "Flow Dictate Developer Makefile"
	@echo "==============================="
	@echo ""
	@echo "Setup"
	@echo "  make setup                    # create .venv and sync runtime + dev deps"
	@echo "  make sync                     # sync runtime + dev deps"
	@echo ""
	@echo "Quality"
	@echo "  make test                     # run Python unit tests"
	@echo "  make lint                     # run Ruff lint checks"
	@echo "  make check                    # run lint + test"
	@echo ""
	@echo "CLI Workflows"
	@echo "  make doctor                   # permission preflight"
	@echo "  make doctor-prompt            # permission preflight with prompts"
	@echo "  make doctor-json              # machine-readable permission report"
	@echo "  make hotkey-setup             # capture and persist hotkey to .env"
	@echo "  make run BACKEND=api OUTPUT=active-app"
	@echo "  make run-stub                 # one deterministic stub cycle"
	@echo "  make run-api OUTPUT=stdout    # API transcription mode"
	@echo "  make run-realtime OUTPUT=stdout"
	@echo "  make daemon BACKEND=api OUTPUT=active-app"
	@echo "  make daemon-stub              # one deterministic daemon cycle"
	@echo ""
	@echo "Build and Packaging"
	@echo "  make build                    # build Python package (uv build)"
	@echo "  make swift-build              # build menu-bar app package"
	@echo "  make swift-test               # run menu-bar app tests"
	@echo ""
	@echo "macOS App Install"
	@echo "  make app-install              # install / refresh FlowDictate.app"
	@echo "  make app-open                 # open installed app"
	@echo "  make app-uninstall            # uninstall app and related state"
	@echo ""
	@echo "Variable defaults:"
	@echo "  BACKEND=$(BACKEND) OUTPUT=$(OUTPUT)"
	@echo ""

setup:
	$(UV) venv
	$(UV) sync --group dev

sync:
	$(UV) sync --group dev

test:
	$(UV) run --group dev pytest

lint:
	$(UV) run --group dev ruff check .

check: lint test

doctor:
	$(UV) run $(CLI) doctor

doctor-prompt:
	$(UV) run $(CLI) doctor --prompt-permissions

doctor-json:
	$(UV) run $(CLI) doctor --json

hotkey-setup:
	$(UV) run $(CLI) hotkey-setup

run:
	$(UV) run $(CLI) run --backend $(BACKEND) --output $(OUTPUT)

run-stub:
	$(UV) run $(CLI) run --backend stub --output stdout --run-once --simulate-trigger --use-stub-hotkey

run-api:
	$(UV) run $(CLI) run --backend api --output $(OUTPUT)

run-realtime:
	$(UV) run $(CLI) run --backend realtime --output $(OUTPUT)

daemon:
	$(UV) run $(CLI) daemon --backend $(BACKEND) --output $(OUTPUT)

daemon-stub:
	$(UV) run $(CLI) daemon --backend stub --output stdout --run-once --simulate-trigger --use-stub-hotkey

build:
	$(UV) build

swift-build:
	swift build --package-path $(SWIFT_APP_PATH)

swift-test:
	swift test --package-path $(SWIFT_APP_PATH)

app-install:
	./scripts/install_team_alpha_macos.sh

app-open:
	open /Applications/FlowDictate.app

app-uninstall:
	./scripts/uninstall_team_alpha_macos.sh
