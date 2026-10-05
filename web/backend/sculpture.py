"""A bounded shape-design conversation, followed by ordinary Nova publication."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field

import toolkit

MAX_ATTEMPTS = 3
MAX_REVIEWS = 1
MAX_TURNS = MAX_ATTEMPTS + MAX_REVIEWS + 2
_DESIGN_NAMES = {"submit_brick_design", "accept_design"}


def select_tools(schemas, build_style):
    """Keep shape generation on the bounded design tools."""
    design = build_style == "sculpture"
    return [t for t in schemas if (t["function"]["name"] in _DESIGN_NAMES) == design]


def configure_turn(ctx, schemas, default_max_steps):
    """Activate the focused prompt and short turn limit only when design tools are allowed."""
    if not any(t["function"]["name"] in _DESIGN_NAMES for t in schemas):
        return None, default_max_steps
    ctx.workflow = DesignWorkflow()
    guide = toolkit.root() / "docs/agent/sculptures.md"
    if not guide.is_file():
        raise ValueError("Update the paired ldraw-nova checkout for Sculpture Mode.")
    return guide.read_text(), MAX_TURNS


@dataclass
class DesignWorkflow:
    failures: int = 0
    reviews: int = 0
    submissions: int = 0
    best: tuple[str, str] | None = None  # latest successful solid voxels and title
    finished: bool = False
    card_url: str | None = None
    brick_count: int | None = None
    stopped: bool = False
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def submit(self, ctx, grid, shapes, title="Sculpture model", layer_unit="brick", hollow=True):
        from tools import ToolError, ToolResult, resolve_path, run_command, t_write_file
        async with self.lock:
            if self.finished:
                return ToolResult("Already published. Reply with the model card; do not rebuild.")
            self.submissions += 1
            if self.submissions > MAX_TURNS:
                raise ToolError("Design attempt limit reached. Accept the last successful design.")
            stem = f"design-{self.submissions}"
            title = str(title).replace("\n", " ").replace("\r", " ")[:120]
            design = dict(grid=grid, shapes=shapes, title=title, layer_unit=layer_unit, hollow=hollow)
            await t_write_file(ctx, f"output/{stem}.json", json.dumps(design))
            report_path = resolve_path(ctx, f"output/{stem}.report.json", write=True)
            # Review the cheap draft first. Final packing runs only after acceptance.
            argv = ["./ldraw-agent", "sculpture", "preview", f"output/{stem}.json",
                    "--output", f"output/{stem}.png", "--voxels-output", f"output/{stem}.voxels.json",
                    "--report", f"output/{stem}.report.json"]
            ctx.emit("progress", {"summary": "Building the voxel design and its preview."})
            checked = await run_command(ctx, argv, 300)
            report = json.loads(report_path.read_text()) if report_path.is_file() else {}
            if checked.exit_code or not report.get("checks_passed"):
                self.failures += 1
                if self.failures < MAX_ATTEMPTS:
                    return ToolResult("Build failed: " + report.get("error", checked.as_text()) +
                                      " Submit a corrected complete design.")
                if self.best:
                    return await self.accept(ctx)
                # Last failed attempt: use the draft builder's recolour/removal fallback.
                repaired = await run_command(ctx, [*argv, "--repair"], 300)
                report = json.loads(report_path.read_text()) if report_path.is_file() else {}
                if repaired.exit_code or not report.get("checks_passed"):
                    raise ToolError(report.get("error", "No buildable voxel design was produced"))
            self.best = (f"output/{stem}.voxels.json", title)
            if self.reviews >= MAX_REVIEWS or self.failures >= MAX_ATTEMPTS:
                return await self.accept(ctx)
            self.reviews += 1
            return ToolResult(json.dumps(report) +
                              "\nReview both views against the request. Call accept_design if it looks right, "
                              "or submit one improved complete design. Draft brick counts are estimates.",
                              images=[resolve_path(ctx, f"output/{stem}.png")])

    async def accept(self, ctx):
        from tools import ToolError, ToolResult, resolve_path, run_command, t_publish_model
        if self.finished:
            return ToolResult("Already published. Reply with the model card; do not rebuild.")
        if not self.best:
            return ToolResult("No successful build to accept yet. Submit a complete design.")
        self.finished = True  # acceptance is terminal, including a conversion/publication failure
        voxels, title = self.best
        ctx.emit("progress", {"summary": "Converting the accepted voxels into bricks."})
        report_path = resolve_path(ctx, "output/sculpture.report.json", write=True)
        converted = await run_command(ctx, ["./ldraw-agent", "sculpture", "convert", voxels,
            "--output", "output/sculpture.mpd", "--title", title,
            "--render-output", "output/sculpture.render.mpd",
            "--report", "output/sculpture.report.json"], 300)
        report = json.loads(report_path.read_text()) if report_path.is_file() else {}
        if converted.exit_code or not report.get("checks_passed"):
            raise ToolError(report.get("error", converted.as_text()))
        # Publication already validates and renders: no separate CAD review or validation cycle.
        result = await t_publish_model(ctx, "output/sculpture.mpd", title,
                                       render_path="output/sculpture.render.mpd")
        if result.models:
            publication = json.loads(result.content)
            self.card_url = publication["card_url"]
            self.brick_count = report.get("brick_count")
            publication.pop("note", None)  # its general-purpose visual-review instruction is already satisfied
            publication["conversion"] = {key: report[key] for key in
                ("brick_count", "support_voxels_added", "unresolved_voxels") if key in report}
            result.content = json.dumps(publication) + "\nFinished. Reply with the published model card."
        return result


async def submit_brick_design(ctx, grid, shapes, title="Sculpture model", layer_unit="brick", hollow=True):
    return await ctx.workflow.submit(ctx, grid, shapes, title, layer_unit, hollow)


async def accept_design(ctx):
    # Serialise acceptance too: concurrent provider calls must never publish twice.
    async with ctx.workflow.lock:
        return await ctx.workflow.accept(ctx)


async def finish_design(run, ctx, save, execute):
    """A text-only acceptance or exhausted turn budget also keeps the latest good draft."""
    if ctx.workflow.finished:
        if ctx.workflow.card_url and ctx.store.messages(ctx.chat_id)[-1]["role"] != "assistant":
            save({"role": "assistant", "content": f"Published [{ctx.workflow.best[1]}]({ctx.workflow.card_url}) — {ctx.workflow.brick_count} bricks."})
        return
    if ctx.workflow.stopped:
        return
    if not ctx.workflow.best:
        raise ValueError("No buildable voxel design was submitted. Start a new turn to try again.")
    # Use the existing permission gate and transcript format for backend finalisation too.
    import uuid
    call_id = uuid.uuid4().hex
    save({"role": "assistant", "content": None, "tool_calls": [{"id": call_id, "type": "function",
          "function": {"name": "accept_design", "arguments": "{}"}}]})
    info = {"id": call_id, "name": "accept_design", "arguments": "{}"}
    run.tools_running[call_id] = info
    run.emit("tool_start", info)
    try:
        result = await execute(run, ctx, call_id, "accept_design", "{}")
        save({"role": "tool", "tool_call_id": call_id, "name": "accept_design",
              "content": result.content, "_models": [m["id"] for m in result.models]})
        if result.models:
            card = json.loads(result.content.split("\nFinished.")[0])["card_url"]
            save({"role": "assistant", "content": f"Published [{ctx.workflow.best[1]}]({card})."})
    finally:
        run.tools_running.pop(call_id, None)
        run.emit("tool_end", info)
