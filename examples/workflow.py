"""A workflow_tracker in a topbar driving which "page" is shown below it.

Three independent page classes (Example1/2/3 -- plain objects, nothing
kwebui-specific about them beyond the render(container) method) each
build their own group of widgets into a shared container(). Clicking a
step in the tracker clears that container and rebuilds it with the
selected page's content, and moves the tracker's "current step" marker
to match. Run with:

    python examples/workflow.py

Then open the printed URL (default http://127.0.0.1:8701, or the next
free port after it) in a browser.
"""

from kwebui import KApp

TASKS = [
    {"id": 1, "title": "Example 1", "status": "in-progress"},
    {"id": 2, "title": "Example 2", "status": "pending"},
    {"id": 3, "title": "Example 3", "status": "pending"},
   
]


class Example1:
    def render(self, container) -> None:
        container.text("Example 1", size=24, bold=True)
        container.text("A plain text-and-button page.", color="#6b7280")
        container.button("Say hi", on_click=self.on_button_click)

    def on_button_click(self) -> None:
        print("hi from example 1")


class Example2:
    def render(self, container) -> None:
        container.text("Example 2", size=24, bold=True)
        container.checkbox("Enable feature", on_change=lambda v: print("checkbox:", v))
        container.slider("Volume", min_value=0, max_value=100, value=40, on_change=lambda v: print("volume:", v))


class Example3:
    def render(self, container) -> None:
        container.text("Example 3", size=24, bold=True)
        container.listbox(["Red", "Green", "Blue"], on_select=lambda item: print("selected:", item))
        container.progressbar(70)


class Workflow(KApp):
    def build(self) -> None:
        self.examples = {1: Example1(), 2: Example2(), 3: Example3()}

        # bar = self.topbar()
        # self.tracker = bar.workflow_tracker(list(TASKS), on_select=self.show_task)

        sidebar = self.sidebar()
        sidebar.text("Workflow", size=18, bold=True)
        # sidebar.text("Pick a step in the topbar above to switch pages.", color="#6b7280")
        self.tracker = sidebar.workflow_tracker(list(TASKS), on_select=self.show_task,orientation="vertical")

        # The container is the "rest of the page" -- everything except
        # the topbar and the sidebar -- and its whole content gets
        # replaced each time a different step is selected.
        self.content = self.container()
        self.current_task_id = None
        self.show_task(1)

    def show_task(self, task_id: int) -> None:
        if task_id == self.current_task_id:
            return
        self.current_task_id = task_id

        tasks = [
            {**task, "status": "in-progress" if task["id"] == task_id else "pending"}
            for task in self.tracker.props["tasks"]
        ]
        self.tracker.set_tasks(tasks)

        self.content.clear()
        self.examples[task_id].render(self.content)


if __name__ == "__main__":
    Workflow(title="kwebui Workflow Example").run()
