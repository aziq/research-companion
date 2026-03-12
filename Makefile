VENV    := .venv
PYTHON  := $(VENV)/bin/python
PIP     := $(VENV)/bin/pip
UVICORN := $(VENV)/bin/uvicorn
PORT    ?= 8080

.DEFAULT_GOAL := help

.PHONY: help install dev run kb adduser

help:
	@echo ""
	@echo "  make install          create .venv and install dependencies"
	@echo "  make dev              start with auto-reload (local dev)"
	@echo "  make run              start without auto-reload (production)"
	@echo "  make kb               open the admin CLI (python kb.py)"
	@echo "  make adduser          create a web-only user  (EMAIL=foo@bar.com)"
	@echo ""
	@echo "  PORT=8080 make dev    override the default port"
	@echo ""

$(VENV)/bin/activate: requirements.txt
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip --quiet
	$(PIP) install -r requirements.txt --quiet
	@touch $(VENV)/bin/activate

install: $(VENV)/bin/activate

dev: install
	$(UVICORN) main:app --reload --host 0.0.0.0 --port $(PORT)

run: install
	$(UVICORN) main:app --host 0.0.0.0 --port $(PORT)

kb: install
	$(PYTHON) kb.py $(ARGS)

adduser: install
ifndef EMAIL
	$(error EMAIL is not set — usage: make adduser EMAIL=alice@example.com)
endif
	$(PYTHON) kb.py adduser $(EMAIL)
