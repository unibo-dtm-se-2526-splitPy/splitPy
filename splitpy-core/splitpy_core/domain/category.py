"""Expense categories. Values are stable strings, safe to persist and expose over the API."""

from enum import StrEnum


class Category(StrEnum):
    FOOD = "FOOD"
    HOUSING = "HOUSING"
    TRANSPORT = "TRANSPORT"
    LEISURE = "LEISURE"
    UTILITIES = "UTILITIES"
    OTHER = "OTHER"
