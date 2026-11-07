"""Read-only use cases: nothing is stored, plans and reports are computed on every request."""

from splitpy_app.application.ports import UnitOfWork
from splitpy_core.domain.date_range import DateRange
from splitpy_core.domain.ids import GroupId
from splitpy_core.domain.report import ReportService, SpendingReport
from splitpy_core.domain.settlement import SettlementPlan, SettlementService


class ComputeSettlement:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def execute(self, *, group_id: GroupId) -> SettlementPlan:
        with self._uow:
            group = self._uow.groups.get(group_id)
        return SettlementService.plan(group.balances())


class GenerateReport:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def execute(self, *, group_id: GroupId, period: DateRange) -> SpendingReport:
        # Only the expenses of the period are loaded (RF-13).
        with self._uow:
            group = self._uow.groups.get_for_period(group_id, period)
        return ReportService.spending(group, period)
