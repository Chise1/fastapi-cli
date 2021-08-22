from datetime import datetime, timedelta

# type: ignore
from jose import jwt

from fast_tmp.conf import settings

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM


def create_access_token(data: dict, expires_delta: timedelta):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(
    token: str,
):
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
