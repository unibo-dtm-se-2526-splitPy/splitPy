"""Domain errors. Each class carries a stable code that adapters map without parsing messages."""

from typing import ClassVar


class DomainError(Exception):
    code: ClassVar[str] = "DOMAIN_ERROR"


class CurrencyMismatch(DomainError):
    code = "CURRENCY_MISMATCH"


class NonPositiveAmount(DomainError):
    code = "NON_POSITIVE_AMOUNT"


class SplitError(DomainError):
    code = "SPLIT_ERROR"


class SplitDoesNotMatchAmount(SplitError):
    code = "SPLIT_DOES_NOT_MATCH_AMOUNT"


class PercentagesDoNotSumTo100(SplitError):
    code = "PERCENTAGES_DO_NOT_SUM_TO_100"


class EmptyParticipantSet(SplitError):
    code = "EMPTY_PARTICIPANT_SET"


class NegativeShare(SplitError):
    code = "NEGATIVE_SHARE"


class MembershipError(DomainError):
    code = "MEMBERSHIP_ERROR"


class NotAMember(MembershipError):
    code = "NOT_A_MEMBER"


class AlreadyAMember(MembershipError):
    code = "ALREADY_A_MEMBER"


class MemberHasNonZeroBalance(MembershipError):
    code = "MEMBER_HAS_NON_ZERO_BALANCE"


class NotAnAdministrator(MembershipError):
    code = "NOT_AN_ADMINISTRATOR"


class AdminSuccessorRequired(MembershipError):
    code = "ADMIN_SUCCESSOR_REQUIRED"


class GroupArchived(DomainError):
    code = "GROUP_ARCHIVED"


class InvalidPayment(DomainError):
    code = "INVALID_PAYMENT"


class InvalidDateRange(DomainError):
    code = "INVALID_DATE_RANGE"


class EntityNotFound(DomainError):
    code = "ENTITY_NOT_FOUND"


class GroupNotFound(EntityNotFound):
    code = "GROUP_NOT_FOUND"


class ExpenseNotFound(EntityNotFound):
    code = "EXPENSE_NOT_FOUND"


class PaymentNotFound(EntityNotFound):
    code = "PAYMENT_NOT_FOUND"
