"""
pruner.py - Smart Context Pruning Engine

Identifies files that are consuming tokens unnecessarily and recommends
pruning them from the active context window. Uses recency-weighted
analysis to determine which context files are truly stale vs. active.

This is what makes Claude Autopilot actionable, not just observational.
"""

import os
from dataclasses import dataclass
from typing import List, Optional

from core.session_reader import ClaudeSession, SessionReader

# Files that are almost always safe to prune
AUTO_PRUNABLE_PATTERNS = [
    "package-lock.json",
    "yarn.lock",
    "poetry.lock",
    "Pipfile.lock",
    ".DS_Store",
    "*.pyc",
    "*.min.js",
    "*.min.css",
    "__pycache__",
    ".gitignore",
    "CHANGELOG.md",
]


@dataclass
class PruningRecommendation:
    file_path: str
    token_count: int
    reason: str
    confidence: float       # 0.0-1.0 confidence in the recommendation
    safe_to_auto_prune: bool


class ContextPruner:
    """
    Analyzes session context and recommends files to remove.

    Scoring algorithm:
    1. Compute recency-weighted token contribution per file
    2. Flag files with low recency weight as stale
    3. Auto-flag known bloat patterns (package-lock.json etc.)
    4. Estimate token savings per recommendation
    """

    STALE_TURN_THRESHOLD = 5   # File not referenced in last N turns
    HIGH_COST_THRESHOLD = 2000  # Files consuming more than this are always analyzed

    def __init__(self, reader: SessionReader):
        self.reader = reader

    def analyze(self, session: ClaudeSession) -> List[PruningRecommendation]:
        recommendations = []
        n_turns = session.turn_count
        if n_turns == 0:
            return recommendations

        # Get recency-weighted file scores
        weights = session.context_file_weights()

        # Detect stale files (referenced early, not referenced recently)
        stale = self._detect_stale_files(session)

        # Detect auto-prunable patterns
        auto_prunable = self._detect_auto_prunable(list(weights.keys()))

        seen = set()

        for file_path, weight in sorted(weights.items(), key=lambda x: x[1], reverse=True):
            if file_path in seen:
                continue
            seen.add(file_path)

            reason = None
            confidence = 0.0
            safe = False

            if file_path in auto_prunable:
                reason = "Auto-generated/lock file — safe to skip"
                confidence = 0.98
                safe = True
            elif file_path in stale:
                turns_ago = stale[file_path]
                reason = f"Not referenced in last {turns_ago} turns (stale)"
                confidence = min(0.9, turns_ago / 10.0)
                safe = turns_ago > 8
            elif weight < 500 and n_turns > 10:
                reason = "Very low token contribution despite many turns"
                confidence = 0.5
                safe = False
            else:
                continue

            # Estimate token count as proportional to weight
            estimated_tokens = int(weight)

            recommendations.append(PruningRecommendation(
                file_path=file_path,
                token_count=estimated_tokens,
                reason=reason,
                confidence=confidence,
                safe_to_auto_prune=safe,
            ))

        return sorted(recommendations, key=lambda r: r.token_count, reverse=True)

    def _detect_stale_files(self, session: ClaudeSession) -> dict:
        """
        Returns {file_path: turns_since_last_reference} for stale files.
        """
        last_seen = {}
        n = session.turn_count
        for i, turn in enumerate(session.turns):
            for f in turn.files_referenced:
                last_seen[f] = i

        stale = {}
        for f, last_turn in last_seen.items():
            turns_ago = n - last_turn
            if turns_ago >= self.STALE_TURN_THRESHOLD:
                stale[f] = turns_ago
        return stale

    def _detect_auto_prunable(self, file_paths: List[str]) -> List[str]:
        prunable = []
        for f in file_paths:
            fname = os.path.basename(f).lower()
            for pattern in AUTO_PRUNABLE_PATTERNS:
                if pattern.startswith("*"):
                    if fname.endswith(pattern[1:]):
                        prunable.append(f)
                        break
                elif fname == pattern.lower():
                    prunable.append(f)
                    break
        return prunable

    def apply(self, session: ClaudeSession, recommendations: List[PruningRecommendation]) -> int:
        """
        Apply pruning recommendations by removing files from .claude settings.
        Returns the number of files actually removed.

        Note: This modifies the .claude/settings.json file in the project directory.
        The changes take effect when Claude Code starts a new session.
        """
        import json
        settings_path = session.project_path / ".claude" / "settings.json"
        if not settings_path.exists():
            return 0
        try:
            with open(settings_path) as f:
                settings = json.load(f)
        except Exception:
            return 0

        # Claude Code stores included files in settings
        include_files = settings.get("includeFiles", [])
        files_to_remove = {r.file_path for r in recommendations if r.safe_to_auto_prune}
        new_includes = [f for f in include_files if os.path.basename(f) not in files_to_remove]
        removed = len(include_files) - len(new_includes)

        settings["includeFiles"] = new_includes
        try:
            with open(settings_path, "w") as f:
                json.dump(settings, f, indent=2)
        except Exception:
            return 0

        return removed
