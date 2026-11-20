FROM python:3.12-slim

WORKDIR /usr/src/app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# mysqlclient needs a compiler and the MySQL client headers
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential default-libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements first, so this slow step is cached until they change
COPY /project/requirements.txt /usr/src/app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . /usr/src/app/

# A Windows checkout can leave CRLF line endings in the script, which Linux cannot run
RUN sed -i 's/\r$//' /usr/src/app/entrypoint.sh \
    && chmod +x /usr/src/app/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/usr/src/app/entrypoint.sh"]
# The default is the production server. docker-compose.yml repeats it, and worker and beat replace it.
CMD ["gunicorn", "project.wsgi:application", "--bind", "0.0.0.0:8000", "--access-logfile", "-", "--error-logfile", "-"]