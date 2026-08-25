"""The minimal example from the project spec. Run with:

    python examples/demo_check_id.py
"""

from kwebui import KApp


    
class Demo(KApp):
    def example_callback(self) -> None:
        print(self.id_text.value)
        if self.id_text.value in ["1", "2", "3"]:
            print("ID not found in inventory!")
            self.alert.success(f"ID {self.id_text.value} not found in inventory!")
            self.id_text.unhighlight()  # Remove highlight from the textedit to indicate success

            
        else:
            print("ID found in inventory!")
            self.alert.error(f"ID {self.id_text.value} found in inventory. Please check the ID and try again.")
            self.id_text.highlight()  # Highlight the textedit to indicate success
            self.id_text.set_value("")  # Clear the textedit for the next input
            self.id_text.focus()  # Focus the textedit again for convenience
    def build(self) -> None:
        self.text("Check ID", size=28)
        self.id_text = self.textedit("Device Name", placeholder="Enter Name")
        self.id_text = self.textedit("Device Sample Input", placeholder="Enter Sample Input")
        self.id_text = self.textedit("Device ID", placeholder="Enter Device ID")
        self.button("Check inventory", on_click=lambda: self.example_callback())
        self.alert = self.empty()

       
        

        


if __name__ == "__main__":
    Demo(title="Demo").run()
