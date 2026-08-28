.PHONY: install install-canonical verify-adult capsule verify-anchor download smoke run analyse release test lint typecheck

install:
	poetry install

install-canonical:
	python -m pip install -r environment/requirements.lock.txt
	python -m pip install --no-deps -e .

verify-adult:
	poetry run ml-repro --root . verify-design-lock --config configs/adult.yml

capsule: verify-adult
	poetry run ml-repro --root . build-anchor-capsule --config configs/adult.yml

verify-anchor: verify-adult
	poetry run ml-repro --root . verify-external-anchor --config configs/adult.yml

download: verify-adult verify-anchor
	poetry run ml-repro --root . download-data --config configs/adult.yml

smoke:
	poetry run ml-repro --root . verify-design-lock --config configs/smoke.yml
	poetry run ml-repro --root . run-all --config configs/smoke.yml
	poetry run ml-repro --root . release-status --config configs/smoke.yml

run: verify-adult verify-anchor
	poetry run ml-repro --root . run-all --config configs/adult.yml

analyse: verify-adult verify-anchor
	poetry run ml-repro --root . analyse --config configs/adult.yml

release: verify-adult verify-anchor
	poetry run ml-repro --root . release-status --config configs/adult.yml
	poetry run ml-repro --root . finalise-primary-release --config configs/adult.yml

test:
	poetry run pytest

lint:
	poetry run ruff check .

typecheck:
	poetry run mypy src
