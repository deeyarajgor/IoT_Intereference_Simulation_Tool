# algorithms/acs.py — Adaptive Channel Selection Algorithms
#   ALGORITHM 1: Threshold-Based Channel Switching
#       Source: Vatankhah, S. & Liscano, R. (2024) / Mseddi et al. (2024)
#       Logic: If current channel's SINR < threshold, scan all channels
#              and jump to whichever single channel currently has the
#              HIGHEST SINR. Simple, fast, low computation, good for
#              resource-constrained IoT hardware.
#
#   ALGORITHM 2: Weighted Channel Scoring (Quality Estimation)
#       Source: Mseddi et al. (2024)
#       Logic: Instead of looking at SINR alone, score every candidate
#              channel using a WEIGHTED combination of:
#                 - current SINR              (signal quality right now)
#                 - recent stability           (avoid channels that look
#                                                good now but were bad
#                                                recently — avoids "flapping")
#                 - channel utilisation        (avoid channels other devices
#                                                are already crowding onto)
#              Pick the channel with the highest overall score.

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Dict
import numpy as np
import config
from simulation.environment import ChannelEnvironment, ChannelState
from simulation.devices import IoTDevice, DeviceManager


# RESULT CONTAINER
@dataclass
class SwitchDecision:
    """
    The outcome of an ACS algorithm evaluating one device.

    Returned by every algorithm's decide() method so main.py and the
    logger can record WHAT was decided and WHY, regardless of which
    algorithm produced it.
    """
    device_id: int
    should_switch: bool          # True if the algorithm recommends switching
    target_channel: Optional[int]  # The channel to switch to (None if no switch)
    reason: str                  # Human-readable explanation, useful for logs and for your evaluation chapter's discussion


# ABSTRACT BASE CLASS — shared interface for both algorithms

class BaseACSAlgorithm(ABC):
    """
    Common interface that both ACS algorithms must implement.

    Using an abstract base class here means main.py can hold a reference
    to "whichever algorithm is currently active" without caring which one
    it actually is — this is what allows you to run the SAME simulation
    twice (once per algorithm) and compare results fairly, since every
    other part of the pipeline (environment, devices, interference) stays
    identical between runs.
    """

    name: str = "BaseACS"   # Overridden by each subclass for logging/labels

    @abstractmethod
    def decide(
        self,
        device: IoTDevice,
        environment: ChannelEnvironment,
        all_devices: List[IoTDevice]
    ) -> SwitchDecision:
        """
        Decide whether a given device should switch channels, and to where.

        Parameters
        ----------
        device : IoTDevice
            The device currently flagged by the Monitor as needing a decision.
        environment : ChannelEnvironment
            Gives access to all 16 channels' current SINR/interference state.
        all_devices : list of IoTDevice
            All devices in the simulation — needed by Algorithm 2 to check
            channel utilisation (how many devices are already on each channel).

        Returns
        -------
        SwitchDecision
        """
        raise NotImplementedError

# ALGORITHM 1: THRESHOLD-BASED CHANNEL SWITCHING
class ThresholdBasedACS(BaseACSAlgorithm):

    name = "Threshold-Based ACS"

    def decide(
        self,
        device: IoTDevice,
        environment: ChannelEnvironment,
        all_devices: List[IoTDevice]
    ) -> SwitchDecision:

        current_channel = environment.get_channel(device.channel_id)

        # STEP 1: Check if a switch is even needed
        # Note: by the time this method is called, the Monitor has already
        # confirmed the device has been degraded for the full detection window (500ms). This check is a final safety confirmation.
        if current_channel.sinr_db >= config.SINR_THRESHOLD_DB:
            return SwitchDecision(
                device_id=device.device_id,
                should_switch=False,
                target_channel=None,
                reason="Current channel SINR is acceptable; no switch needed."
            )

        # STEP 2: Scan all channels and find the one with highest SINR
        all_channels = environment.get_all_channels()

        # Sort channels by SINR descending; the first entry is the best.
        best_channel = max(all_channels, key=lambda ch: ch.sinr_db)

        # STEP 3: Validate the candidate before committing to a switch
        # Avoid switching to a channel that's barely better than the current one — that would waste a switch (which has its own brief outage
        # cost) for negligible gain. Must clear ACS_MIN_SINR_TO_ACCEPT.
        if best_channel.sinr_db < config.ACS_MIN_SINR_TO_ACCEPT:
            return SwitchDecision(
                device_id=device.device_id,
                should_switch=False,
                target_channel=None,
                reason=(
                    f"Best available channel ({best_channel.channel_id}) SINR "
                    f"{best_channel.sinr_db:.1f} dB still below acceptance "
                    f"threshold {config.ACS_MIN_SINR_TO_ACCEPT} dB."
                )
            )

        # Don't switch to the channel the device is already on
        if best_channel.channel_id == device.channel_id:
            return SwitchDecision(
                device_id=device.device_id,
                should_switch=False,
                target_channel=None,
                reason="Current channel is already the best available channel."
            )

        # STEP 4: Approve the switch
        return SwitchDecision(
            device_id=device.device_id,
            should_switch=True,
            target_channel=best_channel.channel_id,
            reason=(
                f"Current channel SINR {current_channel.sinr_db:.1f} dB below "
                f"threshold {config.SINR_THRESHOLD_DB} dB. Switching to channel "
                f"{best_channel.channel_id} (SINR {best_channel.sinr_db:.1f} dB)."
            )
        )


