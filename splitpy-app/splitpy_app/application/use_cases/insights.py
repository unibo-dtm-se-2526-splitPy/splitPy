"""Read-only use cases: nothing is stored, plans and reports are computed on every request."""

from splitpy_app.application.ports import RecordedEvent, UnitOfWork
from splitpy_core.domain.balances import Balances
from splitpy_core.domain.date_range import DateRange
from splitpy_core.domain.ids import GroupId
from splitpy_core.domain.report import ReportService, SpendingReport
from splitpy_core.domain.settlement import SettlementPlan, SettlementService


class ComputeBalances:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def execute(self, *, group_id: GroupId) -> Balances:
        with self._uow:
            group = self._uow.groups.get(group_id)
        return group.balances()


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
        with self._uow:
            group = self._uow.groups.get(group_id)
        return ReportService.spending(group, period)


class ListActivity:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def execute(self, *, group_id: GroupId) -> list[RecordedEvent]:
        """Newest first (RF-15). The group is loaded first, so an unknown one is not an empty feed."""
        with self._uow:
            self._uow.groups.get(group_id)
            return self._uow.events.list_for_group(group_id)
