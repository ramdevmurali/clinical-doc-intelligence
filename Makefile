.PHONY: help up down logs migrate seed validate-golden-set eval-extractions probe-clinical-path replay-documents-dlq replay-extractions-dlq replay-validation-dlq replay-fhir-dlq

help:
	@echo "Clinical Document Intelligence skeleton commands"
	@echo "  make up                         Start local infrastructure"
	@echo "  make down                       Stop local infrastructure"
	@echo "  make migrate                    Apply database schema"
	@echo "  make seed                       Seed demo synthetic documents"
	@echo "  make validate-golden-set        Validate golden notes and labels"
	@echo "  make eval-extractions           Run extraction evaluation harness"
	@echo "  make probe-clinical-path        Probe the full document workflow"

up:
	docker compose -f infra/docker-compose.yml up -d

down:
	docker compose -f infra/docker-compose.yml down

logs:
	docker compose -f infra/docker-compose.yml logs -f

migrate:
	python3 scripts/migrate_db.py

seed:
	python3 scripts/seed_demo_documents.py

validate-golden-set:
	python3 scripts/validate_golden_set.py

eval-extractions:
	python3 scripts/eval_extractions.py

probe-clinical-path:
	python3 scripts/probe_clinical_path.py

replay-documents-dlq:
	python3 scripts/replay_documents_dlq.py

replay-extractions-dlq:
	python3 scripts/replay_extractions_dlq.py

replay-validation-dlq:
	python3 scripts/replay_validation_dlq.py

replay-fhir-dlq:
	python3 scripts/replay_fhir_dlq.py
