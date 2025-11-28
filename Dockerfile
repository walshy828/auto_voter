FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    wget \
    curl \
    expect \
    iproute2 \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install ExpressVPN
# Note: You may need to update this URL to the latest version from expressvpn.com
RUN wget -q https://www.expressvpn.works/clients/linux/expressvpn_3.70.0.2-1_amd64.deb -O expressvpn.deb && \
    dpkg -i expressvpn.deb && \
    rm expressvpn.deb

# Copy requirements and install
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /app/requirements.txt

# Copy app and scripts
COPY . /app
RUN chmod +x /app/entrypoint.sh /app/activate_expressvpn.exp

ENV PYTHONPATH=/app
ENV FLASK_APP=app.api:app

EXPOSE 8080

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app.api:app", "--workers", "1", "--worker-class", "gevent", "--threads", "4"]
