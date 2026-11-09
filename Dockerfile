FROM python:3.12-slim

LABEL maintainer="Elvis Freitas Lopes Herllain <4459357+evslopes@users.noreply.github.com>"
LABEL description="SRE & Tier-3 Sustainment Incident Intelligence Console (Dash + Plotly)"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd -r sreapp && useradd -r -g sreapp sreapp

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir . && \
    mkdir -p /app/data /app/reports && \
    chown -R sreapp:sreapp /app

USER sreapp:sreapp

EXPOSE 8050

CMD ["gunicorn", "--bind", "0.0.0.0:8050", "--workers", "2", "--threads", "4", "sre_analytics.app:server"]
