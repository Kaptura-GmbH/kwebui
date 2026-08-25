"""WorkflowTracker widget: a horizontal or vertical step tracker/stepper.

    tasks = [
        {"id": 1, "title": "Analyze requirements", "status": "completed"},
        {"id": 2, "title": "Create database", "status": "completed"},
        {"id": 3, "title": "Build API", "status": "in-progress"},
        {"id": 4, "title": "Build frontend", "status": "pending"},
        {"id": 5, "title": "Deploy", "status": "pending"},
    ]
    self.workflow_tracker(tasks, orientation="horizontal", on_select=lambda task_id: ...)

Rendering (the circle per status, connecting line, title/detail text) is
entirely `workflow_tracker.js`'s job -- the Python side only validates and
carries the task list as plain JSON, the same shape ``ListBoxWidget``
uses for ``items`` or ``JsonWidget`` uses for ``data``.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

from ..events import Event
from ..plugin import WidgetPlugin
from ..widget import Widget

#: "error" isn't in the spec's own example tasks list, but covers the
#: "Missing Details" red state a workflow step can end up in.
_STATUSES = {"completed", "in-progress", "pending", "error"}
_ORIENTATIONS = {"horizontal", "vertical"}


def _validate_status(status: str) -> None:
    if status not in _STATUSES:
        available = ", ".join(sorted(_STATUSES))
        raise ValueError(f"Unknown task status {status!r}. Available: {available}")


def _validate_tasks(tasks: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    validated = []
    for task in tasks:
        if "id" not in task or "title" not in task or "status" not in task:
            raise ValueError(f"Task {task!r} must have 'id', 'title', and 'status' keys")
        _validate_status(task["status"])
        validated.append(
            {
                "id": task["id"],
                "title": task["title"],
                "status": task["status"],
                "detail": task.get("detail", ""),
            }
        )
    return validated


class WorkflowTrackerWidget(Widget):
    def set_tasks(self, tasks: Sequence[dict[str, Any]]) -> "WorkflowTrackerWidget":
        self.update(tasks=_validate_tasks(tasks))
        return self

    def set_task_status(self, task_id: Any, status: str, detail: str | None = None) -> "WorkflowTrackerWidget":
        """Update one task in place -- the common case of progressing a
        workflow step by step, without the caller having to re-send the
        whole list each time."""
        _validate_status(status)
        tasks = [dict(task) for task in self.props.get("tasks", [])]
        for task in tasks:
            if task["id"] == task_id:
                task["status"] = status
                if detail is not None:
                    task["detail"] = detail
                break
        else:
            raise ValueError(f"No task with id {task_id!r}")
        self.update(tasks=tasks)
        return self


class WorkflowTrackerPlugin(WidgetPlugin):
    """
    Example:
        tasks = [
            {"id": 1, "title": "Analyze requirements", "status": "completed"},
            {"id": 2, "title": "Build API", "status": "in-progress"},
            {"id": 3, "title": "Deploy", "status": "pending"},
        ]
        self.workflow_tracker(tasks, orientation="horizontal", on_select=lambda task_id: ...)
    """

    widget_name = "workflow_tracker"

    def create(
        self,
        widget_id: str,
        tasks: Sequence[dict[str, Any]],
        *,
        orientation: str = "horizontal",
        on_select: Callable[[Any], None] | None = None,
    ) -> WorkflowTrackerWidget:
        if orientation not in _ORIENTATIONS:
            available = ", ".join(sorted(_ORIENTATIONS))
            raise ValueError(f"Unknown orientation {orientation!r}. Available: {available}")
        props = {
            "tasks": _validate_tasks(tasks),
            "orientation": orientation,
            "on_select": on_select,
        }
        return WorkflowTrackerWidget(widget_id, self.widget_name, props)

    def handle_event(self, widget: Widget, event: Event) -> None:
        if event.type != "select":
            return
        callback = widget.props.get("on_select")
        if callback is not None:
            callback(event.payload.get("task_id"))
