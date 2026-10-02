from datetime import UTC, datetime
from uuid import UUID

from splitpy_core.domain.ids import UserId
from splitpy_core.domain.member import Member, Role

ALICE = UserId(UUID(int=1))
JOINED = datetime(2026, 1, 1, tzinfo=UTC)
LEFT = datetime(2026, 2, 1, tzinfo=UTC)


class TestRole:
    def test_has_admin_and_member(self):
        assert {role.name for role in Role} == {"ADMIN", "MEMBER"}


class TestMember:
    def test_member_without_left_at_is_active(self):
        assert Member(ALICE, Role.MEMBER, joined_at=JOINED).is_active()

    def test_member_with_left_at_is_not_active(self):
        assert not Member(ALICE, Role.MEMBER, joined_at=JOINED, left_at=LEFT).is_active()

    def test_left_at_defaults_to_none(self):
        assert Member(ALICE, Role.ADMIN, joined_at=JOINED).left_at is None
