from typing import Container

import aioredis
from aioredis import Redis


class AsyncRedisUtil:
    """
    异步redis操作,
    配置说明：
        在startup配置：
        await AsyncRedisUtil.init(host,port,...)，参数
        在shutdown配置
        await AsyncRedisUtil.close()
    note:
        exp是指过期时间,单位是秒.
    """

    r: Redis = None

    @classmethod
    async def init(cls, host="localhost", port=6379, password=None, db=0, **kwargs):
        cls.r = await aioredis.create_redis_pool(
            f"redis://{host}:{port}", password=password, db=db, **kwargs
        )
        return cls.r

    @classmethod
    async def _exp_of_none(cls, *args, exp_of_none, callback):
        if not exp_of_none:
            return await getattr(cls.r, callback)(*args)
        key = args[0]
        tr = cls.r.multi_exec()
        fun = getattr(tr, callback)
        exists = await cls.r.exists(key)
        if not exists:
            fun(*args)
            tr.expire(key, exp_of_none)
            ret, _ = await tr.execute()
        else:
            fun(*args)
            ret = (await tr.execute())[0]
        return ret

    @classmethod
    async def set(cls, key, value, exp=None):
        assert cls.r, "must call init first"
        await cls.r.set(key, value, expire=exp)

    @classmethod
    async def get(cls, key, default=None, encoding="utf-8"):
        assert cls.r, "must call init first"
        value = await cls.r.get(key, encoding=encoding)
        if value is None:
            return default
        return value

    @classmethod
    async def hget(cls, name, key, default=0, encoding="utf-8"):
        """
        缓存清除，接收list or str
        """
        assert cls.r, "must call init first"
        v = await cls.r.hget(name, key, encoding=encoding)
        if v is None:
            return default
        return v

    @classmethod
    async def get_or_set(cls, key, default=None, value_fun=None, encoding="utf-8"):
        """
        获取或者设置缓存
        """
        assert cls.r, "must call init first"
        value = await cls.r.get(key, encoding=encoding)
        if value is None and default:
            return default
        if value is not None:
            return value
        if value_fun:
            value, exp = await value_fun()
            await cls.r.set(key, value, expire=exp)
        return value

    @classmethod
    async def delete(cls, key):
        """
        缓存清除，接收list or str
        """
        assert cls.r, "must call init first"
        return await cls.r.delete(key)

    @classmethod
    async def sadd(cls, name, values, exp_of_none=None):
        assert cls.r, "must call init first"
        return await cls._exp_of_none(name, values, exp_of_none=exp_of_none, callback="sadd")

    @classmethod
    async def hset(cls, name, key, value, exp_of_none=None):
        assert cls.r, "must call init first"
        return await cls._exp_of_none(name, key, value, exp_of_none=exp_of_none, callback="hset")

    @classmethod
    async def hdel(cls, name, key, exp_of_none=None):
        assert cls.r, "must call init first"
        return await cls._exp_of_none(name, key, exp_of_none=None, callback="hdel")

    @classmethod
    async def hincrby(cls, name, key, value=1, exp_of_none=None):
        assert cls.r, "must call init first"
        return await cls._exp_of_none(name, key, value, exp_of_none=exp_of_none, callback="hincrby")

    @classmethod
    async def hincrbyfloat(cls, name, key, value, exp_of_none=None):
        assert cls.r, "must call init first"
        return await cls._exp_of_none(
            name, key, value, exp_of_none=exp_of_none, callback="hincrbyfloat"
        )

    @classmethod
    async def incrby(cls, name, value=1, exp_of_none=None):
        assert cls.r, "must call init first"
        return await cls._exp_of_none(name, value, exp_of_none=exp_of_none, callback="incrby")

    @classmethod
    def multi_exec(cls):
        """
        批量提交的方式,不确定是否为原子性
        eg:
        async def main():
        redis = await aioredis.create_redis_pool('redis://localhost')
        tr = redis.multi_exec()
        tr.set('key1', 'value1')
        tr.set('key2', 'value2')
        ok1, ok2 = await tr.execute()
        assert ok1
        assert ok2
        """
        assert cls.r, "must call init first"
        return cls.r.multi_exec()

    @classmethod
    async def subscribe(cls, channel: str, *channels: Container[str]):
        """
        发布-订阅模式
        :param channel:发布者
        :param channels: 订阅者
        """
        return await cls.r.subscribe(channel, *channels)

    @classmethod
    async def publish(cls, channel: str, message):
        """
        发布消息
        :param channel:发布者
        :param message: 消息
        :return:
        """
        await cls.r.publish(channel, message)

    @classmethod
    async def close(cls):
        cls.r.close()
        await cls.r.wait_closed()
