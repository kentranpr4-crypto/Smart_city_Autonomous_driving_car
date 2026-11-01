# Smart City V2X — reproducible commands. Run `make setup` once (needs network).
PY := .venv/bin/python
.PHONY: setup check test test-physics build-web smoke-web reproduce clean
setup:
	python3 -m venv .venv
	$(PY) -m pip install --quiet --upgrade pip
	$(PY) -m pip install --quiet --require-hashes -r requirements.lock
	cd web && npm ci --ignore-scripts --no-audit --no-fund
check:
	$(PY) scripts/check_repo.py
test:
	$(PY) -m pytest
test-physics:
	$(PY) -m pytest -m phy
build-web:
	cd web && npm run build
smoke-web: build-web
	node scripts/web_smoke.cjs
reproduce:
	@test -n "$(RUN)" || (echo "usage: make reproduce RUN=<scenario.yaml> SEED=<n>"; exit 2)
	$(PY) -m backend.run $(RUN) --seed $(SEED) --out results/reproduce --verify-hash $(EXPECT)
clean:
	rm -rf results web/dist .pytest_cache .hypothesis
