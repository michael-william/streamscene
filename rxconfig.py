import reflex as rx

config = rx.Config(
    app_name="streamscene",
    backend_host="0.0.0.0",
    backend_port=8000,
    frontend_port=3000,
    api_url="https://streamscene.dataandstories.com",
    deploy_url="https://streamscene.dataandstories.com",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)