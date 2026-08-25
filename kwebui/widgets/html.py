"""HTML widget: a raw HTML block, Streamlit ``st.html`` style.

The string is written to the DOM as-is (``innerHTML``, not escaped text).
Like Streamlit's ``st.html``, this widget trusts the caller -- ``html`` is
meant to be a literal or template string the developer wrote, never
unsanitized end-user input.
"""

from __future__ import annotations

from ..plugin import WidgetPlugin
from ..widget import Widget


class HtmlWidget(Widget):
    def set_html(self, html: str) -> "HtmlWidget":
        self.update(html=html)
        return self


class HtmlPlugin(WidgetPlugin):
    """
    Example:
        app.html("<strong>Status:</strong> <span style='color:green'>OK</span>")
    """

    widget_name = "html"

    def create(self, widget_id: str, html: str) -> HtmlWidget:
        return HtmlWidget(widget_id, self.widget_name, {"html": html})
