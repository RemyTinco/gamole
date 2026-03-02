FROM python:3.12-slim

# Install git (needed for codebase indexing)
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv for fast dependency resolution
RUN pip install uv

# Copy all source first (packages needed for editable install)
COPY pyproject.toml ./
COPY packages/ packages/
COPY apps/api/ apps/api/

# Install project with all local packages
RUN pip install -e .

EXPOSE 3001

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3001", "--app-dir", "apps/api"]
