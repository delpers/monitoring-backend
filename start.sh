#!/bin/bash

PORT=${PORT:-8000}  # Utilise 8000 si $PORT n'est pas défini
uvicorn main:app --host=0.0.0.0 --port=$PORT --reload
