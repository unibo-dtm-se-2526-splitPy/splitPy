"""Balances, settlement plan, report and activity feed (RF-10, RF-11, RF-13, RF-15)."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from splitpy_app.adapters.rest.dependencies import AppServices, CurrentUser
from splitpy_app.adapters.rest.schemas.insights import (
    ActivityEntryResponse,
    ActivityPageResponse,
    BalancesResponse,
    ReportResponse,
    SettlementResponse,
)
from splitpy_app.application.use_cases.insights import (
    ComputeBalances,
    ComputeSettlement,
    GenerateReport,
    ListActivity,
)
from splitpy_core.domain.date_range import DateRange
from splitpy_core.domain.ids import GroupId

router = APIRouter(prefix="/groups/{group_id}", tags=["insights"])


@router.get("/balances")
def balances(group_id: UUID, by: CurrentUser, services: AppServices) -> BalancesResponse:
    computed = ComputeBalances(services.units()).execute(group_id=GroupId(group_id))
    return BalancesResponse.from_domain(computed)


@router.get("/settlement")
def settlement(group_id: UUID, by: CurrentUser, services: AppServices) -> SettlementResponse:
    plan = ComputeSettlement(services.units()).execute(group_id=GroupId(group_id))
    return SettlementResponse.from_domain(plan)


@router.get("/report")
def report(
    group_id: UUID,
    start: Annotated[date, Query(alias="from")],
    end: Annotated[date, Query(alias="to")],
    by: CurrentUser,
    services: AppServices,
) -> ReportResponse:
    generated = GenerateReport(services.units()).execute(
        group_id=GroupId(group_id), period=DateRange(start, end)
    )
    return ReportResponse.from_domain(generated)


@router.get("/activity")
def activity(
    group_id: UUID,
    by: CurrentUser,
    services: AppServices,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ActivityPageResponse:
    recorded = ListActivity(services.units()).execute(group_id=GroupId(group_id))
    first = (page - 1) * size
    return ActivityPageResponse(
        items=[
            ActivityEntryResponse.from_domain(entry) for entry in recorded[first : first + size]
        ],
        page=page,
        size=size,
    )
