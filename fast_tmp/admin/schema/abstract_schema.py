from typing import Optional, TypeVar, Union

from pydantic.main import BaseModel

from fast_tmp.admin.schema.enums import ActionTypeEnum, ButtonLevelEnum, ButtonSize, TypeEnum


class BaseAmisModel(BaseModel):
    """
    所有amis类的父类
    """

    type: Union[TypeEnum, str]


AmisModel = TypeVar("AmisModel", bound=BaseAmisModel)


class _Action(BaseAmisModel):
    """
    操作按钮
    """

    type = TypeEnum.action
    label: str
    actionType: ActionTypeEnum
    icon: Optional[str]
    size: ButtonSize = ButtonSize.md
    level: ButtonLevelEnum = ButtonLevelEnum.primary
    tooltip: Optional[str]  # 鼠标挪上去的提示


class Message(BaseModel):
    """
    消息框
    """

    fetchSucss: Optional[str]
    fetchFailed: Optional[str]
    saveSuccess: Optional[str]
    saveFailed: Optional[str]
