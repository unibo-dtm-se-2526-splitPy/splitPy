from dataclasses import FrozenInstanceError
from uuid import UUID

import pytest

from splitpy_core.domain.ids import ExpenseId, GroupId, PaymentId, UserId

RAW = UUID("12345678-1234-5678-1234-567812345678")
ID_TYPES = [UserId, GroupId, ExpenseId, PaymentId]


@pytest.mark.parametrize("id_type", ID_TYPES)
def test_id_wraps_uuid(id_type):
    assert id_type(RAW).value == RAW


@pytest.mark.parametrize("id_type", ID_TYPES)
def test_ids_with_same_uuid_are_equal_and_hash_equal(id_type):
    assert id_type(RAW) == id_type(RAW)
    assert hash(id_type(RAW)) == hash(id_type(RAW))


@pytest.mark.parametrize("id_type", ID_TYPES)
def test_id_is_immutable(id_type):
    identifier = id_type(RAW)
    with pytest.raises(FrozenInstanceError):
        identifier.value = UUID(int=0)


def test_ids_of_different_kinds_are_never_equal():
    assert UserId(RAW) != GroupId(RAW)
    assert ExpenseId(RAW) != PaymentId(RAW)
    assert len({UserId(RAW), GroupId(RAW), ExpenseId(RAW), PaymentId(RAW)}) == 4


def test_user_ids_are_ordered_by_uuid():
    low, high = UserId(UUID(int=1)), UserId(UUID(int=2))
    assert sorted([high, low]) == [low, high]


def test_ids_of_different_kinds_cannot_be_compared_for_order():
    with pytest.raises(TypeError):
        _ = UserId(RAW) < GroupId(RAW)
