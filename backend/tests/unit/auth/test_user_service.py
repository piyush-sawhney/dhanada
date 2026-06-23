"""Unit tests for UserService."""
import pytest

from dhanada.auth.db.repository import UserRepository
from dhanada.auth.db.session import DatabaseSession
from dhanada.auth.exceptions import InvalidCredentialsError, ValidationError
from dhanada.auth.services.user_service import UserService

pytestmark = pytest.mark.asyncio


class TestUserService:
    @pytest.fixture
    async def user_repo(self, _ensure_tables, auth_manager) -> UserRepository:
        db = DatabaseSession(str(auth_manager.config.database_url))
        async with db.session() as session:
            yield UserRepository(session)

    @pytest.fixture
    async def user_service(self, auth_manager, user_repo) -> UserService:
        return UserService(
            user_repo=user_repo,
            password_manager=auth_manager._password_manager,
        )

    async def test_register_empty_password(self, user_service):
        with pytest.raises(ValidationError, match="Password is required"):
            await user_service.register(email="empty.pass@test.com", password="")

    async def test_change_password_wrong_old_password(self, test_user, user_service):
        with pytest.raises(InvalidCredentialsError):
            await user_service.change_password(
                user_id=test_user.id,
                old_password="WrongPass123!",
                new_password="NewPass123!",
            )

    async def test_change_password_success(self, test_user, user_service):
        await user_service.change_password(
            user_id=test_user.id,
            old_password="ServiceTest123!",
            new_password="NewPass456!",
        )
