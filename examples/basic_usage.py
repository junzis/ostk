"""Example: Reconstruct flight trajectory using ostk (OpenSky ToolKit).

This example demonstrates how to use ostk to rebuild a flight
trajectory from raw ADS-B messages with higher accuracy than using
pre-computed state vectors.
"""

# %%
import matplotlib.pyplot as plt
from pyopensky.trino import Trino

from ostk import rebuild

trino = Trino()

# %%
# Using pyopensky history
traj_history = trino.history(
    icao24="485A32",
    start="2025-11-08 12:00:00",
    stop="2025-11-08 15:00:00",
)

# %%
# trajectory reconstruction
traj_rebuild = rebuild(
    icao24="485A32",
    start="2025-11-08 12:00:00",
    stop="2025-11-08 15:00:00",
    trino=trino,
)


# %%
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3), sharex=True, sharey=True)
ax1.plot(
    traj_history.time,
    traj_history.baroaltitude,
    label="history trajectory",
)
ax1.legend()
ax1.set_ylabel("Barometric Altitude (m)")
ax1.tick_params(axis="x", labelrotation=30)

ax2.plot(
    traj_rebuild.time,
    traj_rebuild.baroaltitude,
    label="rebuilt trajectory",
    color="tab:orange",
)
ax2.legend()
ax2.tick_params(axis="x", labelrotation=30)
plt.tight_layout()
plt.show()

# %%
