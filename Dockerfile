FROM python:3.12-slim

WORKDIR /app

# Install real TrueType fonts (DejaVu) so text overlays render with proper
# typography/weights instead of silently falling back to PIL's bitmap default.
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY src/ src/
COPY examples/ examples/

ENTRYPOINT ["python", "-m", "src.cli"]
