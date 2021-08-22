from typing import Iterable, List, Union

from tortoise import Model, fields

from fast_tmp.conf import settings


class Permission(Model):
    label = fields.CharField(max_length=128)
    codename = fields.CharField(max_length=128, unique=True)
    groups: fields.ManyToManyRelation["Group"]

    def __eq__(self, other) -> bool:
        if other == self.codename or getattr(other, "codename", None) == self.codename:
            return True
        return False

    def __str__(self):
        return self.label

    def __repr__(self):
        return self.label

    class Meta:
        ordering = ["id"]


class User(Model):
    username = fields.CharField(max_length=128, unique=True)
    password = fields.CharField(max_length=255)
    is_active = fields.BooleanField(default=True)
    is_superuser = fields.BooleanField(default=False)
    groups: fields.ManyToManyRelation["Group"]

    class Meta:
        abstract = settings.AUTH_USER_MODEL_NAME != "User"
        ordering = ["id"]

    def set_password(self, raw_password: str):
        """
        设置密码
        """
        from fast_tmp.utils.password import make_password

        self.password = make_password(raw_password)

    def verify_password(self, raw_password: str) -> bool:
        """
        验证密码
        """
        from fast_tmp.utils.password import verify_password

        return verify_password(raw_password, self.password)

    @property
    async def perms(self) -> List[Permission]:
        if not hasattr(self, "__perms"):
            permission_instances = await Permission.filter(groups__users=self.pk)
            self.__perms = permission_instances
        return self.__perms  # mypy:ignore

    async def has_perm(self, perm: Union[Permission, str]) -> bool:
        """
        判定用户是否有权限
        """
        if self.is_superuser:
            return True
        for permission_instance in await self.perms:
            if permission_instance == perm:
                return True
        return False

    async def has_perms(self, perms: Iterable[Union[Permission, str], ...]) -> bool:
        """
        根据permission的codename进行判定
        """
        if self.is_superuser:
            return True
        for perm in perms:
            for perm_instance_codename in await self.perms:
                if perm == perm_instance_codename:
                    continue
            else:
                return False
        return True

    async def get_perms(self):
        return self.perms

    def __str__(self):
        return self.username


class Group(Model):
    name = fields.CharField(max_length=128, unique=True)
    permissions = fields.ManyToManyField(
        f"{settings.AUTH_APP_NAME}.Permission", related_name="groups"
    )
    users = fields.ManyToManyField(
        f"{settings.AUTH_APP_NAME}.{settings.AUTH_USER_MODEL_NAME}", related_name="groups"
    )

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["id"]
