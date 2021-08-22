from typing import Iterable, Optional, Union

# noinspection Mypy
from cas import CASClient
from fastapi import Cookie, Depends, FastAPI, HTTPException, status

from fast_tmp.conf import settings
from fast_tmp.depends.auth import get_current_user
from fast_tmp.models import Permission, User

app = FastAPI()
cas_client = CASClient(
    version=3,
    service_url="http://127.0.0.1:8002/login?next=%2Fprofile",
    server_url=settings.CAS_SERVER_URL,
)


def decode_cookie(s: str) -> str:
    """
    解码cookie
    """

    return s


async def get_user_from_cookie(username: Optional[str] = Cookie(None)) -> Optional[User]:
    if username:
        username_decode = decode_cookie(username)
        user = await User.filter(username=username_decode).first()
    else:
        user = None
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_superuser(current_user: User = Depends(get_current_active_user)):
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return current_user


def get_user_has_perms(perms: Iterable[Union[Permission, str]]):
    """# type:ignore
    判定用户是否具有相关权限
    :param perms:
    :return:
    """

    async def user_has_perms(user: User = Depends(get_current_active_user)):
        if await user.has_perms(perms):
            return user
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

    return user_has_perms
