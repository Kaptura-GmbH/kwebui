"""The minimal example from the project spec. Run with:

    python examples/demo.py
"""

from kwebui import KApp

def example_callback():
    print("Hello World 1")
    
class Demo(KApp):
    def test_callback(self):
        self.popup("Delete this item?", kind="yesno", on_return=self.on_delete_answer)
    def build(self) -> None:
        self.text("Hello World", size=28)
        self.button("Click Me", on_click=example_callback)
        self.button("Test", on_click=self.test_callback)
        self.checkbox(
            "Enable feature",
            on_change=lambda checked: print("Feature enabled" if checked else "Feature disabled"),
        )
        test = self.textedit("Name")

        self.progressbar(50)
        self.button("Highlight Name", on_click=lambda: test.focus() )
        

        


if __name__ == "__main__":
    Demo(title="Demo").run()
