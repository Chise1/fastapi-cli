from typing import List, Optional, Tuple, Type

from fastapi import APIRouter, Depends
from pydantic.main import BaseModel
from starlette import status
from tortoise import (
    BackwardFKRelation,
    BackwardOneToOneRelation,
    ForeignKeyFieldInstance,
    ManyToManyFieldInstance,
    Model,
    OneToOneFieldInstance,
)
from tortoise.query_utils import Q
from tortoise.queryset import QuerySet

from fast_tmp.depends.auth import get_user_has_perms
from fast_tmp.utils.crud_tools import add_filter
from fast_tmp.utils.pydantic import pydantic_model_creator
from fast_tmp.utils.pydantic_creator import pydantic_offsetlimit_creator


def add_fetch_field_search(queryset: QuerySet, include_fields: Tuple[str, ...]):
    """
    获取列表的时候对额外字段也进行获取
    """
    fields_map = queryset.model._meta.fields_map
    select_fields = []
    fetch_fields = []
    for field_name, field in fields_map.items():
        if isinstance(field, (ForeignKeyFieldInstance, OneToOneFieldInstance)):  # 外键,一对一
            if (include_fields and field_name in include_fields) or not include_fields:
                select_fields.append(field_name)
        elif isinstance(
            field, (BackwardFKRelation, BackwardOneToOneRelation, ManyToManyFieldInstance)
        ):  # 反向外键,反向一对一,多对多
            if (include_fields and field_name in include_fields) or not include_fields:
                fetch_fields.append(field_name)
        else:  # 一般键
            pass
    if select_fields:
        queryset = queryset.select_related(*select_fields)
    if fetch_fields:
        queryset = queryset.prefetch_related(*fetch_fields)
    return queryset


async def check_filter_kwargs(kwargs, query, schema):
    if kwargs:
        s = {}
        for k, v in kwargs.items():
            if not v == "__null__":
                s[k] = v
            else:
                pass
        if s:
            query = query.filter(**s)
    data = await query
    return [schema.from_orm(i) for i in data]


async def check_filter_kwargs_with_page(count, kwargs, query, schema, paging_schema):
    if kwargs:
        s = {}
        for k, v in kwargs.items():
            if not v == "__null__":
                s[k] = v
            else:
                pass
        if s:
            query = query.filter(**s)
            count = count.filter(**s)
    data = await query
    return paging_schema(total=await count.count(), data=[schema.from_orm(i) for i in data])


def create_list_route(
    route: APIRouter,
    path: str,
    model: Type[Model],
    fields: Tuple[str, ...] = (),
    computed_fields: Tuple[str, ...] = (),
    codenames: Tuple[str, ...] = (),
    searchs: Tuple[str, ...] = (),
    filters: Tuple[str, ...] = (),
    res_pydantic_model: Optional[Type[BaseModel]] = None,
    random_str: str = "",
    allow_cycles: bool = True,
    depth: int = 1,
    **kw,
):
    """
    创建list的路由
    """
    if res_pydantic_model:
        schema = res_pydantic_model
    else:
        schema = pydantic_model_creator(
            model,
            name=f"CREATORList{model.__name__}{path.replace('/', '_')}{random_str}",
            include=fields,
            computed=computed_fields,
            allow_cycles=allow_cycles,
            depth=depth,
        )
    if searchs:

        async def model_list(
            search: Optional[str] = None,
            **kwargs,
        ):
            query = model.all()
            if search:
                x = [Q(**{f"{i}__contains": search}) for i in searchs]
                if x:
                    q = x[0]
                    for i in x[1:]:
                        q = q | i
                    query = query.filter(q)
            query = add_fetch_field_search(
                query,
                fields,
            )
            return await check_filter_kwargs(kwargs, query, schema)

    else:

        async def model_list(
            **kwargs,
        ):
            query = model.all()
            query = add_fetch_field_search(query, fields)
            return await check_filter_kwargs(kwargs, query, schema)

    add_filter(model_list, filters)
    route.get(
        path,
        dependencies=[Depends(get_user_has_perms(codenames))],
        response_model=List[schema],  # tpye:ignore
        **kw,
    )(model_list)


