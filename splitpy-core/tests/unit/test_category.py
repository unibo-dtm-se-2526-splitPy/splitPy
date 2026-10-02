from splitpy_core.domain.category import Category


class TestCategory:
    def test_has_the_six_categories_of_the_domain_model(self):
        assert {category.name for category in Category} == {
            "FOOD",
            "HOUSING",
            "TRANSPORT",
            "LEISURE",
            "UTILITIES",
            "OTHER",
        }

    def test_is_built_from_its_stable_value(self):
        assert Category("FOOD") is Category.FOOD
