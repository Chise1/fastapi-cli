from typing import Any, Dict, List, Set, Type

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel
from starlette.requests import Request
from tortoise import (
    BackwardFKRelation,
    BackwardOneToOneRelation,
    ForeignKeyFieldInstance,
    ManyToManyFieldInstance,
    Model,
    OneToOneFieldInstance,
)
from tortoise.queryset import QuerySet
from tortoise.transactions import in_transaction

from fast_tmp.conf import settings

from ..models import Permission, User
from ..utils.common import import_module
from .auth import get_current_active_user, get_user_has_perms
from .creator import AbstractApp, AbstractCRUD
from .depends import get_model
from .res_model import AmisRes

router = APIRouter()


class ListDataWithPage(BaseModel):  # 带分页的数据
    items: List[dict]
    total: int = 0


def get_abstract_app():
    return AbstractApp._instance


def get_app_page(resource: str, app: AbstractApp = Depends(get_abstract_app)) -> AbstractCRUD:
    return app.get_AbstractCRUD(resource)


def get_fields(include_fields, exclude_fields, model, need_m2m: bool = False):
    """
    获取要读取的字段
    """
    if not include_fields:
        map_keys = list(model._meta.fields_map.keys())
        fields = set(map_keys)
        for exclude_field in exclude_fields:
            try:
                fields.remove(exclude_field)
            except ValueError:
                pass
    else:
        fields = set(include_fields)
    relation_fields = set()  # 把多对多和反向外键关系去掉
    for field, field_type in model._meta.fields_map.items():
        if isinstance(field_type, (ManyToManyFieldInstance, BackwardFKRelation)):
            relation_fields.add(field)
    if not need_m2m:
        return fields - relation_fields
    return fields, relation_fields


def get_model_amis_relation_label(model: Type[Model]):
    if hasattr(model, "Amis") and hasattr(model.Amis, "relation_label"):  # type:ignore
        return model.Amis.relation_label  # type:ignore
    return {}


def exclude_reference(fields: Set, model):
    """
    清理关系字段（即生成的authoer_id等实际字段）
    检查并替换跨表查询字段,(只针对外键）
    """
    relation_fields_rename = {}
    fields_value = set()
    for field in fields:
        if model._meta.fields_map[field].reference is not None:
            pass
        # elif load_relation_fields and get_model_amis_relation_label(model).get(field):
        #     relation_fields_rename[field] = field + "__" + model.Amis.relation_label.get(field)
        else:
            if model._meta.fields_map[field].source_field is not None:
                relation_fields_rename[field] = model._meta.fields_map[field].source_field
            else:
                fields_value.add(field)

    return fields_value, relation_fields_rename


def get_select_prefetch_fields(
    qs: QuerySet,
    fields,
    model,
):
    """
    确定需要额外加载那几张表
    """
    map_keys = list(model._meta.fields_map.keys())
    select_fields = []
    prefetch_fields = []
    for field in fields:
        if field not in map_keys:
            f = field.split("__")
            if len(f) != 2:
                raise ValueError(f"{model.__name__} don't have proetry: {field}")
            f_name, sub_name = f
            for k, field_type in model._meta.fields_map:
                if k == f_name:
                    if isinstance(
                        field_type,
                        (
                            ForeignKeyFieldInstance,
                            OneToOneFieldInstance,
                        ),
                    ):
                        select_fields.append(f_name)
                    elif isinstance(
                        field_type,
                        BackwardOneToOneRelation,
                    ):
                        prefetch_fields.append(f_name)
                    else:
                        pass
                    break
            else:
                raise ValueError(f"{model.__name__} don't have proetry: {field}")

    if select_fields:
        qs = qs.select_related(*select_fields)
    if prefetch_fields:
        qs = qs.prefetch_related(*prefetch_fields)
    return qs


