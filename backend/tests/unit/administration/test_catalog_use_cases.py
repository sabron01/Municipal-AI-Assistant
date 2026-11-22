from uuid import uuid4

import pytest

from municipal_assistant.administration.application.use_cases import (
    CatalogUseCases,
    normalize_catalog_name,
)
from municipal_assistant.administration.domain.entities import Category
from municipal_assistant.administration.domain.errors import InvalidCatalogEntry


def test_catalog_names_are_trimmed_unicode_normalized_and_casefolded():
    display, normalized = normalize_catalog_name("  Cafe\u0301  ")

    assert display == "Café"
    assert normalized == "café"


@pytest.mark.parametrize("value", ["", " \t ", "x" * 201, "service\u0000name"])
def test_invalid_catalog_names_are_rejected(value):
    with pytest.raises(InvalidCatalogEntry):
        normalize_catalog_name(value)


def test_subcategories_cannot_become_parents():
    parent_id, child_id = uuid4(), uuid4()

    class Repository:
        def get_category(self, category_id):
            if category_id == parent_id:
                return Category(parent_id, None, None, "Root", None)
            if category_id == child_id:
                return Category(child_id, parent_id, "Root", "Child", None)
            return None

    use_cases = CatalogUseCases(Repository())

    with pytest.raises(InvalidCatalogEntry, match="Only top-level"):
        use_cases.create_category(parent_id=child_id, name="Nested", actor_id=uuid4())
