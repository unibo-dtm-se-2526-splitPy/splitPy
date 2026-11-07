"""A member leaves the group by getting a left_at, never by being deleted."""

from support import ALICE, T0, T1

from splitpy_core.domain.member import Member, Role


class TestRole:
    def test_has_admin_and_member(self):
        assert {role.name for role in Role} == {"ADMIN", "MEMBER"}


class TestMember:
    def test_member_without_left_at_is_active(self):
        assert Member(ALICE, Role.MEMBER, joined_at=T0).is_active()

    def test_member_with_left_at_is_not_active(self):
        assert not Member(ALICE, Role.MEMBER, joined_at=T0, left_at=T1).is_active()

    def test_left_at_defaults_to_none(self):
        assert Member(ALICE, Role.ADMIN, joined_at=T0).left_at is None