# ALGORITHM 2: WEIGHTED CHANNEL SCORING
class WeightedScoringACS(BaseACSAlgorithm):

    name = "Weighted Scoring ACS"

    # WEIGHTS — tunable constants for the scoring formula
    # These sum to a sensible balance: SINR matters most (it's the direct measure of channel quality), stability matters somewhat (avoids
    # short-term noise), and utilisation is a smaller corrective factor.
    WEIGHT_SINR = 0.6
    WEIGHT_STABILITY = 0.25
    WEIGHT_UTILISATION = 0.15

    def decide(
        self,
        device: IoTDevice,
        environment: ChannelEnvironment,
        all_devices: List[IoTDevice]
    ) -> SwitchDecision:

        current_channel = environment.get_channel(device.channel_id)

        # STEP 1: Check if a switch is even needed (same as Algorithm 1)
        if current_channel.sinr_db >= config.SINR_THRESHOLD_DB:
            return SwitchDecision(
                device_id=device.device_id,
                should_switch=False,
                target_channel=None,
                reason="Current channel SINR is acceptable; no switch needed."
            )

        # STEP 2: Build channel utilisation counts (devices per channel)
        # Needed for the utilisation_penalty factor — channels already crowded with devices score lower, spreading load more evenly.
        utilisation: Dict[int, int] = {}
        for d in all_devices:
            utilisation[d.channel_id] = utilisation.get(d.channel_id, 0) + 1

        # STEP 3: Score every channel
        all_channels = environment.get_all_channels()
        scored_channels = []

        for channel in all_channels:
            score = self._compute_score(channel, utilisation)
            scored_channels.append((channel, score))

        # Sort descending by score; best candidate is first
        scored_channels.sort(key=lambda pair: pair[1], reverse=True)
        best_channel, best_score = scored_channels[0]

        # STEP 4: Validate the candidate before committing to a switch
        if best_channel.sinr_db < config.ACS_MIN_SINR_TO_ACCEPT:
            return SwitchDecision(
                device_id=device.device_id,
                should_switch=False,
                target_channel=None,
                reason=(
                    f"Best scored channel ({best_channel.channel_id}) SINR "
                    f"{best_channel.sinr_db:.1f} dB still below acceptance "
                    f"threshold {config.ACS_MIN_SINR_TO_ACCEPT} dB."
                )
            )

        if best_channel.channel_id == device.channel_id:
            return SwitchDecision(
                device_id=device.device_id,
                should_switch=False,
                target_channel=None,
                reason="Current channel already scores highest; no switch needed."
            )

        # STEP 5: Approve the switch
        return SwitchDecision(
            device_id=device.device_id,
            should_switch=True,
            target_channel=best_channel.channel_id,
            reason=(
                f"Current channel SINR {current_channel.sinr_db:.1f} dB below "
                f"threshold. Switching to channel {best_channel.channel_id} "
                f"(score {best_score:.2f}, SINR {best_channel.sinr_db:.1f} dB)."
            )
        )

    # SCORING HELPER
    def _compute_score(
        self,
        channel: ChannelState,
        utilisation: Dict[int, int]
    ) -> float:
        """
        Compute the composite score for one candidate channel.

        All three sub-scores are normalised to roughly the [0, 1] range
        before weighting, so the weights (0.6 / 0.25 / 0.15) behave
        predictably regardless of the raw units involved (dB vs. device count).
        """

        # Factor 1: SINR score 
        # Normalise SINR against a realistic range (0 dB = unusable, 30 dB = excellent). Clipped to [0, 1].
        sinr_score = np.clip(channel.sinr_db / 30.0, 0.0, 1.0)

        # Factor 2: Stability score
        # Based on the standard deviation of the channel's recent SINR history (sinr_history, last 10 ticks from environment.py).
        # Lower variance = more stable = higher score.
        if len(channel.sinr_history) >= 3:
            std_dev = float(np.std(channel.sinr_history))
            # A std_dev of 0 dB -> stability_score = 1.0 (perfectly stable)
            # A std_dev of 10+ dB -> stability_score approaches 0.0 (volatile)
            stability_score = np.clip(1.0 - (std_dev / 10.0), 0.0, 1.0)
        else:
            stability_score = 0.5   # Not enough data yet — neutral assumption

        # Factor 3: Utilisation penalty 
        # More devices already on this channel -> higher penalty.
        # Normalised against NUM_IOT_DEVICES so it scales with deployment size.
        devices_on_channel = utilisation.get(channel.channel_id, 0)
        utilisation_penalty = np.clip(
            devices_on_channel / config.NUM_IOT_DEVICES, 0.0, 1.0
        )

        # Combine into final weighted score
        score = (
            (self.WEIGHT_SINR * sinr_score)
            + (self.WEIGHT_STABILITY * stability_score)
            - (self.WEIGHT_UTILISATION * utilisation_penalty)
        )

        return float(score)

# FACTORY FUNCTION — convenient way for main.py to select an algorithm

def create_algorithm(algorithm_name: str) -> BaseACSAlgorithm:
    """
    Factory function to instantiate an ACS algorithm by name.

    This lets main.py (or a config setting) choose the algorithm with a
    simple string, e.g.:

        algo = create_algorithm("threshold")
        algo = create_algorithm("weighted")

    Keeping this logic here (rather than scattering if/else checks in
    main.py) makes it trivial to add a third algorithm later if needed —
    just add another elif branch and a new class above.
    """
    name = algorithm_name.lower().strip()

    if name in ("threshold", "threshold_based", "algorithm1"):
        return ThresholdBasedACS()
    elif name in ("weighted", "weighted_scoring", "algorithm2"):
        return WeightedScoringACS()
    else:
        raise ValueError(
            f"Unknown ACS algorithm: '{algorithm_name}'. "
            f"Expected 'threshold' or 'weighted'."
        )