"""Schemas of the group endpoints (RF-04, RF-05, RF-16)."""

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from splitpy_app.adapters.rest.schemas.base import Schema
from splitpy_core.domain.group import Group, GroupStatus
from splitpy_core.domain.ids import UserId
from splitpy_core.domain.member import Member, Role
from splitpy_core.domain.money import Currency
from splitpy_core.ports.group_repository import GroupSummary


class CreateGroupRequest(Schema):
    name: str
    currency: str

    def command(self) -> dict[str, object]:
        return {"name": self.name, "currency": Currency(self.currency)}


class AddMemberRequest(Schema):
    user_id: UUID
    role: Role = Role.MEMBER

    def command(self) -> dict[str, object]:
        return {"user_id": UserId(self.user_id), "role": self.role}


class UpdateGroupRequest(Schema):
    """The group has no rename command, and archiving cannot be undone: ARCHIVED is all it takes."""

    status: Literal[GroupStatus.ARCHIVED]


class MemberResponse(Schema):
    user_id: UUID
    role: Role
    joined_at: datetime
    left_at: datetime | None

    @classmethod
    def from_domain(cls, member: Member) -> Self:
        return cls(
            user_id=member.user_id.value,
            role=member.role,
            joined_at=member.joined_at,
            left_at=member.left_at,
        )


class GroupSummaryResponse(Schema):
    id: UUID
    name: str
    currency: str
    status: GroupStatus

    @classmethod
    def from_domain(cls, summary: GroupSummary) -> Self:
        return cls(
            id=summary.id.value,
            name=summary.name,
            currency=summary.currency.code,
            status=summary.status,
        )


class GroupResponse(Schema):
    """Former members stay listed with their left_at: past expenses still name them."""

    id: UUID
    name: str
    currency: str
    status: GroupStatus
    members: list[MemberResponse]

    @classmethod
    def from_domain(cls, group: Group) -> Self:
        return cls(
            id=group.id.value,
            name=group.name,
            currency=group.currency.code,
            status=group.status,
            members=[MemberResponse.from_domain(member) for member in group.members()],
        )
