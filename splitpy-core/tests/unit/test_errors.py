import re

import pytest

from splitpy_core.domain import errors
from splitpy_core.domain.errors import (
    AlreadyAMember,
    CurrencyMismatch,
    DomainError,
    EmptyParticipantSet,
    EntityNotFound,
    ExpenseNotFound,
    GroupArchived,
    GroupNotFound,
    InvalidDateRange,
    InvalidPayment,
    MemberHasNonZeroBalance,
    MembershipError,
    NonPositiveAmount,
    NotAMember,
    NotAnAdministrator,
    PaymentNotFound,
    PercentagesDoNotSumTo100,
    SplitDoesNotMatchAmount,
    SplitError,
)

HIERARCHY = {
    CurrencyMismatch: DomainError,
    NonPositiveAmount: DomainError,
    SplitError: DomainError,
    SplitDoesNotMatchAmount: SplitError,
    PercentagesDoNotSumTo100: SplitError,
    EmptyParticipantSet: SplitError,
    MembershipError: DomainError,
    NotAMember: MembershipError,
    AlreadyAMember: MembershipError,
    MemberHasNonZeroBalance: MembershipError,
    NotAnAdministrator: MembershipError,
    GroupArchived: DomainError,
    InvalidPayment: DomainError,
    InvalidDateRange: DomainError,
    EntityNotFound: DomainError,
    GroupNotFound: EntityNotFound,
    ExpenseNotFound: EntityNotFound,
    PaymentNotFound: EntityNotFound,
}

ALL_ERRORS = [DomainError, *HIERARCHY]


def _defined_error_classes():
    return {
        obj
        for obj in vars(errors).values()
        if isinstance(obj, type) and issubclass(obj, DomainError)
    }


@pytest.mark.parametrize(("error", "parent"), HIERARCHY.items())
def test_error_has_expected_direct_parent(error, parent):
    assert error.__bases__ == (parent,)


def test_domain_error_is_an_exception():
    assert issubclass(DomainError, Exception)


def test_module_defines_exactly_the_designed_hierarchy():
    assert _defined_error_classes() == set(ALL_ERRORS)


@pytest.mark.parametrize("error", ALL_ERRORS)
def test_error_code_is_upper_snake_case(error):
    assert re.fullmatch(r"[A-Z][A-Z0-9]*(_[A-Z0-9]+)*", error.code)


def test_error_codes_are_unique():
    codes = [error.code for error in ALL_ERRORS]
    assert len(codes) == len(set(codes))


def test_error_code_is_stable():
    assert SplitDoesNotMatchAmount.code == "SPLIT_DOES_NOT_MATCH_AMOUNT"
    assert PercentagesDoNotSumTo100.code == "PERCENTAGES_DO_NOT_SUM_TO_100"
    assert GroupNotFound.code == "GROUP_NOT_FOUND"


def test_error_instance_exposes_code_and_message():
    error = CurrencyMismatch("EUR and USD cannot be added")
    assert error.code == "CURRENCY_MISMATCH"
    assert str(error) == "EUR and USD cannot be added"


def test_specific_error_is_caught_by_its_family():
    with pytest.raises(SplitError):
        raise PercentagesDoNotSumTo100("sum is 9999 basis points")
