FROM python:3.12-slim

# Disable Python buffering for real-time logs
ENV PYTHONUNBUFFERED=1
ENV PYTHONIOENCODING=UTF-8

# Workdir inside container
WORKDIR /app

# Install minimal system dependencies for aiohttp
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy only dependency files first (for better caching)
COPY requirements.txt .
COPY healthcheck.sh /usr/local/bin/healthcheck.sh
RUN chmod +x /usr/local/bin/healthcheck.sh


# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy your actual application last
COPY ./eventstreamer .

# Expose nothing — it's an event client, not a server
# (But leaving here for clarity)
EXPOSE 0

# Docker healthcheck will call this small python script
# HEALTHCHECK --interval=30s --timeout=3s \
#     CMD python healthcheck.py || exit 1

# Entrypoint
CMD ["python", "main.py"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD /usr/local/bin/healthcheck.sh