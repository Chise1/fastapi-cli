import inspect
from typing import Any, Optional, Tuple


def add_filter(func: Any, filters: Optional[Tuple[str, ...]] = None):
    signature = inspect.signature(func)
    res = []
    for k, v in signature.parameters.items():
        if k == "kwargs":
            continue
        res.append(v)
    if filters:
        for filter_ in filters:
            res.append(
                inspect.Parameter(
                    filter_, kind=inspect.Parameter.KEYWORD_ONLY, annotation=str, default="__null__"
                )
            )
    # noinspection Mypy,PyArgumentList
    func.__signature__ = inspect.Signature(
        parameters=res, __validate_parameters__=False
    )  # type:ignore
