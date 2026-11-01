.PHONY: run clean

# Run the FastAPI app with uvicorn
run:
	uvicorn practices.practice_05.service.app:app --reload --host 0.0.0.0 --port 8000

# Remove persisted data
clean:
	rm -f practices/practice_05/service/data/subscribers.json
