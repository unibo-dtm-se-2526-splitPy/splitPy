import pytest

from splitpy_app.adapters.rest.problems import PROBLEM_CONTENT_TYPE, problem_for
from splitpy_core.domain import errors
from splitpy_core.domain.errors import (
    AlreadyAMember,
    DomainError,
    ExpenseNotFound,
    GroupArchived,
    GroupNotFound,
    MemberHasNonZeroBalance,
    NotAMember,
    NotAnAdministrator,
    PaymentNotFound,
    PercentagesDoNotSumTo100,
    SplitDoesNotMatchAmount,
)

INSTANCE = "/api/v1/groups/3f1b/expenses"


def all_domain_errors():
    return [
        obj
        for obj in vars(errors).values()
        if isinstance(obj, type) and issubclass(obj, DomainError)
    ]


class TestStatus:
    def test_non_administrator_is_forbidden(self):
        assert problem_for(NotAnAdministrator("no"), INSTANCE).status == 403

    @pytest.mark.parametrize("error", [GroupNotFound, ExpenseNotFound, PaymentNotFound])
    def test_missing_entity_is_not_found(self, error):
        assert problem_for(error("missing"), INSTANCE).status == 404

    @pytest.mark.parametrize("error", [GroupArchived, AlreadyAMember])
    def test_state_conflict_is_409(self, error):
        assert problem_for(error("conflict"), INSTANCE).status == 409

    def test_i03_non_member_payer_or_participant_is_unprocessable(self):
        # The 403 for a caller outside the group comes from the membership guard, not from here.
        assert problem_for(NotAMember("not a member"), INSTANCE).status == 422

    @pytest.mark.parametrize(
        "error", [SplitDoesNotMatchAmount, PercentagesDoNotSumTo100, MemberHasNonZeroBalance]
    )
    def test_invariant_violation_is_unprocessable(self, error):
        assert problem_for(error("invalid"), INSTANCE).status == 422

    @pytest.mark.parametrize("error", all_domain_errors())
    def test_every_domain_error_maps_to_a_client_error(self, error):
        assert 400 <= problem_for(error("x"), INSTANCE).status < 500


class TestProblemBody:
    def test_domain_error_becomes_a_problem_with_its_stable_code(self):
        problem = problem_for(SplitDoesNotMatchAmount("shares sum to 4490, not 4500"), INSTANCE)
        assert problem.to_dict() == {
            "type": "https://splitpy.example/errors/split-does-not-match-amount",
            "title": "Split does not match amount",
            "status": 422,
            "code": "SPLIT_DOES_NOT_MATCH_AMOUNT",
            "detail": "shares sum to 4490, not 4500",
            "instance": INSTANCE,
        }

    def test_title_keeps_numbers_readable(self):
        problem = problem_for(PercentagesDoNotSumTo100("9999"), INSTANCE)
        assert problem.title == "Percentages do not sum to 100"

    def test_unexpected_error_is_500_without_internal_details(self):
        problem = problem_for(KeyError("secret internal state"), INSTANCE)
        assert (problem.status, problem.code) == (500, "INTERNAL_ERROR")
        assert "secret" not in str(problem.to_dict())

    def test_content_type_is_problem_json(self):
        assert PROBLEM_CONTENT_TYPE == "application/problem+json"
