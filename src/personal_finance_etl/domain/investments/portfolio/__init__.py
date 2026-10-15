"""Investment portfolio aggregation and snapshot analytics.

Owns
----
- Portfolio daily snapshot construction.
- Portfolio, asset-class, subtype, geography, and sector aggregation.
- Tax harvest analytics and outperforming lot analytics.

Does not own
-------------
- Multiprocessing coordination (owned by application.investments).
- UI reporting charts (owned by presentation).
"""

