"""HTTP client of the private PlanTo3D service. The only code that talks to it.

PlanTo3D listens on 127.0.0.1 (PLAN3D_SERVICE_URL) and is never called from a browser.
Its own API is plain HTTP with JSON bodies and `{"error": "..."}` on failure.
"""

import logging
from typing import Any
from urllib.parse import quote

import httpx

from app.modules.plan3d.settings import get_settings

logger = logging.getLogger("construtiva.plan3d.client")


class Plan3dError(Exception):
    """PlanTo3D refused a request. `status` and `message` are safe to pass to the user."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


class Plan3dUnavailable(Plan3dError):
    """The service cannot be reached."""

    def __init__(self, detail: str = "") -> None:
        super().__init__(
            503, "The 3D builder is not running right now. Please try again in a moment."
        )
        self.detail = detail


def _error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict) and isinstance(body.get("error"), str):
        return body["error"]
    return f"The 3D builder answered with an error ({response.status_code})."


class Plan3dClient:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self.http = http

    async def _json(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = await self.http.request(method, path, **kwargs)
        except httpx.HTTPError as e:
            logger.warning("PlanTo3D %s %s failed: %s", method, path, type(e).__name__)
            raise Plan3dUnavailable(type(e).__name__) from e
        if response.status_code >= 400:
            raise Plan3dError(response.status_code, _error_message(response))
        try:
            return response.json()
        except ValueError as e:
            raise Plan3dError(502, "The 3D builder sent an unreadable answer.") from e

    async def system(self) -> dict[str, Any]:
        return await self._json("GET", "/api/system")

    async def upload(self, pdf_bytes: bytes, filename: str, *, detect: bool = True) -> str:
        """Hand a PDF to PlanTo3D. Returns its job id. With `detect` it starts detecting at
        once; without, it only draws the page images and waits for `import_plan`."""
        headers = {"X-Filename": quote(filename or "plan.pdf"), "Content-Type": "application/pdf"}
        if not detect:
            headers["X-Detect"] = "0"
        body = await self._json("POST", "/api/upload", content=pdf_bytes, headers=headers)
        return str(body["id"])

    async def import_plan(
        self, job_id: str, plan: dict[str, Any] | None, reader: str, notice: str = ""
    ) -> None:
        """Give a job a plan read by something other than PlanTo3D's detector (`plan`), or
        an empty plan to trace over the page (None). `reader`: ai, stored, trace or manual."""
        await self._json(
            "POST",
            f"/api/jobs/{job_id}/import",
            json={"plan": plan, "reader": reader, "notice": notice[:300]},
        )

    async def plan(self, job_id: str) -> dict[str, Any]:
        return await self._json("GET", f"/jobs/{job_id}/plan.json")

    async def save_plan(self, job_id: str, plan: dict[str, Any]) -> None:
        await self._json("POST", f"/api/jobs/{job_id}/plan", json=plan)

    async def room_types(self) -> list[str]:
        """PlanTo3D's room types (web/rooms.json)"""
        body = await self._json("GET", "/web/rooms.json")
        return [t for t in body.get("types", {}) if t != "multipurpose"]

    async def save_area(self, spec: dict[str, Any]) -> str:
        """add an area spec to PlanTo3D's library (validated there); -> its type name"""
        body = await self._json(
            "POST", "/api/areas", json={"spec": spec, "source": "ai", "reviewed": False}
        )
        return str(body["type"])

    async def tour(self, job_id: str, quality: str) -> None:
        """Queue a rendered video tour of the built house (PlanTo3D blender/cinema.py)."""
        await self._json("POST", f"/api/jobs/{job_id}/tour", json={"quality": quality})

    async def support(self, job_id: str, floor: int, segments: list[list[float]]) -> list[float]:
        """How much of each proposed wall (plan feet) the drawing shows: 0-1 each."""
        body = await self._json(
            "POST", f"/api/jobs/{job_id}/support", json={"floor": floor, "segments": segments}
        )
        return [float(v) for v in body.get("coverage", [])]

    async def page_png(self, job_id: str) -> bytes:
        """The drawing's first page as PlanTo3D rendered it."""
        try:
            response = await self.http.get(f"/jobs/{job_id}/page-1.png")
        except httpx.HTTPError as e:
            raise Plan3dUnavailable(type(e).__name__) from e
        if response.status_code != 200:
            raise Plan3dUnavailable(f"page image: HTTP {response.status_code}")
        return response.content

    async def source_pdf(self, job_id: str) -> bytes:
        """The PDF the job was made from."""
        try:
            response = await self.http.get(f"/jobs/{job_id}/source.pdf")
        except httpx.HTTPError as e:
            raise Plan3dUnavailable(type(e).__name__) from e
        if response.status_code != 200:
            raise Plan3dError(
                response.status_code, "The plan's PDF is missing from the 3D builder."
            )
        return response.content

    async def sample_pdf(self) -> bytes:
        try:
            response = await self.http.get("/examples/sample_plan.pdf")
        except httpx.HTTPError as e:
            raise Plan3dUnavailable(type(e).__name__) from e
        if response.status_code != 200:
            raise Plan3dError(502, "The sample plan is missing from the 3D builder.")
        return response.content

    async def job(self, job_id: str) -> dict[str, Any] | None:
        """PlanTo3D's status of a job, or None when it no longer has it."""
        try:
            return await self._json("GET", f"/api/jobs/{job_id}")
        except Plan3dError as e:
            if e.status == 404:
                return None
            raise

    async def build(self, job_id: str, quality: str, furniture_set: str = "") -> None:
        """Build the house; `furniture_set` names the owner's own furniture models (service.py)."""
        body = {"quality": quality, **({"furniture_set": furniture_set} if furniture_set else {})}
        await self._json("POST", f"/api/jobs/{job_id}/build", json=body)

    async def export(self, job_id: str) -> str:
        """Pack the Blender file. Returns its path on the service (/jobs/<id>/house_blender.zip)."""
        body = await self._json("POST", f"/api/jobs/{job_id}/export", timeout=960.0)
        return str(body["url"])

    async def delete(self, job_id: str) -> None:
        try:
            await self._json("DELETE", f"/api/jobs/{job_id}")
        except Plan3dError as e:
            if e.status != 404:  # already gone on the service is fine
                raise


_client: Plan3dClient | None = None


def get_plan3d_client() -> Plan3dClient:
    """The shared client (a FastAPI dependency, replaced by a fake transport in tests)."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = Plan3dClient(
            httpx.AsyncClient(
                base_url=settings.service_url.rstrip("/"),
                timeout=httpx.Timeout(settings.timeout_s, connect=5.0),
                follow_redirects=False,
            )
        )
    return _client
