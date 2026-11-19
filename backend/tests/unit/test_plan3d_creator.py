"""The creator agent loop (plan3d/creator.py), with a fake model and a fake PlanTo3D."""

from types import SimpleNamespace as NS

from app.modules.plan3d import creator


def block(kind, **kw):
    return NS(type=kind, **kw)


def reply(stop, *blocks):
    return NS(
        stop_reason=stop, content=list(blocks), usage=NS(input_tokens=1000, output_tokens=200)
    )


class FakeModel:
    def __init__(self, script):
        self.script, self.requests = list(script), []
        self.beta = NS(messages=NS(create=self.create))

    def create(self, **kw):
        self.requests.append(kw)
        return self.script.pop(0)


class FakeService:
    def __init__(self, fail=()):
        self.ops, self.fail, self.finished = [], set(fail), None

    def creator_start(self, area, size):
        self.area = area
        return "s1"

    def creator_op(self, sid, op, args):
        self.ops.append((op, args))
        if op in self.fail:
            return {"ok": False, "error": "max must be greater than min"}
        if op == "render_preview":
            return {"ok": True, "preview": "preview.png", "png_b64": "iVBOR"}
        return {"ok": True, "op": op}

    def creator_finish(self, sid, meta):
        self.finished = meta
        return {"ok": True, "entry": {"id": self.area, "review": "unreviewed"}}


def tool(i, name, **inp):
    return block("tool_use", id=f"t{i}", name=name, input=inp)


def test_builds_previews_exports_and_records_cost():
    model = FakeModel(
        [
            reply(
                "tool_use",
                block("text", text="a pad"),
                tool(1, "add_box", min=[-5, -5, 0], max=[5, 5, 0.3]),
            ),
            reply("tool_use", tool(2, "render_preview")),
            reply("tool_use", tool(3, "export")),
        ]
    )
    svc = FakeService()
    out = creator.create(
        "helipad",
        "Helipad",
        "a landing pad",
        [12, 12, 1],
        svc,
        client=model,
        model="claude-opus-5-5",
    )
    assert [o for o, _ in svc.ops] == ["add_box", "render_preview", "export"]
    assert out["ok"] and out["turns"] == 3 and out["entry"]["review"] == "unreviewed"
    assert out["cost_usd"] == round(3 * (1000 * 4 + 200 * 20) / 1e6, 4)
    assert svc.finished["prompt"].startswith("Make the area 'Helipad'")
    # the preview reaches the model as an image; the base64 is not repeated in the text
    # (task, then assistant / results pairs: the preview's results are the fifth message)
    preview = model.requests[-1]["messages"][4]["content"][0]["content"]
    assert preview[1]["type"] == "image" and "png_b64" not in preview[0]["text"]
    assert (
        model.requests[0]["tools"] == creator.TOOLS
        and "Style materials:" in model.requests[0]["system"]
    )


def test_errors_go_back_to_the_model_and_turns_are_capped():
    model = FakeModel(
        [reply("tool_use", tool(i, "add_box", min=[1, 1, 1], max=[0, 0, 0])) for i in range(9)]
    )
    svc = FakeService(fail={"add_box"})
    out = creator.create(
        "pond", "Koi pond", "a pond", [4, 3, 1], svc, client=model, model="m", max_turns=3
    )
    assert out["turns"] == 3 and len(svc.ops) == 3
    last = model.requests[-1]["messages"][-1]["content"][0]
    assert last["is_error"] is True and "greater" in last["content"][0]["text"]


def test_stops_on_end_turn_and_refusal():
    for stop in ("end_turn", "refusal"):
        svc = FakeService()
        out = creator.create(
            "x_y",
            "X",
            "x",
            [2, 2, 2],
            svc,
            client=FakeModel([reply(stop, block("text", text="done"))]),
            model="m",
        )
        assert out["turns"] == 1 and svc.ops == [] and svc.finished is not None


def test_off_by_default(monkeypatch):
    from app.modules.plan3d import settings

    monkeypatch.setattr(settings, "get_settings", lambda: NS(creator_agent=False))
    out = creator.run("helipad", "Helipad", "pad", [10, 10, 1])
    assert out["ok"] is False and "PLAN3D_CREATOR_AGENT" in out["problems"][0]


async def test_endpoint_only_for_listed_admins_with_the_flag(monkeypatch):
    import pytest
    from fastapi import HTTPException

    from app.modules.plan3d import router

    body = {"area": "helipad", "size_m": [10, 10, 1]}
    for flag, admins in ((False, "u1"), (True, ""), (True, "u2")):
        settings = NS(creator_agent=flag, creator_admins=admins)
        monkeypatch.setattr(router, "get_settings", lambda s=settings: s)
        with pytest.raises(HTTPException) as e:
            await router.run_creator(body, NS(id="u1"))
        assert e.value.status_code == 403
    monkeypatch.setattr(router, "get_settings", lambda: NS(creator_agent=True, creator_admins="u1"))
    monkeypatch.setattr(creator, "run", lambda *a: {"ok": True, "args": a})
    out = await router.run_creator(body, NS(id="u1"))
    assert out["args"][0] == "helipad" and out["args"][3] == [10.0, 10.0, 1.0]
