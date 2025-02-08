.DEFAULT_GOAL := help

SHELL=bash

.PHONY: fmt
fmt:  ## Run autoformatting and linting
	@uv run pre-commit run --all-files

.PHONY: clean
clean:  ## Clean up caches and build artifacts
	@rm -rf .ruff_cache/
	@rm -rf .venv/
	@rm -rf ./src/mewline/dist
	@rm -rf ./src/mewline.egg-info
	@find . -type f -name '*.py[co]' -delete -or -type d -name __pycache__ -delete

.PHONY: help
help:  ## Display this help screen
	@echo -e "\033[1mAvailable commands:\033[0m"
	@grep -E '^[a-z.A-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' | sort
