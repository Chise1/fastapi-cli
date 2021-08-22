from typing import Any, Dict, List, Type, cast

import pydantic
from tortoise.contrib.pydantic.base import PydanticListModel


def pydantic_offsetlimit_creator(schema: Type[pydantic.BaseModel]) -> Type[pydantic.BaseModel]:
    """
    生成分页用的schema
    """

    lname = f"{schema.__name__}_paging"

    properties: Dict[str, Any] = {
        "__annotations__": {"data": List[schema], "total": int},
    }  # type: ignore
    model = cast(Type[PydanticListModel], type(lname, (PydanticListModel,), properties))
    setattr(model.__config__, "title", f"{getattr(schema.__config__, 'title')}_limitoffset")
    return model
