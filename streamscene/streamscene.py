"""StreamScene - Family E Ink Message Board."""

import reflex as rx

from streamscene.pages.index import index
from streamscene.pages.login import login
from streamscene.pages.callback import callback
from streamscene.pages.streams import streams


# Create the app
app = rx.App()

# Register pages
app.add_page(index, route="/")
app.add_page(login, route="/login")
app.add_page(callback, route="/callback")
app.add_page(streams, route="/streams")
