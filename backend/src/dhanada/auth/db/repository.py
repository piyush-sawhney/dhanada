"""Repository pattern for database operations."""

import uuid
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from dhanada.auth.models.base import BaseModel
from dhanada.auth.models.refresh_token import RefreshToken
from dhanada.auth.models.role import Role, UserRole
from dhanada.auth.models.totp import TOTPSecret
from dhanada.auth.models.user import User

ModelT = TypeVar("ModelT", bound=BaseModel)


class BaseRepository(Generic[ModelT]):
    """Generic CRUD repository."""

    def __init__(self, model_class: type[ModelT], session: AsyncSession) -> None:
        self._model = model_class
        self._session = session

    async def create(self, *, created_by_id: uuid.UUID | None = None, **kwargs: Any) -> ModelT:
        if created_by_id is not None:
            kwargs["created_by_id"] = created_by_id
        instance = self._model(**kwargs)
        self._session.add(instance)
        await self._session.flush()
        return instance

    async def get(self, id: uuid.UUID) -> ModelT | None:
        result = await self._session.execute(
            select(self._model).where(self._model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_all(self) -> list[ModelT]:
        result = await self._session.execute(select(self._model))
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(self._model)
        )
        return result.scalar_one()

    async def update(self, id: uuid.UUID, *, updated_by_id: uuid.UUID | None = None, **kwargs: Any) -> ModelT | None:
        if updated_by_id is not None:
            kwargs["updated_by_id"] = updated_by_id
        result = await self._session.execute(
            update(self._model).where(self._model.id == id).values(**kwargs).returning(self._model)
        )
        await self._session.flush()
        return result.scalar_one_or_none()

    async def delete(self, id: uuid.UUID) -> bool:
        result = await self._session.execute(
            delete(self._model).where(self._model.id == id)
        )
        await self._session.flush()
        return result.rowcount > 0


class UserRepository(BaseRepository[User]):
    """User-specific repository operations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(User, session)

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        result = await self._session.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def update_last_login(self, user_id: uuid.UUID) -> None:
        await self._session.execute(
            update(User)
            .where(User.id == user_id)
            .values(last_login=datetime.now(UTC))
        )
        await self._session.flush()

    async def delete(self, id: uuid.UUID, *, deleted_by_id: uuid.UUID | None = None) -> bool:
        now = datetime.now(UTC)
        return await self.update(id, deleted_at=now, deleted_by_id=deleted_by_id) is not None


class RoleRepository(BaseRepository[Role]):
    """Role-specific repository operations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Role, session)

    async def get_by_name(self, name: str) -> Role | None:
        result = await self._session.execute(
            select(Role).where(Role.name == name)
        )
        return result.scalar_one_or_none()

    async def get_user_roles(self, user_id: uuid.UUID) -> list[Role]:
        result = await self._session.execute(
            select(UserRole).where(UserRole.user_id == user_id)
        )
        user_roles = result.scalars().all()
        return [ur.role for ur in user_roles]

    async def assign_role_to_user(
        self, user_id: uuid.UUID, role_id: uuid.UUID,
        *, created_by_id: uuid.UUID | None = None,
    ) -> bool:
        user = await self._session.get(User, user_id)
        role = await self.get(role_id)
        if user is None or role is None:
            return False
        existing = await self._session.execute(
            select(UserRole).where(
                UserRole.user_id == user_id, UserRole.role_id == role_id
            )
        )
        if existing.scalar_one_or_none() is not None:
            return True
        user_role = UserRole(
            user_id=user_id, role_id=role_id,
            created_by_id=created_by_id,
        )
        self._session.add(user_role)
        await self._session.flush()
        return True

    async def remove_role_from_user(self, user_id: uuid.UUID, role_id: uuid.UUID) -> bool:
        result = await self._session.execute(
            delete(UserRole).where(
                UserRole.user_id == user_id, UserRole.role_id == role_id
            )
        )
        await self._session.flush()
        return result.rowcount > 0

    async def get_permissions(self, user_id: uuid.UUID) -> list[str]:
        result = await self._session.execute(
            select(UserRole).where(UserRole.user_id == user_id)
        )
        user_roles = result.scalars().all()
        permissions: list[str] = []
        for ur in user_roles:
            for perm in ur.role.permissions:
                permissions.append(f"{perm.resource}:{perm.action}")
        return permissions

    async def check_permission(
        self, user_id: uuid.UUID, resource: str, action: str
    ) -> bool:
        user = await self._session.execute(
            select(User).where(User.id == user_id)
        )
        user_obj = user.scalar_one_or_none()
        if user_obj is None or user_obj.deleted_at is not None:
            return False
        if user_obj.is_superuser:
            return True
        result = await self._session.execute(
            select(UserRole).where(UserRole.user_id == user_id)
        )
        user_roles = result.scalars().all()
        for ur in user_roles:
            for perm in ur.role.permissions:
                if perm.resource == resource and perm.action == action:
                    return True
        return False


class TOTPRepository(BaseRepository[TOTPSecret]):
    """TOTP-specific repository operations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(TOTPSecret, session)

    async def get_by_user_id(self, user_id: uuid.UUID) -> TOTPSecret | None:
        result = await self._session.execute(
            select(TOTPSecret).where(TOTPSecret.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def upsert(self, user_id: uuid.UUID, **kwargs: Any) -> TOTPSecret:
        existing = await self.get_by_user_id(user_id)
        if existing is not None:
            return await self.update(existing.id, **kwargs)
        return await self.create(user_id=user_id, **kwargs)

    async def delete_by_user_id(self, user_id: uuid.UUID) -> bool:
        existing = await self.get_by_user_id(user_id)
        if existing is None:
            return False
        return await self.delete(existing.id)


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    """Refresh token-specific repository operations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(RefreshToken, session)

    async def get_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self._session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def get_active_by_user(self, user_id: uuid.UUID) -> list[RefreshToken]:
        now = datetime.now(UTC)
        result = await self._session.execute(
            select(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.replaced_at.is_(None),
                RefreshToken.expires_at > now,
            )
        )
        return list(result.scalars().all())

    async def get_family_tokens(self, family_id: uuid.UUID) -> list[RefreshToken]:
        result = await self._session.execute(
            select(RefreshToken)
            .where(RefreshToken.family_id == family_id)
            .order_by(RefreshToken.created_at)
        )
        return list(result.scalars().all())

    async def revoke_user_tokens(self, user_id: uuid.UUID) -> int:
        now = datetime.now(UTC)
        result = await self._session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        await self._session.flush()
        return result.rowcount

    async def revoke_family(self, family_id: uuid.UUID) -> int:
        now = datetime.now(UTC)
        result = await self._session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.family_id == family_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        await self._session.flush()
        return result.rowcount
