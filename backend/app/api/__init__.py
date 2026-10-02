"""路由汇总。

写接口（manage / jobs / settings / llm）统一在这里挂上 ``require_admin`` 依赖，
不逐个路由去改——这样新加的写接口默认是「已受保护」的，漏挂的概率更低。

``memes`` 是读写混装（GET 列表/详情/趋势/视频 + POST insight），整路由挂会把
只读接口也锁上，所以留在这里只挂公开读，POST insight 在 memes.py 内单独挂。
"""

from fastapi import APIRouter, Depends

from . import history, jobs, llm, manage, memes, meta, pipeline, settings as settings_api
from .deps import require_admin

api_router = APIRouter()
api_router.include_router(meta.router)
# pipeline 是纯只读的数据流程画像，与 meta 同组：不挂令牌守卫，
# 也不暴露任何凭据/Key，小程序端将来复用不必带 X-Admin-Token。
api_router.include_router(pipeline.router)
# history（梗史馆）同理：只读的复盘视图，数据全部来自库里已算好的快照与逐日序列。
api_router.include_router(history.router)
api_router.include_router(memes.router)
api_router.include_router(llm.router, dependencies=[Depends(require_admin)])
api_router.include_router(settings_api.router, dependencies=[Depends(require_admin)])
api_router.include_router(jobs.router, dependencies=[Depends(require_admin)])
api_router.include_router(manage.router, dependencies=[Depends(require_admin)])

__all__ = ["api_router"]
