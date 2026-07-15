FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# install dependencies in their own layer so rebuilds after code edits
# don't re-download everything - this layer only invalidates when
# requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# run as a non-root user. COPY writes files as root by default, which
# breaks collectstatic overwriting them later - so create the user first
# and copy with --chown. /app itself also has to be writable, because the
# GSI logging service opens countertrak.log relative to the workdir.
RUN useradd --create-home app && chown app:app /app
COPY --chown=app:app . .
USER app

EXPOSE 8000 3000

# default command runs the Django dev server; the gsi service in
# docker-compose.yml overrides this with the GSI listener
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
