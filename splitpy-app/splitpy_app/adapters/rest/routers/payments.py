"""Payment endpoints (RF-12)."""

from uuid import UUID

from fastapi import APIRouter

from splitpy_app.adapters.rest.dependencies import AppServices, CurrentUser
from splitpy_app.adapters.rest.schemas.expenses import PaymentResponse, RecordPaymentRequest
from splitpy_app.application.use_cases.expenses import ListPayments, RecordPayment
from splitpy_core.domain.ids import GroupId

router = APIRouter(prefix="/groups/{group_id}/payments", tags=["payments"])


@router.post("", status_code=201)
def record_payment(
    group_id: UUID, request: RecordPaymentRequest, by: CurrentUser, services: AppServices
) -> PaymentResponse:
    payment = RecordPayment(services.units(), services.clock, services.ids).execute(
        group_id=GroupId(group_id), by=by, **request.command()
    )
    return PaymentResponse.from_domain(payment)


@router.get("")
def list_payments(group_id: UUID, by: CurrentUser, services: AppServices) -> list[PaymentResponse]:
    payments = ListPayments(services.units()).execute(group_id=GroupId(group_id))
    return [PaymentResponse.from_domain(payment) for payment in payments]
