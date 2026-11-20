"""Record and replay the generator's AI answers, so a brief can be re-run offline.

RecordingLLM wraps the live client: every structured() call is answered from the cache when
the same (task, system, user, schema) was seen before, and otherwise asked live (only when
`live=True`) and stored. Replay-only use (live=False) never calls a model, so tests can use
the cached answers as fixtures. Live calls are counted in `calls`.
"""

import hashlib
import json
from pathlib import Path


class CacheMiss(RuntimeError):
    pass


class RecordingLLM:
    def __init__(self, cache_dir: Path, inner=None, live: bool = False, model: str = "cached"):
        self.dir = Path(cache_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.inner = inner
        self.live = live
        self.calls = 0
        self.hits = 0
        self.model = getattr(inner, "model", model) if inner else model
        self.provider = getattr(inner, "provider", "cache") if inner else "cache"

    def _key(self, task: str, system: str, user: str, schema) -> Path:
        h = hashlib.sha256(
            json.dumps([task, system, user, schema.__name__], ensure_ascii=False).encode()
        ).hexdigest()[:20]
        return self.dir / f"{task}_{h}.json"

    def structured(self, *, system: str, user: str, schema, task: str, images=None):
        path = self._key(task, system, user, schema)
        if path.exists():
            self.hits += 1
            return schema.model_validate(json.loads(path.read_text())["answer"])
        if not (self.live and self.inner):
            from app.modules.ai.llm.client import LLMError

            raise LLMError(f"no cached answer for {task} ({path.name})")
        ans = self.inner.structured(system=system, user=user, schema=schema, task=task)
        self.calls += 1
        path.write_text(
            json.dumps(
                {"task": task, "model": self.model, "user": user[:2000],
                 "answer": ans.model_dump(mode="json")},
                ensure_ascii=False,
                indent=1,
            )
        )
        return ans
