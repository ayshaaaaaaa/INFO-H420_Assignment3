FROM apache/airflow:3.0.6-python3.12

USER airflow

RUN pip install --no-cache-dir \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-3.0.6/constraints-3.12.txt" \
    "apache-airflow==3.0.6" \
    pymupdf4llm \
    openai \
    requests
