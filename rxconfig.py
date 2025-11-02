import reflex as rx

config = rx.Config(
    app_name="streamscene",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)