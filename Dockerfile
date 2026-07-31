FROM python:3.12-slim

# Debian slim images ship without /usr/share/zoneinfo, so ZoneInfo("Europe/Dublin")
# raises ZoneInfoNotFoundError and every timestamp would fail to parse. The
# pure-Python tzdata package fixes it with no compiler and no system packages.
# Deliberately unpinned: this collector runs for years, and stale timezone rules
# would silently corrupt timestamps across a DST change.
RUN pip install --no-cache-dir tzdata

WORKDIR /app
COPY esb_outages/ /app/esb_outages/
COPY tests/ /app/tests/

RUN useradd --create-home --uid 1000 esb \
    && mkdir -p /data \
    && chown -R esb:esb /data /app
USER esb

VOLUME ["/data"]
ENV ESB_DATA_DIR=/data \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Unbuffered output matters: Synology's Task Scheduler emails whatever the
# process printed, and buffered output can be lost when a run fails.
ENTRYPOINT ["python", "-m", "esb_outages"]
CMD ["poll"]
