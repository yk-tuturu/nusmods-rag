FROM python:3.12-slim

WORKDIR /app

# CPU-only torch build — the default PyPI wheel drags in CUDA libraries we'll
# never use on a VM with no GPU, and roughly doubles image size for nothing.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bake the embedding model into the image so cold starts don't hit the network.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY api.py refresh.sh ./
COPY src/ src/
RUN chmod +x refresh.sh

# data/ is intentionally NOT copied in — it's scraped/derived, gitignored, and
# under Disqus's ToS should stay off any registry. Mount it as a volume instead.

EXPOSE 8000
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
