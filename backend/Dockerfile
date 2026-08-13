FROM python:3.12-slim

WORKDIR /app

# Embeddings now come from OpenAI's API (see src/embeddings.py) rather than
# a locally-loaded sentence-transformers/torch model — no GPU-sized deps or
# baked-in model download needed anymore.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api.py refresh.sh ./
COPY src/ src/
RUN chmod +x refresh.sh

# data/ is intentionally NOT copied in — it's scraped/derived, gitignored, and
# under Disqus's ToS should stay off any registry. Mount it as a volume instead.

EXPOSE 8000
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
