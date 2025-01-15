FROM python:3.12-alpine

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apk update && \
    apk add gcc build-base libffi-dev mariadb-dev curl ca-certificates

ADD https://astral.sh/uv/install.sh /uv-installer.sh
RUN sh /uv-installer.sh && rm /uv-installer.sh
ENV PATH="/root/.local/bin/:$PATH"

RUN pip install supervisor uv

COPY . /app/
RUN uv sync --frozen
WORKDIR /app/src/app
# --no-dev

# COPY ./entrypoint.sh /app/entrypoint.sh

# ENV PYTHONPATH="$PYTHONPATH:/app/src"
ENV PATH="/app/.venv/bin:$PATH"

# ENTRYPOINT ["/app/entrypoint.sh"]

CMD [ "uvicorn", "app:create_app()", "--bind", "0.0.0.0:8000" ]
# CMD ["sleep","infinity"]
