FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY manage.py ./
COPY config ./config
COPY gado ./gado

# Baked into the image, not done at boot: a container that has to collect static
# on every start is slower to come up and fails later, when it is already
# serving. DJANGO_SECRET_KEY is only needed for the command to run.
RUN DJANGO_SECRET_KEY=build python manage.py collectstatic --noinput

EXPOSE 8790

# Migrations are NOT run here. They are a deliberate step -- `manage.py migrate`
# from the deploy -- because a container that migrates on boot will happily run
# a schema change from any replica, at any restart, with nobody watching.
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8790", "--workers", "3", "--timeout", "60", \
     "--access-logfile", "-", "--error-logfile", "-"]
