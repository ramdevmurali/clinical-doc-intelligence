.PHONY: help up down logs migrate seed eval-extractions probe-clinical-path replay-documents-dlq replay-extractions-dlq replay-validation-dlq replay-fhir-dlq

help:
	@echo "Clinical Document Intelligence skeleton commands"
	@echo "  make up                         Start local infrastructure"
	@echo "  make down                       Stop local infrastructure"
	@echo "  make migrate                    Apply database schema"
	@echo "  make seed                       Seed demo synthetic documents"
	@echo "  make eval-extractions           Run extraction evaluation harness"
	@echo "  make probe-clinical-path        Probe the full document workflow"

up:
	docker compose -f infra/docker-compose.yml up -d

down:
	docker compose -f infra/docker-compose.yml down

logs:
	docker compose -f infra/docker-compose.yml logs -f

migrate:
	python scripts/migrate_db.py

seed:
	python scripts/seed_demo_documents.py

eval-extractions:
	python scripts/eval_extractions.py

probe-clinical-path:
	python scripts/probe_clinical_path.py

replay-documents-dlq:
	python scripts/replay_documents_dlq.py

replay-extractions-dlq:
	python scripts/replay_extractions_dlq.py

replay-validation-dlq:
	python scripts/replay_validation_dlq.py

replay-fhir-dlq:
	python scripts/replay_fhir_dlq.py
