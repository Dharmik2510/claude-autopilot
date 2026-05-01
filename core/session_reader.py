"""
session_reader.py - Parses Claude Code JSONL session files

Claude Code stores sessions at ~/.claude/projects/<hash>/<session>.jsonl
Each line is a JSON object with conversation turn + token metadata.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional


@dataclass
class SessionTurn:
    turn_number: int
    timestamp: datetime
    user_message: Optional[str]
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    tool_calls: int
    files_referenced: List[str] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def efficiency_score(self) -> float:
        if self.input_tokens == 0:
            return 0.0
        base = min(1.0, self.output_tokens / max(1, self.input_tokens))
        tool_bonus = min(0.3, self.tool_calls * 0.05)
        bloat_penalty = 0.2 if (self.input_tokens > 10000 and self.output_tokens < 200) else 0
        return max(0.0, min(1.0, base + tool_bonus - bloat_penalty))


@dataclass
class ClaudeSession:
    session_id: str
    project_name: str
    project_path: Path
    session_file: Path
    turns: List[SessionTurn] = field(default_factory=list)
    last_updated: float = 0.0

    @property
    def turn_count(self) -> int:
        return len(self.turns)

    @property
    def total_input_tokens(self) -> int:
        return sum(t.input_tokens for t in self.turns)

    @property
    def total_output_tokens(self) -> int:
        return sum(t.output_tokens for t in self.turns)

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    def token_deltas(self) -> List[int]:
        return [t.total_tokens for t in self.turns]

    def cumulative_tokens(self) -> List[int]:
        total = 0
        result = []
        for t in self.turns:
            total += t.total_tokens
            result.append(total)
        return result

    def context_file_weights(self) -> dict:
        n = len(self.turns)
        weights = {}
        for i, turn in enumerate(self.turns):
            recency = (i + 1) / n if n > 0 else 1
            for f in turn.files_referenced:
                weights[f] = weights.get(f, 0) + turn.input_tokens * recency
        return weights


class SessionReader:
    SESSION_LIMIT = 200_000

    def __init__(self, projects_dir: Path):
        self.projects_dir = projects_dir
        self._cache: dict = {}
        self._cache_mtime: dict = {}

    def get_sessions(self, project_filter: Optional[str] = None) -> List[ClaudeSession]:
        sessions = []
        if not self.projects_dir.exists():
            return sessions
        for project_dir in sorted(self.projects_dir.iterdir()):
            if not project_dir.is_dir():
                continue
            project_name = project_dir.name[:30]
            if project_filter and project_filter.lower() not in project_name.lower():
                continue
            for session_file in sorted(project_dir.glob("*.jsonl")):
                session = self._parse_session_file(session_file, project_name)
                if session and session.turn_count > 0:
                    sessions.append(session)
        return sessions

    def _parse_session_file(self, session_file: Path, project_name: str) -> Optional[ClaudeSession]:
        mtime = session_file.stat().st_mtime
        cache_key = str(session_file)
        if cache_key in self._cache and self._cache_mtime.get(cache_key) == mtime:
            return self._cache[cache_key]
        session = ClaudeSession(
            session_id=session_file.stem,
            project_name=project_name,
            project_path=session_file.parent,
            session_file=session_file,
            last_updated=mtime,
        )
        try:
            with open(session_file, encoding="utf-8") as f:
                for line_num, raw in enumerate(f):
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        obj = json.loads(raw)
                        turn = self._parse_turn(obj, line_num)
                        if turn:
                            session.turns.append(turn)
                    except json.JSONDecodeError:
                        continue
        except (OSError, IOError):
            return None
        self._cache[cache_key] = session
        self._cache_mtime[cache_key] = mtime
        return session

    def _parse_turn(self, obj: dict, line_num: int) -> Optional[SessionTurn]:
        usage = obj.get("usage", {})
        if not usage:
            msg = obj.get("message", {})
            usage = msg.get("usage", {}) if isinstance(msg, dict) else {}
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        if input_tokens == 0 and output_tokens == 0:
            return None
        cache_read = usage.get("cache_read_input_tokens", 0)
        cache_write = usage.get("cache_creation_input_tokens", 0)
        user_msg = None
        content = obj.get("message", {}).get("content", []) if isinstance(obj.get("message"), dict) else []
        if isinstance(content, str):
            user_msg = content[:200]
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    user_msg = (block.get("text") or "")[:200]
                    break
        tool_calls = sum(1 for b in (content if isinstance(content, list) else []) if isinstance(b, dict) and b.get("type") == "tool_use")
        files = self._extract_files(content)
        ts_str = obj.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_str) if ts_str else datetime.now()
        except ValueError:
            ts = datetime.now()
        return SessionTurn(
            turn_number=line_num,
            timestamp=ts,
            user_message=user_msg,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
            tool_calls=tool_calls,
            files_referenced=files,
        )

    def _extract_files(self, content) -> List[str]:
        files = []
        if not isinstance(content, list):
            return files
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            tool_name = block.get("name", "")
            if tool_name in ("Read", "Write", "Edit", "MultiEdit", "Bash"):
                inp = block.get("input", {})
                fpath = inp.get("file_path", inp.get("path", ""))
                if fpath:
                    files.append(os.path.basename(str(fpath)))
        return files
