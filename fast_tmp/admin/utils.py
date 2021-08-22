from typing import Callable, Dict, List, Optional, Tuple, Type

from tortoise import (
    BackwardFKRelation,
    BackwardOneToOneRelation,
    ForeignKeyFieldInstance,
    ManyToManyFieldInstance,
    Model,
    OneToOneFieldInstance,
)
from tortoise.fields import (
    BigIntField,
    BooleanField,
    CharField,
    DateField,
    DatetimeField,
    DecimalField,
    Field,
    FloatField,
    IntField,
    JSONField,
    SmallIntField,
    TextField,
    TimeDeltaField,
    UUIDField,
)
from tortoise.fields.data import CharEnumFieldInstance, IntEnumFieldInstance

from fast_tmp.admin.schema.abstract_schema import _Action
from fast_tmp.admin.schema.actions import DialogAction
from fast_tmp.admin.schema.crud import CRUD
from fast_tmp.admin.schema.forms import Column, Control, Mapping
from fast_tmp.admin.schema.forms.enums import FormWidgetSize, ItemModel
from fast_tmp.admin.schema.forms.widgets import (
    DateItem,
    DatetimeItem,
    NumberItem,
    SelectItem,
    SelectOption,
    SwitchItem,
    TextItem,
    TimeItem,
    UUIDItem,
)
from fast_tmp.admin.schema.frame import Dialog
from fast_tmp.conf import settings


def _get_base_attr(field_type: Field, **kwargs) -> dict:
    res = dict(
        className=None,
        inputClassName=None,
        labelClassName=None,
        name=field_type.model_field_name,
        label=field_type.model_field_name,
        labelRemark=None,
        description=None,
        placeholder=None,
        inline=False,
        submitOnChange=False,
        disabled=False,
        disableOn=None,
        required=field_type.required,
        mode=ItemModel.normal,
        size=FormWidgetSize.md,
        value=field_type.default()
        if isinstance(field_type.default, Callable)
        else field_type.default,
        # fixme:注意如果参数为函数该怎么办
    )
    res.update(kwargs)
    return res


def get_columns_from_model(
    model: Type[Model],
    include: Tuple[str, ...] = (),
    exclude: Tuple[str, ...] = (),
    extra_fields: Dict[str, _Action] = None,
) -> List[Column]:
    """
    从pydantic_queryset_creator创建的schema获取字段
    """
    fields = model._meta.fields_map  # todo：增加多对多字段显示
    if not extra_fields:
        extra_fields = {}
    res = []
    if hasattr(model, "Amis") and hasattr(model.Amis, "name_label"):
        name_label: dict = model.Amis.name_label
    else:
        name_label = {}
    for field, field_type in fields.items():
        if include and field not in include or exclude and field in exclude:
            continue

        if field in extra_fields.keys():
            res.append(extra_fields[field])
            continue
        if field_type.reference is not None:  # 忽略外键
            continue
        if field in name_label.keys():
            res.append(Column(name=field, label=name_label[field]))
        elif isinstance(field_type, (IntEnumFieldInstance, CharEnumFieldInstance)):
            res.append(
                Mapping(
                    name=field,
                    label=field,
                    map={k: v for k, v in field_type.enum_type.choices.items()},
                )
            )
        elif isinstance(field_type, (ManyToManyFieldInstance, BackwardFKRelation)):
            related_model = model._meta.fields_map[field].related_model
            cs = []
            if hasattr(model, "Amis") and hasattr(model.Amis, "relation_label"):  # mypy:itnore
                for k, v in model.Amis.relation_label:  # mypy:itnore
                    if k == field:
                        r_f: Field = getattr(
                            related_model._meta, model.Amis.relation_label[field]
                        )  # mypy:itnore
                        cs = [
                            Column(
                                name=related_model._meta.pk_attr, label=related_model._meta.pk_attr
                            ),
                            Column(
                                label=r_f.description
                                or model.Amis.relation_label[field],  # mypy:itnore
                                name=model.Amis.relation_label[field],
                            ),
                        ]
            if not cs:
                cs = [Column(name=related_model._meta.pk_attr, label=related_model._meta.pk_attr)]
            res.append(
                DialogAction(
                    label=field,
                    dialog=Dialog(
                        title=field + "列表",
                        body=CRUD(
                            api="get:"
                            + f"{settings.ADMIN_PREFIX}/{model.__name__}/backrelation/"
                            + "${"
                            + model._meta.pk_attr
                            + "}"
                            + "?field="
                            + field,
                            columns=cs,
                        ),
                    ),
                )
            )
        elif (
            isinstance(field_type, (OneToOneFieldInstance, ForeignKeyFieldInstance))
            and hasattr(model, "Amis")
            and hasattr(model.Amis, "relation_label")  # mypy:itnore
            and model.Amis.relation_label.get(field)  # mypy:itnore
        ):
            res.append(
                Mapping(
                    name=field,
                    label=field,
                    source=f"get:{settings.ADMIN_PREFIX}/{model.__name__}/mapping?field={field}",
                )
            )
        else:
            res.append(Column(name=field, label=field))
    return res