@router.get("/{resource}/list", response_model=AmisRes)
async def list_view(
    request: Request,
    abstract_crud: AbstractCRUD = Depends(get_app_page),
    model: Type[Model] = Depends(get_model),
    perPage: int = 10,
    page: int = 1,
    user: User = Depends(get_user_has_perms()),
):
    qs = model.all()
    params = dict(request.query_params)
    params.pop("page")
    params.pop("perPage")
    if params:
        qs = qs.filter(**params)
    total = await qs.count()
    qs = qs.limit(perPage).offset((page - 1) * perPage)
    fields = get_fields(abstract_crud.list_include, abstract_crud.list_exclude, model)
    qs = get_select_prefetch_fields(qs, fields, model)
    fields, relation_fields_rename = exclude_reference(fields, model)
    values = await qs.values(*fields, **relation_fields_rename)
    return AmisRes(
        data=ListDataWithPage(
            total=total,
            items=values,
        ),
    )


@router.put("/{resource}/update/{pk}")
async def update(
    request: Request,
    model: Model = Depends(get_model),
    abstract_crud: AbstractCRUD = Depends(get_app_page),
    pk: int = Path(...),
    user: User = Depends(get_user_has_perms()),
):
    fields, relation_fields = get_fields(
        abstract_crud.up_include, abstract_crud.up_exclude, model, need_m2m=True
    )
    data: dict = await request.json()
    fields, relation_fields_rename = exclude_reference(fields, model)
    data_value = {}
    relation_data: Dict[str, Any] = {}
    relation_fields_keys = relation_fields_rename.keys()
    for k, v in data.items():
        if k in fields:
            data_value[k] = v
        elif k in relation_fields_keys:
            data_value[relation_fields_rename[k]] = v
        else:
            pass
    # 把里面的外键字段更换为对应的数据库字段
    for k, v in data.items():
        for field, field_type in model._meta.fields_map.items():
            if k == field:
                if isinstance(field_type, ForeignKeyFieldInstance):
                    data_value.pop(k)
                    data_value[field_type.source_field] = v
                break

    async with in_transaction() as conn:
        instance = await model.filter(pk=pk).using_db(conn).select_for_update().get()
        await instance.update_from_dict(data_value).save(using_db=conn)
        for k, v in relation_data.items():
            for field, field_type in model._meta.fields_map.items():
                if field == k:
                    if isinstance(field_type, ManyToManyFieldInstance):
                        field_model = model._meta.fields_map[field].related_model  # type:ignore
                        await getattr(instance, k).clear(using_db=conn)  # 清理旧的多对多字段
                        await getattr(instance, k).add(
                            *await field_model.filter(pk__in=v), using_db=conn
                        )
                    break

    return AmisRes()


@router.get("/{resource}/update/{pk}")
async def update_view(
    request: Request,
    pk: int = Path(...),
    abstract_crud: AbstractCRUD = Depends(get_app_page),
    model: Model = Depends(get_model),
    user: User = Depends(get_user_has_perms()),
):
    qs = model.filter(pk=pk)
    fields = get_fields(abstract_crud.up_include, abstract_crud.up_exclude, model)
    qs = get_select_prefetch_fields(qs, fields, model)
    fields, relation_fields_rename = exclude_reference(
        fields,
        model,
    )
    data = await qs.values(*fields, **relation_fields_rename)  # fixme:是字典还是列表？
    return AmisRes(data=data)


@router.post("/{resource}/create")
async def create(
    request: Request,
    abstract_crud: AbstractCRUD = Depends(get_app_page),
    model: Model = Depends(get_model),
    user: User = Depends(get_user_has_perms()),
):
    fields, relation_fields = get_fields(
        abstract_crud.create_include, abstract_crud.create_exclude, model, need_m2m=True
    )
    data: dict = await request.json()
    relation_data = {}
    data_value = {}
    for k, v in data.items():
        if k in relation_fields:
            relation_data[k] = v
        else:
            data_value[k] = v
    # 把里面的外键字段更换为对应的数据库字段
    for k, v in data.items():
        for field, field_type in model._meta.fields_map.items():
            if k == field:
                if isinstance(field_type, ForeignKeyFieldInstance):
                    data_value.pop(k)
                    data_value[field_type.source_field] = v
                break
    async with in_transaction() as conn:
        instance = await model.create(**data_value, using_db=conn)
        for k, v in relation_data.items():
            for field, field_type in model._meta.fields_map.items():
                if field == k:
                    if isinstance(field_type, ManyToManyFieldInstance):
                        field_model = model._meta.fields_map[field].related_model  # type:ignore
                        subs = await field_model.filter(pk__in=v)
                        await getattr(instance, k).add(*subs, using_db=conn)
                    break
    return AmisRes()


