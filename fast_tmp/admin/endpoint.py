from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends
from fastapi.params import Path
from pydantic import BaseModel
from sqlalchemy import (
    DECIMAL,
    INTEGER,
    BigInteger,
    DateTime,
    Float,
    Integer,
    Numeric,
    SmallInteger,
    delete,
    func,
    select,
)
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import RedirectResponse

from fast_tmp.site import ModelAdmin, get_model_site

from ..db import get_db_session
from ..models import User
from ..site.utils import clean_data_to_model, get_pk
from .depends import decode_access_token_from_data
from .responses import BaseRes, key_error, not_found_instance

router = APIRouter()


async def get_data(request: Request) -> dict:
    """
    从异步函数里面读取数据
    """
    return await request.json()


class ListDataWithPage(BaseModel):  # 带分页的数据
    items: List[dict]
    total: int = 0


@router.get("/{resource}/list")
def list_view(
    request: Request,
    page_model: ModelAdmin = Depends(get_model_site),
    perPage: int = 10,
    page: int = 1,
    session: Session = Depends(get_db_session),
    user: Optional[User] = Depends(decode_access_token_from_data),
):
    if not user:
        return RedirectResponse(request.url_for("admin:login"))
    sql = page_model.get_list_sql()
    if sql == None:
        return BaseRes()
    datas = session.execute(sql.limit(perPage).offset((page - 1) * perPage))
    items = []
    for data in datas:
        items.append(dict(data))
    s = session.execute(select(func.count()).select_from(page_model.model))
    total = 0
    for i in s:
        total = i[0]
    return BaseRes(
        data=ListDataWithPage(
            total=total,
            items=items,
        )
    )


@router.put("/{resource}/update")
def update_data(
    request: Request,
    page_model: ModelAdmin = Depends(get_model_site),
    session: Session = Depends(get_db_session),
    data: dict = Depends(get_data),
    user: Optional[User] = Depends(decode_access_token_from_data),
):
    if not user:
        return RedirectResponse(request.url_for("admin:login"))
    data = clean_data_to_model(page_model.get_clean_fields(page_model.update_fields), data)
    w = get_pks(page_model, request)
    if isinstance(w, BaseRes):
        return w
    old_data = session.execute(select(page_model.model).where(*w)).scalar_one_or_none()
    if not old_data:
        return not_found_instance
    page_model.update_model(old_data, data)
    session.commit()
    return BaseRes()


@router.get("/{resource}/update")
def update_view(
    request: Request,
    page_model: ModelAdmin = Depends(get_model_site),
    session: Session = Depends(get_db_session),
    user: Optional[User] = Depends(decode_access_token_from_data),
):
    if not user:
        return RedirectResponse(request.url_for("admin:login"))

    pks = get_pks(page_model, request)
    if isinstance(pks, BaseRes):
        return pks
    data = session.execute(page_model.get_one_sql(pks)).fetchone()
    if not data:
        return not_found_instance
    return BaseRes(data=dict(data))


@router.post("/{resource}/create")
def create(
    request: Request,
    data: dict = Depends(get_data),
    page_model: ModelAdmin = Depends(get_model_site),
    session: Session = Depends(get_db_session),
    user: Optional[User] = Depends(decode_access_token_from_data),
):
    if not user:
        return RedirectResponse(request.url_for("admin:login"))

    data = clean_data_to_model(page_model.create_fields, data)
    instance = page_model.create_model(data)
    session.add(instance)
    session.commit()
    return BaseRes(data=data)


@router.delete("/{resource}/delete")
def delete_one(
    request: Request,
    page_model: ModelAdmin = Depends(get_model_site),
    session: Session = Depends(get_db_session),
    user: Optional[User] = Depends(decode_access_token_from_data),
):
    if not user:
        return RedirectResponse(request.url_for("admin:login"))

    w = get_pks(page_model, request)
    if isinstance(w, BaseRes):
        return w
    session.execute(delete(page_model.model).where(*w))
    session.commit()
    return BaseRes()


def get_pks(page_model: ModelAdmin, request: Request):
    """
    获取要查询的单个instance的主键
    """
    params = dict(request.query_params)
    pks = get_pk(page_model.model)
    w = []
    for k, v in params.items():
        if pks.get(k) is not None:
            field = pks[k]
            if isinstance(
                field.type, (Integer, DECIMAL, BigInteger, Float, INTEGER, Numeric, SmallInteger)
            ):
                w.append(pks[k] == int(v))
            elif isinstance(field.type, DateTime):
                w.append(pks[k] == datetime.strptime(v, "%Y-%m-%dT%H:%M:%S"))
            else:
                w.append(pks[k] == v)
        else:
            return key_error
    return w


class DIDS(BaseModel):
    ids: List[int]


#  todo next version
# @router.post("/{resource}/deleteMany/")
# def bulk_delete(request: Request, ids: DIDS,
#                 model_site: Optional[ModelAdmin] = Depends(get_model_site),
#
#                 ):
#     # await model.filter(pk__in=ids.ids).delete()
#     return BaseRes()


@router.get("/{resource}/schema")
def get_schema(
    request: Request,
    page: ModelAdmin = Depends(get_model_site),
    user: Optional[User] = Depends(decode_access_token_from_data),
):
    if not user:
        return RedirectResponse(request.url_for("admin:login"))

    return BaseRes(data=page.get_app_page())


@router.get("/{resource}/selects/{field}")
def get_selects(
    request: Request,
    field: str = Path(...),  # type: ignore
    page_model: ModelAdmin = Depends(get_model_site),
    user: Optional[User] = Depends(decode_access_token_from_data),
    session: Session = Depends(get_db_session),
    perPage: int = 10,
    page: int = 1,
):
    source_field = getattr(page_model.model, field)
    relation_model = source_field.property.mapper.class_

    datas = session.execute(
        select(list(get_pk(relation_model).values())).limit(perPage).offset((page - 1) * perPage)
    )
    items = []
    for data in datas:
        items.append(dict(data))
    s = session.execute(select(func.count()).select_from(relation_model))
    total = 0
    for i in s:
        total = i[0]
    return BaseRes(data={"total": total, "rows": items})