def get_controls_from_model(
    model: Type[Model],
    include: Tuple[str, ...] = (),
    exclude: Tuple[str, ...] = (),
    extra_controls: Optional[Tuple[Column, ...]] = None,
    extra_fields: Dict[str, Control] = None,
    exclude_readonly: bool = True,
) -> List[Control]:
    """
    从pydantic_queryset_creator创建的schema获取字段
    extra_fields:额外的自定义字段
    """
    if not extra_fields:
        extra_fields = {}
    fields = model._meta.fields_map
    res = []
    for field, field_type in fields.items():
        if include and field not in include or (exclude and field in exclude):
            continue
        if exclude_readonly and field_type.pk:
            continue
        if field_type.reference is not None:  # 忽略外键
            continue
        if field in extra_fields.keys():
            res.append(extra_fields[field])
            continue
        if isinstance(field_type, (IntField, SmallIntField, BigIntField)):
            if isinstance(field_type, IntEnumFieldInstance):
                enum_type = field_type.enum_type
                res.append(
                    SelectItem(
                        options=[
                            SelectOption(label=label, value=value)
                            for value, label in enum_type.choices.items()
                        ],
                        **_get_base_attr(field_type),
                    ),
                )
            else:
                res.append(
                    NumberItem(
                        min=field_type.constraints.get("ge") or None,
                        max=field_type.constraints.get("le") or None,
                        precision=0,
                        step=1,
                        **_get_base_attr(field_type),
                        validations={
                            "minimum": field_type.constraints.get("ge") or None,
                            "maximum": field_type.constraints.get("le") or None,
                        },
                    ),
                )
        elif isinstance(field_type, CharField):
            if isinstance(field_type, CharEnumFieldInstance):
                enum_type = field_type.enum_type
                res.append(
                    SelectItem(
                        options=[
                            SelectOption(label=label, value=value)
                            for value, label in enum_type.choices.items()
                        ],
                        **_get_base_attr(field_type),
                    ),
                )
            else:
                res.append(
                    TextItem(
                        **_get_base_attr(field_type),
                        validations={
                            "maxLength": field_type.max_length or None,
                        },
                    )
                )
        # todo:等待完成,另，需要完成date
        elif isinstance(field_type, DatetimeField):
            res.append(
                DatetimeItem(
                    **_get_base_attr(field_type),
                    format="YYYY-MM-DD HH:mm:ss",
                    inputFormat="YYYY-MM-DD HH:mm:ss",
                )
            )
        elif isinstance(field_type, DateField):
            res.append(
                DateItem(
                    **_get_base_attr(field_type),
                    format="YYYY-MM-DD",
                    inputFormat="YYYY-MM-DD",
                )
            )
        elif isinstance(field_type, TimeDeltaField):
            res.append(
                TimeItem(
                    **_get_base_attr(field_type),
                    format="HH:mm",
                    inputFormat="HH:mm",
                    timeConstrainst=False,
                )
            )
        elif isinstance(field_type, CharEnumFieldInstance):  # fixme:需要修复
            print(field_type.enum_type)
        elif isinstance(field_type, BooleanField):
            if field_type.default is False:
                res.append(
                    SwitchItem(
                        name=field_type.model_field_name,
                        label="开关",
                        trueValue=True,
                        falseValue=False,
                        value=True,  # fixme：测试是否具有默认值
                    )
                )
            else:
                enum_type = {"True": True, "False": False}
                res.append(
                    SelectItem(
                        options=[
                            SelectOption(label=label, value=value) for value, label in enum_type
                        ],
                        **_get_base_attr(
                            field_type,
                            default={"label": "True", "value": True}
                            if field_type.default
                            else {"label": "False", "value": False},
                        ),
                    ),
                )
        elif isinstance(field_type, FloatField):
            validation = {}
            if field_type.constraints.get("ge") and field_type.constraints.get("le"):
                validation["minimum"] = field_type.constraints.get("ge")
                validation["maximum"] = field_type.constraints.get("le")
            res.append(
                NumberItem(
                    min=field_type.constraints.get("ge"),
                    max=field_type.constraints.get("le"),
                    precision=None,
                    step=1,
                    showSteps=None,
                    **_get_base_attr(field_type),
                    validations=validation,
                )
            )
        elif isinstance(field_type, DecimalField):
            validation = {}
            if field_type.constraints.get("ge") is not None:
                validation["minimum"] = field_type.constraints.get("ge")
            if field_type.constraints.get("le") is not None:
                validation["maximum"] = field_type.constraints.get("le")
            res.append(
                NumberItem(
                    min=field_type.constraints.get("ge"),
                    max=field_type.constraints.get("le"),
                    precision=2,
                    step=1,
                    showSteps=None,
                    **_get_base_attr(field_type),
                    validations=validation,
                )
            )
        elif isinstance(field_type, JSONField):  # fixme:需要解决tortoise-orm字段问题
            pass
        elif isinstance(field_type, TextField):
            res.append(
                TextItem(
                    **_get_base_attr(field_type),
                )
            )
        elif isinstance(field_type, UUIDField):
            res.append(UUIDItem(**_get_base_attr(field_type), length=None))
        elif isinstance(field_type, ManyToManyFieldInstance):
            res.append(
                SelectItem(
                    **_get_base_attr(field_type, required=False),
                    source=f"get:{settings.ADMIN_PREFIX}/{model.__name__}/select?field={field}",
                    multiple=True,
                    extractValue=True,
                    joinValues=False,
                )
            )
        elif isinstance(field_type, BackwardFKRelation):
            pass
        elif isinstance(
            field_type, (ForeignKeyFieldInstance, OneToOneFieldInstance, BackwardOneToOneRelation)
        ):
            res.append(
                SelectItem(
                    **_get_base_attr(field_type, name=field),
                    source=f"get:{settings.ADMIN_PREFIX}/{model.__name__}/select?field={field}",
                )
            )
        else:
            raise ValueError(f"{field}字段的字段类型尚不支持!")
    if extra_controls:
        res.extend(extra_controls)
    return res