@router.delete("/{resource}/delete/{pk}")
async def delete(
    request: Request,
    pk: int,
    model: Model = Depends(get_model),
    user: User = Depends(get_user_has_perms()),
):
    await model.filter(pk=pk).delete()
    return AmisRes()


class DIDS(BaseModel):
    ids: List[int]


@router.post("/{resource}/deleteMany/")
async def bulk_delete(request: Request, ids: DIDS, model: Model = Depends(get_model)):
    await model.filter(pk__in=ids.ids).delete()
    return AmisRes()


#
#
# @router.get("/{resource}/schema")
# async def get_schema(
#     request: Request,
#     resource: str,
#     page: AbstractCRUD = Depends(get_app_page),
#     model: Model = Depends(get_model),
#     user: User = Depends(get_user_has_perms()),
# ):
#     return page.get_Page().dict(exclude_none=True)


@router.get("/{resource}/select")
async def get_schema(
    request: Request,
    field: str = Query(
        ...,
    ),
    page: AbstractCRUD = Depends(get_app_page),
    model: Model = Depends(get_model),
    user: User = Depends(get_user_has_perms()),
):
    field_model = model._meta.fields_map[field].related_model  # type:ignore
    amis_c = getattr(model, "Amis", None)
    if (
        amis_c is not None
        and hasattr(amis_c, "relation_label")
        and amis_c.relation_label.get(field)
    ):
        return await field_model.all().values(
            value=field_model._meta.pk_attr, label=amis_c.relation_label.get(field)
        )
    else:
        return await field_model.all().values(
            label=field_model._meta.pk_attr, value=field_model._meta.pk_attr
        )


@router.get("/{resource}/mapping")
async def get_schema_mapping(
    request: Request,
    field: str = Query(
        ...,
    ),
    page: AbstractCRUD = Depends(get_app_page),
    model: Model = Depends(get_model),
    user: User = Depends(get_user_has_perms()),
):
    field_model = model._meta.fields_map[field].related_model  # type:ignore
    amis_c = getattr(model, "Amis", None)
    if (
        amis_c is not None
        and hasattr(amis_c, "relation_label")
        and amis_c.relation_label.get(field)
    ):
        data = await field_model.all().values(value="id", label=amis_c.relation_label.get(field))
    else:
        data = await field_model.all().values(label="id", value="id")
    res = {}
    for i in data:
        res[i["value"]] = i["label"]
    return AmisRes(data=res)


@router.get("/{resource}/backrelation/{pk}")
async def get_backrealtion_values(
    request: Request,
    field: str = Query(...),
    pk: str = Query(...),
    page: AbstractCRUD = Depends(get_app_page),
    model: Model = Depends(get_model),
    user: User = Depends(get_user_has_perms()),
):
    field_model = model._meta.fields_map[field].related_model  # type:ignore
    # if isinstance(model._meta.fields_map[field],ManyToManyFieldInstance):
    amis_c = getattr(model, "Amis", None)
    if (
        amis_c is not None
        and hasattr(amis_c, "relation_label")
        and amis_c.relation_label.get(field)
    ):
        # return await field_model.all().values(
        #     field_model._meta.pk_attr, amis_c.relation_label.get(field)
        # )
        return (
            await model.filter(pk=pk)
            .prefetch_related(field)
            .values(
                **{
                    field_model._meta.pk_attr: field + "__" + field_model._meta.pk_attr,
                    amis_c.relation_label.get(field): field
                    + "__"
                    + amis_c.relation_label.get(field),
                }
            )
        )

    else:
        return (
            await model.filter(pk=pk)
            .prefetch_related(field)
            .values(**{field_model._meta.pk_attr: field + "__" + field_model._meta.pk_attr})
        )


module: AbstractApp = import_module(settings.EXTRA_SETTINGS["ADMIN_SITE_CLASS"])


@router.get("/site")
async def get_data(user: User = Depends(get_current_active_user)):
    # fixme:修改为基于权限的返回
    if not user.is_superuser:
        user_perms = await user.perms
    else:
        user_perms = await Permission.all()
    return AmisRes(data={"pages": module.dict(user_perms)})
