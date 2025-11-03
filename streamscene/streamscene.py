"""StreamScene - Family E Ink Message Board."""

import os
from dotenv import load_dotenv
import reflex as rx

from streamscene.pages.index import index
from streamscene.pages.login import login
from streamscene.pages.callback import callback
from streamscene.pages.dashboard import dashboard
from streamscene.pages.streams import streams
from streamscene.pages.stream_posts import stream_posts_page

# Import FastAPI app for device API
from streamscene.api import api

# Load environment variables from .env file
load_dotenv()


# Create the app with API transformer
app = rx.App(api_transformer=api)

# Register Reflex pages
app.add_page(index, route="/")
app.add_page(login, route="/login")
app.add_page(callback, route="/callback")
app.add_page(dashboard, route="/dashboard")
app.add_page(streams, route="/streams")
app.add_page(stream_posts_page, route="/streams/[slug]")
