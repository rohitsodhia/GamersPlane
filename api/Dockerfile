FROM python:3.13-alpine

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apk update && \
    apk add gcc build-base libffi-dev mariadb-dev curl ca-certificates

ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh
ENV PATH="/root/.local/bin/:$PATH"

RUN pip install supervisor

COPY pyproject.toml uv.lock /app/
RUN uv sync --frozen --no-install-project --no-dev

COPY . /app/
RUN uv sync --frozen --no-install-project --no-dev && \
    uv pip install hatchling && \
    uv sync --frozen --no-editable --no-build-isolation
# --no-dev
# COPY ./entrypoint.sh /app/entrypoint.sh

# ENV PYTHONPATH="$PYTHONPATH:/app/src"
ENV PATH="/app/.venv/bin:$PATH"

# ENTRYPOINT ["/app/entrypoint.sh"]

WORKDIR /app/src/app
CMD [ "uvicorn", "--factory", "main:create_app", "--host", "0.0.0.0", "--port", "8000" ]
# CMD ["sleep","infinity"]
