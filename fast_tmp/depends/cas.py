"""
@Time    : 2021/2/6 12:46
@Author  : yuxiaofei
@info    : cas协议的登录
"""

from typing import Any, List, Optional

from cas import CASClient
from fastapi import Cookie, Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError

from fast_tmp.conf import settings
from fast_tmp.depends.auth import get_current_user, get_user, oauth2_scheme
from fast_tmp.models import User
from fast_tmp.utils.token import decode_access_token

app = FastAPI()
cas_client = CASClient(
    version=3,
    service_url="http://127.0.0.1:8002/login?next=%2Fprofile",
    server_url=settings.CAS_SERVER_URL + "/cas/",
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


async def get_current_user_from_cookie(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = await get_user(username=username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_superuser(current_user: User = Depends(get_current_active_user)):
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return current_user


def get_user_has_perms(perms: List[Any]):
    """
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
