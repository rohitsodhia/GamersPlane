FROM python:3.8-alpine

WORKDIR /usr/src/app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apk update && \
    apk add gcc build-base libffi-dev mariadb-dev py-bcrypt

RUN pip install --upgrade pip
RUN pip install supervisor pipenv
COPY ./Pipfile* /usr/src/app/
RUN pipenv install --deploy --system --dev

# COPY ./entrypoint.sh /usr/src/app/entrypoint.sh

COPY . /usr/src/app/
WORKDIR /usr/src/app/src

# ENV PYTHONPATH="$PYTHONPATH:/usr/src/app/src"
ENV DJANGO_SETTINGS_MODULE='django_conf'

# ENTRYPOINT ["/usr/src/app/entrypoint.sh"]

CMD [ "uvicorn", "app:create_app()", "--bind", "0.0.0.0:8000" ]
