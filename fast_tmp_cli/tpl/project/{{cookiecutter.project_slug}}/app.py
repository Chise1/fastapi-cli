import os

os.environ.setdefault("FASTAPI_SETTINGS_MODULE", "{{cookiecutter.project_slug}}.settings")# 请勿在此配置前面加 import

from tortoise.contrib.fastapi import register_tortoise
from fast_tmp.site import register_model_site

from fast_tmp.conf import settings
from fast_tmp.factory import create_app

app = create_app()
app.title = "{{cookiecutter.project_slug}}"

register_tortoise(app, config=settings.TORTOISE_ORM, generate_schemas=True)
if settings.DEBUG:
    from starlette.staticfiles import StaticFiles
    app.mount("/static", StaticFiles(directory="static"), name="static")  # 注册admin页面需要的静态文件，

if __name__ == "__main__":
    import uvicorn  # type:ignore

    uvicorn.run(app, debug=True, port=8000, lifespan="on")