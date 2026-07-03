# simulation/interference.py — Interference Injection Engine
# This file is the "glue" between devices.py and environment.py.
#
# Each tick, it:
#   1. Moves Bluetooth interferers to their next frequency-hopped channel
#   2. Combines the power of every active interferer per channel (multiple interferers can overlap on the same channel — their
#      power must be summed, not just picked from one)
#   3. Produces an interference_map: { channel_id: total_power_dbm } which environment.py uses to calculate SINR
#
# This separation keeps responsibilities clean:
#   devices.py     -> WHO exists (Wi-Fi APs, Bluetooth devices)
#   interference.py -> WHERE they are right now + HOW MUCH power they add
#   environment.py  -> WHAT EFFECT that has on signal quality (SINR, loss)

import numpy as np
from typing import Dict, List
import config
from simulation.devices import Interferer, InterfererType

class InterferenceEngine:
    """
    Computes the total interference power on every channel, every tick.

    This class doesn't own the interferers — they live in DeviceManager.
    It just reads their state, updates Bluetooth hopping, and aggregates
    power per channel.
    """

    def __init__(self):
        # Seeded RNG — keep consistent with environment.py and devices.py
        self.rng = np.random.default_rng(seed=123)

        # Optional: scenario control. This lets main.py simulate interference
        # appearing partway through the run (e.g. "Wi-Fi turns on at tick 100") rather than being present for the entire simulation.
        # Useful for testing how fast ACS reacts to NEW interference.
        self.scenario_active = True

    # MAIN TICK UPDATE
    def update(self, interferers: List[Interferer], current_tick: int) -> Dict[int, float]:
        """
        Run one tick of interference simulation.

        Parameters
        ----------
        interferers : list of Interferer
            All interferers in the simulation (from DeviceManager).
        current_tick : int
            The current simulation tick — used for time-based scenarios
            (e.g. turning interference on/off at specific times).

        Returns
        -------
        dict
            { channel_id (int): total_interference_power_dbm (float) }
            Every channel from 1 to NUM_CHANNELS will have an entry,
            even if it's just the noise floor (no interferer present).
        """

        # Step 1: Update Bluetooth frequency hopping for this tick
        self._update_bluetooth_hopping(interferers)

        # Step 2: Apply any time-based scenario rules (optional)
        self._apply_scenario_rules(interferers, current_tick)

        # Step 3: Aggregate power per channel across all active interferers
        interference_map = self._aggregate_power_per_channel(interferers)

        return interference_map

    # STEP 1: BLUETOOTH FREQUENCY HOPPING
    def _update_bluetooth_hopping(self, interferers: List[Interferer]):
        """
        Move each Bluetooth interferer to a new random channel.

        Real Bluetooth (Classic) hops ~1600 times per second across 79
        channels in the 2.4 GHz band. In our simulation, one tick = 100ms,
        so we approximate this by picking a new random channel for each
        Bluetooth interferer every tick — capturing the KEY property that
        matters for this simulation: Bluetooth interference is unpredictable
        and moves around, unlike Wi-Fi which sits still.
        """
        for interferer in interferers:
            if interferer.interferer_type == InterfererType.BLUETOOTH:
                if interferer.is_active:
                    new_channel = int(self.rng.integers(1, config.NUM_CHANNELS + 1))
                    interferer.current_hop_channel = new_channel

    # STEP 2: TIME-BASED SCENARIO RULES (OPTIONAL)
    def _apply_scenario_rules(self, interferers: List[Interferer], current_tick: int):
        """
        Optionally toggle interferers on/off at specific simulation times.

        This is useful for your evaluation chapter — e.g. you might want to
        show "interference starts at tick 50" so the dashboard clearly shows
        the BEFORE (clean) and AFTER (degraded -> recovered) phases, which
        makes the ACS recovery behaviour much easier to see and screenshot
        for your report.

        Currently a placeholder — by default everything stays active the
        whole simulation (self.scenario_active = True does nothing here).
        You can extend this method later, e.g.:

            if current_tick == 50:
                interferers[0].is_active = True   # Wi-Fi #1 switches on
            if current_tick == 300:
                interferers[0].is_active = False  # Wi-Fi #1 switches off
        """
        # No-op by default — all interferers remain active throughout.
        # This keeps the first working version simple. We can add timed scenarios later once the core pipeline is verified end-to-end.
        pass

    # STEP 3: POWER AGGREGATION PER CHANNEL
    def _aggregate_power_per_channel(self, interferers: List[Interferer]) -> Dict[int, float]:
        """
        Sum interference power on each channel from all active interferers.

        Power in dBm cannot be added directly (it's a logarithmic unit).
        We must convert to linear milliwatts, sum, then convert back to dBm.

        Example: if a Wi-Fi AP (-20 dBm) and a Bluetooth device (-40 dBm)
        both affect channel 6, the combined interference is dominated by
        the Wi-Fi signal (since -20 dBm is far stronger than -40 dBm),
        but the BT contribution still adds a small amount.
        """
        # Start every channel at "no interference" (just background noise). We track power in milliwatts during summation, convert at the end.
        channel_power_mw: Dict[int, float] = {
            ch: _dbm_to_mw(config.NOISE_FLOOR_DBM)
            for ch in range(1, config.NUM_CHANNELS + 1)
        }

        for interferer in interferers:
            if not interferer.is_active:
                continue   # Skip inactive interferers entirely

            affected_channels = interferer.get_affected_channels()
            interferer_power_mw = _dbm_to_mw(interferer.tx_power_dbm)

            for ch in affected_channels:
                channel_power_mw[ch] += interferer_power_mw

        # Convert every channel's total power back to dBm for environment.py
        interference_map_dbm = {
            ch: _mw_to_dbm(power_mw)
            for ch, power_mw in channel_power_mw.items()
        }

        return interference_map_dbm

# PRIVATE HELPER FUNCTIONS
# Same dBm <-> mW conversion logic as environment.py.
# Duplicated intentionally (rather than imported) to keep this module
# self-contained — but if you prefer, these could be moved into a shared utils.py file later.

def _dbm_to_mw(dbm: float) -> float:
    """Convert dBm to milliwatts: P(mW) = 10 ^ (P(dBm) / 10)"""
    return 10 ** (dbm / 10.0)


def _mw_to_dbm(mw: float) -> float:
    """Convert milliwatts to dBm: P(dBm) = 10 * log10(P(mW))"""
    if mw <= 0:
        return -200.0
    return 10.0 * np.log10(mw)