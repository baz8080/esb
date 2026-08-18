"""Static status site for the collected ESB Networks outage data.

Reads the SQLite index that `esb_outages` rebuilds from the raw JSONL logs and
writes a self-contained site to `out/site/`. Standard library only, like the
collector.
"""

__version__ = "1.0.0"
