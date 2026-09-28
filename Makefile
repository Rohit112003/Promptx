# Tokenised Fund Servicing Platform — task shortcuts.
# On Windows without `make`, use: python tasks.py <target>
.PHONY: setup chain deploy backend test seed demo

PY := $(shell if [ -f .venv/bin/python ]; then echo .venv/bin/python; else echo python; fi)

setup:            ## Install Node + Python deps, compile contract, export artifact
	npm install --no-audit --no-fund
	python -m venv .venv || true
	$(PY) -m pip install -U pip
	$(PY) -m pip install -r requirements.txt
	npx hardhat compile
	node scripts/export-artifact.js

chain:            ## Run a local Hardhat node (CHAIN_MODE=hardhat)
	npx hardhat node

deploy:           ## Deploy to the local Hardhat node and write deployments/local.json
	npx hardhat run scripts/deploy.js --network localhost

backend:          ## Run the FastAPI backend (python -m app)
	cd backend && $(PY) -m app

test:             ## Run contract tests and backend tests
	npx hardhat test
	cd backend && $(PY) -m pytest -q

seed:             ## Seed demo data through the running API
	$(PY) backend/scripts/seed_demo_data.py

demo:             ## Start backend (inmemory), seed, and serve — one command
	python tasks.py demo
