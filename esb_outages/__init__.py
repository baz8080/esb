"""Long-term collector for ESB Networks (Ireland) power outage data.

ESB purges outage events a few hours after restoration and offers no historical
archive, so the only way to build a dataset is to snapshot the live API on a
schedule. See README.md for deployment.
"""

__version__ = "1.0.0"
