"""Domain errors: the designed hierarchy, each class with a stable code."""

import re

import pytest

from splitpy_core.domain import errors
from splitpy_core.domain.errors import (
    AdminSuccessorRequired,
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
    NegativeShare,
    NonPositiveAmount,
    NotAMember,
    NotAnAdministrator,
    PaymentNotFound,
    PercentagesDoNotSumTo100,
    SplitDoesNotMatchAmount,
    SplitError,
    SubCentAmount,
    UnsupportedCurrency,
)

HIERARCHY = {
    CurrencyMismatch: DomainError,
    NonPositiveAmount: DomainError,
    SubCentAmount: DomainError,
    UnsupportedCurrency: DomainError,
    SplitError: DomainError,
    SplitDoesNotMatchAmount: SplitError,
    PercentagesDoNotSumTo100: SplitError,
    EmptyParticipantSet: SplitError,
    NegativeShare: SplitError,
    MembershipError: DomainError,
    NotAMember: MembershipError,
    AlreadyAMember: MembershipError,
    MemberHasNonZeroBalance: MembershipError,
    NotAnAdministrator: MembershipError,
    AdminSuccessorRequired: MembershipError,
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


class TestHierarchy:
    @pytest.mark.parametrize(("error", "parent"), HIERARCHY.items())
    def test_error_has_expected_direct_parent(self, error, parent):
        assert error.__bases__ == (parent,)

    def test_domain_error_is_an_exception(self):
        assert issubclass(DomainError, Exception)

    def test_module_defines_exactly_the_designed_hierarchy(self):
        assert _defined_error_classes() == set(ALL_ERRORS)

    def test_specific_error_is_caught_by_its_family(self):
        with pytest.raises(SplitError):
            raise PercentagesDoNotSumTo100("basis points sum to 9999, not 10000")


class TestCodes:
    @pytest.mark.parametrize("error", ALL_ERRORS)
    def test_error_code_is_upper_snake_case(self, error):
        assert re.fullmatch(r"[A-Z][A-Z0-9]*(_[A-Z0-9]+)*", error.code)

    def test_error_codes_are_unique(self):
        codes = [error.code for error in ALL_ERRORS]
        assert len(codes) == len(set(codes))

    def test_error_code_is_stable(self):
        assert SplitDoesNotMatchAmount.code == "SPLIT_DOES_NOT_MATCH_AMOUNT"
        assert PercentagesDoNotSumTo100.code == "PERCENTAGES_DO_NOT_SUM_TO_100"
        assert NegativeShare.code == "NEGATIVE_SHARE"
        assert GroupNotFound.code == "GROUP_NOT_FOUND"
        assert SubCentAmount.code == "SUB_CENT_AMOUNT"
        assert UnsupportedCurrency.code == "UNSUPPORTED_CURRENCY"

    def test_error_instance_exposes_code_and_message(self):
        error = CurrencyMismatch("cannot combine EUR with USD")
        assert error.code == "CURRENCY_MISMATCH"
        assert str(error) == "cannot combine EUR with USD"
