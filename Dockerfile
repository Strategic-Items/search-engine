FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY requirements.lock ./
COPY search_engine ./search_engine
RUN pip install --no-cache-dir -r requirements.lock && \
    pip install --no-cache-dir --no-deps . && \
    useradd --create-home appuser
USER appuser
EXPOSE 8092
CMD ["uvicorn", "search_engine.api:app", "--host", "0.0.0.0", "--port", "8092"]
