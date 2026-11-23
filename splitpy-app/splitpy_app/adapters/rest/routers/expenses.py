"""Expense endpoints (RF-06, RF-08, RF-09, RF-14)."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from splitpy_app.adapters.rest.dependencies import AppServices, CurrentUser
from splitpy_app.adapters.rest.schemas.expenses import (
    ExpensePageResponse,
    ExpenseResponse,
    RegisterExpenseRequest,
    UpdateExpenseRequest,
)
from splitpy_app.application.use_cases.expenses import (
    GetExpense,
    ListExpenses,
    RegisterExpense,
    RemoveExpense,
    UpdateExpense,
)
from splitpy_app.application.use_cases.groups import GetGroup
from splitpy_core.domain.category import Category
from splitpy_core.domain.ids import ExpenseId, GroupId, UserId

router = APIRouter(prefix="/groups/{group_id}/expenses", tags=["expenses"])


@router.post("", status_code=201)
def register_expense(
    group_id: UUID, request: RegisterExpenseRequest, by: CurrentUser, services: AppServices
) -> ExpenseResponse:
    expense = RegisterExpense(services.units(), services.clock, services.ids).execute(
        group_id=GroupId(group_id), by=by, **request.command()
    )
    return ExpenseResponse.from_domain(expense)


@router.get("")
def list_expenses(
    group_id: UUID,
    by: CurrentUser,
    services: AppServices,
    start: Annotated[date | None, Query(alias="from")] = None,
    end: Annotated[date | None, Query(alias="to")] = None,
    category: Category | None = None,
    paid_by: UUID | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ExpensePageResponse:
    listed = ListExpenses(services.units()).execute(
        group_id=GroupId(group_id),
        start=start,
        end=end,
        category=category,
        paid_by=UserId(paid_by) if paid_by else None,
    )
    first = (page - 1) * size
    return ExpensePageResponse(
        items=[ExpenseResponse.from_domain(expense) for expense in listed[first : first + size]],
        page=page,
        size=size,
    )


@router.get("/{expense_id}")
def get_expense(
    group_id: UUID, expense_id: UUID, by: CurrentUser, services: AppServices
) -> ExpenseResponse:
    expense = GetExpense(services.units()).execute(
        group_id=GroupId(group_id), expense_id=ExpenseId(expense_id)
    )
    return ExpenseResponse.from_domain(expense)


@router.patch("/{expense_id}")
def update_expense(
    group_id: UUID,
    expense_id: UUID,
    request: UpdateExpenseRequest,
    by: CurrentUser,
    services: AppServices,
) -> ExpenseResponse:
    # An exact split is read in the group currency.
    group = GetGroup(services.units()).execute(group_id=GroupId(group_id))
    expense = UpdateExpense(services.units(), services.clock).execute(
        group_id=group.id,
        expense_id=ExpenseId(expense_id),
        by=by,
        **request.changes(group.currency),
    )
    return ExpenseResponse.from_domain(expense)


@router.delete("/{expense_id}", status_code=204)
def remove_expense(
    group_id: UUID, expense_id: UUID, by: CurrentUser, services: AppServices
) -> None:
    RemoveExpense(services.units(), services.clock).execute(
        group_id=GroupId(group_id), expense_id=ExpenseId(expense_id), by=by
    )
