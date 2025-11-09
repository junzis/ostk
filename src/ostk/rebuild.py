"""Trajectory reconstruction from raw ADS-B messages."""

# %%
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pyModeS as pms
from pyopensky.schema import PositionData4, VelocityData4
from pyopensky.time import timelike, to_datetime
from pyopensky.trino import Trino
from sqlalchemy import select


# %%
def rebuild(
    icao24: str,
    start: timelike,
    stop: timelike,
    trino: Trino | None = None,
    cached: bool = True,
    compress: bool = False,
    **kwargs: Any,
) -> None | pd.DataFrame:
    """Rebuild trajectory from raw ADS-B position and velocity messages.

    This function queries the PositionData4 and VelocityData4 tables to
    reconstruct a flight trajectory by decoding raw ADS-B messages and
    combining position and velocity information.

    Args:
        icao24: A string identifying the transponder code of the aircraft
        start: A string (default to UTC), epoch or datetime (native
            Python or pandas) for the start of the flight
        stop: A string (default to UTC), epoch or datetime (native Python
            or pandas) for the end of the flight
        trino: A pyopensky Trino instance for database access.
            Default to None, when a new Trino() is created.
        cached: (default: True) switch to False to force a new request to
            the database regardless of the cached files. This option also
            deletes previous cache files
        compress: (default: False) compress cache files. Reduces disk
            space occupied at the expense of slightly increased time
            to load

    Returns:
        A pandas DataFrame with reconstructed trajectory data containing
        time, icao24, lat, lon, baroaltitude, velocity, heading, and
        vertrate columns. Returns None if no data is available.

    Example:
        >>> from openskytools import rebuild
        >>> df = rebuild(
        ...     icao24="400A0E",
        ...     start="2023-01-03 16:00:00",
        ...     stop="2023-01-03 20:00:00"
        ... )

    Note:
        This method provides more accurate position decoding from CPR
        (Compact Position Reporting), resulting in fewer outliers and
        position jumps through better handling of message pairs for
        position calculation. However, it is slower than the history()
        method due to message decoding overhead and only supports
        filtering by icao24 and time range.
    """

    start_ts = to_datetime(start)
    stop_ts = to_datetime(stop)

    if trino is None:
        trino = Trino()

    # Query position data
    pos = trino.query(
        select(PositionData4)
        .with_only_columns(
            PositionData4.icao24,
            PositionData4.mintime,
            PositionData4.rawmsg,
            PositionData4.lat,
            PositionData4.lon,
            PositionData4.alt,
            PositionData4.odd,
            PositionData4.surface,
        )
        .where(PositionData4.icao24.like(icao24.lower()))
        .where(PositionData4.mintime >= start_ts)
        .where(PositionData4.mintime <= stop_ts)
        .where(PositionData4.hour >= start_ts.floor("1h"))
        .where(PositionData4.hour <= stop_ts.ceil("1h"))
        .order_by(PositionData4.mintime),
        cached=cached,
        compress=compress,
    )

    # Query velocity data
    spd = trino.query(
        select(VelocityData4)
        .with_only_columns(
            VelocityData4.icao24,
            VelocityData4.mintime,
            VelocityData4.rawmsg,
            VelocityData4.velocity,
            VelocityData4.heading,
            VelocityData4.vertrate,
        )
        .where(VelocityData4.icao24.like(icao24.lower()))
        .where(VelocityData4.mintime >= start_ts)
        .where(VelocityData4.mintime <= stop_ts)
        .where(VelocityData4.hour >= start_ts.floor("1h"))
        .where(VelocityData4.hour <= stop_ts.ceil("1h"))
        .order_by(VelocityData4.mintime),
        cached=cached,
        compress=compress,
    )

    if pos.shape[0] == 0 or spd.shape[0] == 0:
        return None

    # Preprocess position data
    pos = (
        pos.drop_duplicates("rawmsg")
        # .query("lat==lat")  # Filter out NaN latitudes
        .eval("baroaltitude=alt")
        .assign(time=lambda x: pd.to_datetime(x.mintime, unit="s"))
    )

    # Preprocess velocity data
    spd = (
        spd.drop_duplicates("rawmsg")
        .dropna()
        .assign(time=lambda x: pd.to_datetime(x.mintime, unit="s"))
    )

    # Pair odd and even CPR frames for accurate position decoding
    pos_new = (
        pd.concat(
            [
                pd.merge_asof(
                    pos.query("odd")[
                        ["time", "icao24", "lat", "lon", "mintime", "rawmsg"]
                    ],
                    pos.query("not odd")[["time", "icao24", "mintime", "rawmsg"]],
                    on="time",
                    by="icao24",
                    tolerance=pd.Timedelta("10s"),
                ),
                pd.merge_asof(
                    pos.query("not odd")[
                        ["time", "icao24", "lat", "lon", "mintime", "rawmsg"]
                    ],
                    pos.query("odd")[["time", "icao24", "mintime", "rawmsg"]],
                    on="time",
                    by="icao24",
                    tolerance=pd.Timedelta("10s"),
                ),
            ]
        )
        .sort_values("time")
        .dropna()
    )

    # Decode positions from paired CPR messages
    tcs = []
    lats = []
    lons = []
    alts = []

    for _, r in pos_new.iterrows():
        tcs.append(pms.typecode(r.rawmsg_x))
        alts.append(pms.adsb.altitude(r.rawmsg_x))

        try:
            latlon = pms.adsb.position(r.rawmsg_x, r.rawmsg_y, r.mintime_x, r.mintime_y)

            if latlon is not None:
                lats.append(latlon[0])
                lons.append(latlon[1])
            else:
                lats.append(None)
                lons.append(None)
        except Exception:
            lats.append(r.lat)
            lons.append(r.lon)

    # Add decoded positions and create reference points for validation
    pos_new = (
        pos_new.assign(tc=tcs, lat=lats, lon=lons, alt=alts)
        .assign(
            lat_ref_1=lambda x: x.lat.shift(5),
            lon_ref_1=lambda x: x.lon.shift(5),
        )
        .assign(
            lat_ref_2=lambda x: x.lat.shift(10),
            lon_ref_2=lambda x: x.lon.shift(10),
        )
    )

    # Decode single messages with reference positions for validation
    latlon_1 = []
    latlon_2 = []
    surface_speed = []
    surface_track = []

    r_prev = None
    for _, r in pos_new.iterrows():
        if r_prev is None:
            r_prev = r

        ll1 = pms.adsb.position_with_ref(
            r.rawmsg_x,
            lat_ref=r.lat_ref_1 if r.lat_ref_1 is not None else r.lat,
            lon_ref=r.lon_ref_1 if r.lon_ref_1 is not None else r.lon,
        )
        ll2 = pms.adsb.position_with_ref(
            r.rawmsg_x,
            lat_ref=r.lat_ref_2 if r.lat_ref_2 is not None else r_prev.lat,
            lon_ref=r.lon_ref_2 if r.lon_ref_2 is not None else r_prev.lon,
        )
        latlon_1.append(ll1)
        latlon_2.append(ll2)

        # decode surface velocity
        if 5 <= r.tc <= 8:
            gs, trk, _, _ = pms.adsb.surface_velocity(r.rawmsg_x)
        else:
            gs, trk = None, None

        surface_speed.append(gs)
        surface_track.append(trk)

        r_prev = r

    latlon_1 = np.array(latlon_1)
    latlon_2 = np.array(latlon_2)
    surface_speed = np.array(surface_speed)
    surface_track = np.array(surface_track)

    # Filter outliers by comparing decoded positions with reference positions
    pos_new = (
        pos_new.assign(lat_1=latlon_1[:, 0], lon_1=latlon_1[:, 1])
        .assign(lat_2=latlon_2[:, 0], lon_2=latlon_2[:, 1])
        .assign(surface_speed=surface_speed, surface_track=surface_track)
        .eval("dlat_1=abs(lat-lat_1)")
        .eval("dlon_1=abs(lon-lon_1)")
        .eval("dlat_2=abs(lat-lat_2)")
        .eval("dlon_2=abs(lon-lon_2)")
        .query("dlat_1<0.1 and dlon_1<0.1 and dlat_2<0.1 and dlon_2<0.1")
    )

    # Merge position and velocity data
    state_vector = pd.merge_asof(
        (
            pos_new[
                [
                    "time",
                    "icao24",
                    "lat",
                    "lon",
                    "alt",
                    "surface_speed",
                    "surface_track",
                    "tc",
                ]
            ]
            .rename(columns={"alt": "baroaltitude"})
            .eval("baroaltitude = baroaltitude * 0.3048")  # Convert to meters
        ),
        spd.drop("rawmsg", axis=1),
        on="time",
        by="icao24",
        tolerance=pd.Timedelta("3s"),
        direction="nearest",
    ).sort_values("time")

    # Assign surface_speed to velocity for surface messages in a vectorized way
    mask_surface = (state_vector.tc >= 5) & (state_vector.tc <= 8)

    state_vector["velocity"] = np.where(
        mask_surface, state_vector["surface_speed"], state_vector["velocity"]
    )
    state_vector["heading"] = np.where(
        mask_surface, state_vector["surface_track"], state_vector["heading"]
    )
    state_vector["vertrate"] = np.where(mask_surface, 0, state_vector["vertrate"])

    state_vector = state_vector[
        [
            "time",
            "icao24",
            "lat",
            "lon",
            "baroaltitude",
            "velocity",
            "heading",
            "vertrate",
        ]
    ]

    return state_vector
