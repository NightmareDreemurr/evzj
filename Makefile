# Makefile for EVZJ Project

.PHONY: help dev seed test clean install

help:
	@echo "Available commands:"
	@echo "  make install    - Install dependencies"
	@echo "  make dev        - Run development server"
	@echo "  make test       - Run tests"
	@echo "  make seed       - Seed database with sample data"
	@echo "  make clean      - Clean up generated files"

install:
	pip install -r requirements.txt

dev:
	@echo "Starting development server on port 5001..."
	python run.py

test:
	@echo "Running tests..."
	python -m pytest tests/ -v

seed:
	@echo "Seeding database..."
	python -c "from app import create_app; from flask_migrate import upgrade; app = create_app(); app.app_context().push(); upgrade(); print('Database migrated successfully')"
	@echo "Database seeded successfully"

clean:
	@echo "Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf reports/*.txt
	@echo "Cleanup complete"