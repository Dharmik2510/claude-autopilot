"""
dna_engine.py - Session DNA Fingerprint Generator

Generates a unique visual fingerprint for each Claude Code session
by encoding the token consumption pattern as Unicode block glyphs.
Think: a barcode for your AI work.

The fingerprint is then classified against known pattern archetypes
(debugging, feature building, research, refactoring, etc.) and
compared against your historical session fingerprints for similarity.
"""

import math
from dataclasses import dataclass
from typing import List, Optional

from core.session_reader import ClaudeSession

# Unicode block elements for glyph encoding
GLYPHS = " " + chr(0x2581) + chr(0x2582) + chr(0x2583) + chr(0x2584)
GLYPHS += chr(0x2585) + chr(0x2586) + chr(0x2587) + chr(0x2588)

# Pattern archetypes: (label, signature_vector)
# Each signature is a normalized vector of [spike_ratio, cruise_ratio, burst_ratio, avg_delta]
ARCHETYPES = {
    "Bug Fix":       [0.6, 0.2, 0.2, 0.3],
    "Feature Build": [0.2, 0.5, 0.3, 0.6],
    "Research":      [0.1, 0.7, 0.2, 0.4],
    "Refactor":      [0.3, 0.3, 0.4, 0.7],
    "Code Review":   [0.2, 0.6, 0.2, 0.3],
    "Architecture":  [0.4, 0.3, 0.3, 0.8],
    "Debugging":     [0.7, 0.2, 0.1, 0.4],
    "Data Pipeline": [0.3, 0.4, 0.3, 0.9],
}


@dataclass
class SessionFingerprint:
    session_id: str
    project_name: str
    glyph_string: str       # Visual barcode like: ▁▂▄▇█▆▃▁▂▅▇
    pattern_label: str      # Classified archetype: "Bug Fix", "Feature Build", etc.
    similarity_label: str   # How similar to past sessions: "87% match to your debugging sessions"
    normalized_vector: List[float]  # For cross-session comparison
    turn_count: int
    total_tokens: int


class DNAEngine:
    """
    Generates and classifies session DNA fingerprints.

    A fingerprint is created by:
    1. Taking the per-turn token delta sequence
    2. Normalizing deltas to [0, 8] range (matching Unicode block glyphs)
    3. Encoding each delta as a glyph character
    4. Classifying the pattern against known archetypes
    5. Computing similarity against the historical fingerprint library
    """

    def __init__(self):
        self._history: List[SessionFingerprint] = []
        self._fingerprint_width = 32  # Number of glyph characters in DNA bar

    def fingerprint(self, session: ClaudeSession) -> SessionFingerprint:
        deltas = session.token_deltas()
        if not deltas:
            return SessionFingerprint(
                session_id=session.session_id,
                project_name=session.project_name,
                glyph_string=chr(0x2591) * 8,
                pattern_label="Empty session",
                similarity_label="No history",
                normalized_vector=[0.0, 0.0, 0.0, 0.0],
                turn_count=0,
                total_tokens=0,
            )

        glyphs = self._encode_glyphs(deltas)
        vec = self._compute_signature_vector(deltas)
        label = self._classify_archetype(vec)
        sim_label = self._similarity_label(vec, session.session_id)

        fp = SessionFingerprint(
            session_id=session.session_id,
            project_name=session.project_name,
            glyph_string=glyphs,
            pattern_label=label,
            similarity_label=sim_label,
            normalized_vector=vec,
            turn_count=session.turn_count,
            total_tokens=session.total_tokens,
        )
        self._history.append(fp)
        return fp

    def _encode_glyphs(self, deltas: List[int]) -> str:
        if not deltas:
            return chr(0x2591) * 8

        # Resample to fixed width using simple interpolation
        resampled = self._resample(deltas, self._fingerprint_width)

        # Normalize to 0-8 for glyph index
        max_val = max(resampled) or 1
        min_val = min(resampled)
        span = max_val - min_val or 1

        glyphs = ""
        for v in resampled:
            idx = int(8 * (v - min_val) / span)
            idx = max(0, min(8, idx))
            glyphs += GLYPHS[idx]
        return glyphs

    def _resample(self, data: List[float], target_len: int) -> List[float]:
        """Resample a list to target length using linear interpolation."""
        if len(data) == target_len:
            return data
        result = []
        for i in range(target_len):
            frac = i * (len(data) - 1) / max(1, target_len - 1)
            lo = int(frac)
            hi = min(lo + 1, len(data) - 1)
            lerp = frac - lo
            result.append(data[lo] * (1 - lerp) + data[hi] * lerp)
        return result

    def _compute_signature_vector(self, deltas: List[int]) -> List[float]:
        """
        Compute a 4-component signature vector:
        [spike_ratio, cruise_ratio, burst_ratio, avg_delta_normalized]
        """
        if not deltas:
            return [0.0, 0.0, 0.0, 0.0]

        avg = sum(deltas) / len(deltas)
        std = math.sqrt(sum((d - avg) ** 2 for d in deltas) / max(1, len(deltas)))
        threshold_spike = avg + 1.5 * std
        threshold_burst = avg + 0.5 * std

        spike_count = sum(1 for d in deltas if d > threshold_spike)
        burst_count = sum(1 for d in deltas if threshold_burst < d <= threshold_spike)
        cruise_count = len(deltas) - spike_count - burst_count

        total = len(deltas)
        spike_ratio = spike_count / total
        cruise_ratio = cruise_count / total
        burst_ratio = burst_count / total

        # Normalize average delta to 0-1 range (cap at 10K tokens)
        avg_normalized = min(1.0, avg / 10_000)

        return [spike_ratio, cruise_ratio, burst_ratio, avg_normalized]

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x ** 2 for x in a)) or 1
        mag_b = math.sqrt(sum(x ** 2 for x in b)) or 1
        return dot / (mag_a * mag_b)

    def _classify_archetype(self, vec: List[float]) -> str:
        best_label = "Mixed"
        best_score = -1.0
        for label, sig in ARCHETYPES.items():
            score = self._cosine_similarity(vec, sig)
            if score > best_score:
                best_score = score
                best_label = label
        return best_label

    def _similarity_label(self, vec: List[float], exclude_id: str) -> str:
        comparable = [fp for fp in self._history if fp.session_id != exclude_id]
        if not comparable:
            return "First session of this type"
        best = max(comparable, key=lambda fp: self._cosine_similarity(vec, fp.normalized_vector))
        score = self._cosine_similarity(vec, best.normalized_vector)
        pct = int(score * 100)
        return f"{pct}% match to {best.project_name} ({best.pattern_label})"
