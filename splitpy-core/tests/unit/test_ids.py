"""Typed identifiers: an id of one kind is never equal or comparable to an id of another."""

from dataclasses import FrozenInstanceError
from uuid import UUID

import pytest

from splitpy_core.domain.ids import ExpenseId, GroupId, PaymentId, UserId

RAW = UUID("12345678-1234-5678-1234-567812345678")
ID_TYPES = [UserId, GroupId, ExpenseId, PaymentId]


@pytest.mark.parametrize("id_type", ID_TYPES)
class TestEveryIdType:
    def test_id_wraps_uuid(self, id_type):
        assert id_type(RAW).value == RAW

    def test_ids_with_same_uuid_are_equal_and_hash_equal(self, id_type):
        assert id_type(RAW) == id_type(RAW)
        assert hash(id_type(RAW)) == hash(id_type(RAW))

    def test_id_is_immutable(self, id_type):
        identifier = id_type(RAW)
        with pytest.raises(FrozenInstanceError):
            identifier.value = UUID(int=0)

    def test_id_prints_as_its_uuid(self, id_type):
        assert str(id_type(RAW)) == "12345678-1234-5678-1234-567812345678"


class TestIdKinds:
    def test_ids_of_different_kinds_are_never_equal(self):
        assert UserId(RAW) != GroupId(RAW)
        assert ExpenseId(RAW) != PaymentId(RAW)
        assert len({UserId(RAW), GroupId(RAW), ExpenseId(RAW), PaymentId(RAW)}) == 4

    def test_user_ids_are_ordered_by_uuid(self):
        low, high = UserId(UUID(int=1)), UserId(UUID(int=2))
        assert sorted([high, low]) == [low, high]

    def test_ids_of_different_kinds_cannot_be_compared_for_order(self):
        with pytest.raises(TypeError):
            _ = UserId(RAW) < GroupId(RAW)
