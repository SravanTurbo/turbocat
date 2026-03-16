.PHONY: connectors-setup connectors-test connectors-lint connectors-format

# ── Connectors ────────────────────────────────────────────────
connectors-setup:
	cd connectors && make setup

connectors-test:
	cd connectors && make test

connectors-lint:
	cd connectors && make lint

connectors-format:
	cd connectors && make format
