"""Hypothesis strategies shared by the property tests."""

from uuid import UUID

from hypothesis import strategies as st

from splitpy_core.domain.ids import UserId

user_ids = st.integers(min_value=0, max_value=1_000).map(lambda n: UserId(UUID(int=n)))
members = st.sets(user_ids, min_size=2, max_size=8).map(sorted)
cents = st.integers(min_value=1, max_value=10**7)
