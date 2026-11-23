"""Group endpoints (RF-04, RF-05, RF-16)."""

from uuid import UUID

from fastapi import APIRouter

from splitpy_app.adapters.rest.dependencies import AppServices, CurrentUser
from splitpy_app.adapters.rest.schemas.groups import (
    AddMemberRequest,
    CreateGroupRequest,
    GroupResponse,
    GroupSummaryResponse,
    UpdateGroupRequest,
)
from splitpy_app.application.use_cases.groups import (
    AddMember,
    ArchiveGroup,
    CreateGroup,
    GetGroup,
    ListMyGroups,
    RemoveMember,
)
from splitpy_core.domain.ids import GroupId, UserId

router = APIRouter(prefix="/groups", tags=["groups"])


@router.post("", status_code=201)
def create_group(
    request: CreateGroupRequest, by: CurrentUser, services: AppServices
) -> GroupResponse:
    group = CreateGroup(services.units(), services.clock, services.ids).execute(
        founder=by, **request.command()
    )
    return GroupResponse.from_domain(group)


@router.get("")
def list_groups(by: CurrentUser, services: AppServices) -> list[GroupSummaryResponse]:
    summaries = ListMyGroups(services.units()).execute(user_id=by)
    return [GroupSummaryResponse.from_domain(summary) for summary in summaries]


@router.get("/{group_id}")
def get_group(group_id: UUID, by: CurrentUser, services: AppServices) -> GroupResponse:
    group = GetGroup(services.units()).execute(group_id=GroupId(group_id))
    return GroupResponse.from_domain(group)


@router.patch("/{group_id}")
def update_group(
    group_id: UUID, request: UpdateGroupRequest, by: CurrentUser, services: AppServices
) -> GroupResponse:
    group = ArchiveGroup(services.units(), services.clock).execute(
        group_id=GroupId(group_id), by=by
    )
    return GroupResponse.from_domain(group)


@router.post("/{group_id}/members", status_code=201)
def add_member(
    group_id: UUID, request: AddMemberRequest, by: CurrentUser, services: AppServices
) -> GroupResponse:
    group = AddMember(services.units(), services.clock).execute(
        group_id=GroupId(group_id), by=by, **request.command()
    )
    return GroupResponse.from_domain(group)


@router.delete("/{group_id}/members/{user_id}", status_code=204)
def remove_member(
    group_id: UUID,
    user_id: UUID,
    by: CurrentUser,
    services: AppServices,
    successor: UUID | None = None,
) -> None:
    RemoveMember(services.units(), services.clock).execute(
        group_id=GroupId(group_id),
        user_id=UserId(user_id),
        by=by,
        successor=UserId(successor) if successor else None,
    )