def create_list_route_with_page(
    route: APIRouter,
    path: str,
    model: Type[Model],
    fields: Tuple[str, ...] = (),
    computed_fields: Tuple[str, ...] = (),
    codenames: Tuple[str, ...] = (),
    searchs: Tuple[str, ...] = (),
    filters: Tuple[str, ...] = (),
    res_pydantic_model: Optional[Type[BaseModel]] = None,
    random_str: str = "",
    **kw,
):
    """
    创建list的路由
    """
    if res_pydantic_model:
        schema = res_pydantic_model
    else:
        schema = pydantic_model_creator(
            model,
            name=f"CREATORList{model.__name__}{path.replace('/', '_')}Page{random_str}",
            include=fields,
            computed=computed_fields,
        )
    paging_schema = pydantic_offsetlimit_creator(schema)
    if searchs:

        async def model_list(
            offset: int = 0,
            limit: int = 10,
            search: Optional[str] = None,
            **kwargs,
        ):
            count = model.all()
            query = model.all().limit(limit).offset(offset)
            if search:
                x = [Q(**{f"{i}__contains": search}) for i in searchs]
                if x:
                    q = x[0]
                    for i in x[1:]:
                        q = q | i
                    query = query.filter(q)
                    count = count.filter(q)
            query = add_fetch_field_search(query, fields)
            return await check_filter_kwargs_with_page(count, kwargs, query, schema, paging_schema)

    else:

        async def model_list(
            offset: int = 0,
            limit: int = 10,
            **kwargs,
        ):
            count = model.all()
            query = model.all().limit(limit).offset(offset)
            query = add_fetch_field_search(query, fields)
            return await check_filter_kwargs_with_page(count, kwargs, query, schema, paging_schema)

    add_filter(model_list, filters)
    route.get(
        path,
        dependencies=[Depends(get_user_has_perms(codenames))],
        response_model=paging_schema,
        **kw,
    )(model_list)


def create_retrieve_route(
    route: APIRouter,
    path: str,
    model: Type[Model],
    fields: Tuple[str, ...] = (),
    computed_fields: Tuple[str, ...] = (),
    codenames: Tuple[str, ...] = (),
    res_pydantic_model: Optional[Type[BaseModel]] = None,
    random_str: str = "",
    **kw,
):
    if res_pydantic_model:
        schema = res_pydantic_model
    else:
        schema = pydantic_model_creator(
            model,
            name=f"CREATORRetrieve{model.__name__}{path.replace('/', '_')}ID{random_str}",
            include=fields,
            computed=computed_fields,
        )

    async def model_retrieve(
        id: int,
    ):
        instance = await model.get(pk=id)
        return schema.from_orm(instance).dict()

    route.get(
        path + "/{id}",
        dependencies=[Depends(get_user_has_perms(codenames))],
        **kw,
    )(model_retrieve)


def create_delete_route(
    route: APIRouter,
    path: str,
    model: Type[Model],
    codenames: Tuple[str, ...] = (),
    **kw,
):
    """
    删除路由生成器
    """

    async def model_delete(
        id: int,
    ):
        await model.filter(pk=id).delete()

    route.delete(
        path + "/{id}",
        dependencies=[Depends(get_user_has_perms(codenames))],
        status_code=status.HTTP_200_OK,
        **kw,
    )(model_delete)


def create_post_route(
    route: APIRouter,
    path: str,
    model: Type[Model],
    fields: Tuple[str, ...] = (),
    computed_fields: Tuple[str, ...] = (),
    codenames: Tuple[str, ...] = (),
    res_pydantic_model: Type[BaseModel] = None,
    random_str: str = "",
    **kw,
):
    if res_pydantic_model:
        schema = res_pydantic_model
    else:
        schema = pydantic_model_creator(
            model,
            name=f"CREATORPost{model.__name__}{path.replace('/', '_')}{random_str}",
            include=fields,
            computed=computed_fields,
            exclude_readonly=True,
        )

    async def model_post(
        info: schema,  # mypy:itnore
    ):
        await model.create(**info.dict())  # mypy:itnore

    route.post(
        path,
        dependencies=[Depends(get_user_has_perms(codenames))],
        **kw,
    )(model_post)


# fixme:等待测试
def create_put_route(
    route: APIRouter,
    path: str,
    model: Type[Model],
    fields: Tuple[str, ...] = (),
    computed_fields: Tuple[str, ...] = (),
    codenames: Tuple[str, ...] = (),
    res_pydantic_model: Optional[Type[BaseModel]] = None,
    random_str: str = "",
    **kw,
):
    if res_pydantic_model:
        schema = res_pydantic_model
    else:
        schema = pydantic_model_creator(
            model,
            name=f"CREATORPut{model.__name__}{path.replace('/', '_')}{random_str}",
            include=fields,
            computed=computed_fields,
            exclude_readonly=True,
        )

    async def model_put(
        id: int,
        info: schema,  # mypy:itnore
    ):
        await model.filter(pk=id).update(**info.dict())  # mypy:itnore

    route.put(
        path + "/{id}",
        dependencies=[Depends(get_user_has_perms(codenames))],
        **kw,
    )(model_put)
