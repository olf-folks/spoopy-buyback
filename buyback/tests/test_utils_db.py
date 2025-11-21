import pytest
from buyback.models import EveItemTax
from buyback.views import (
    get_tax_rate_from_database,
    get_flat_rate_from_database,
    get_haul_fee_bool_from_database,
    getqtys,
    generate_api_input
)

@pytest.mark.django_db
class TestUtilsDB:
    def test_get_tax_rate_from_database(self):
        EveItemTax.objects.create(type_id=1, jita_buy_percentage=15.5, flat_cost=0)
        assert get_tax_rate_from_database(1) == 15.5
        assert get_tax_rate_from_database(999) == 0.0

    def test_get_flat_rate_from_database(self):
        EveItemTax.objects.create(type_id=1, flat_cost=1000)
        EveItemTax.objects.create(type_id=2, flat_cost=0)
        # Testing string/invalid conversion if model allows it, but model uses DecimalField/FloatField typically.
        # The view code does try-except ValueError for float conversion, implying flat_cost might be string or problematic?
        # In models.py it is probably DecimalField or IntegerField.
        
        assert get_flat_rate_from_database(1) == 1000.0
        assert get_flat_rate_from_database(2) == 0.0
        assert get_flat_rate_from_database(999) == 0.0

    def test_get_haul_fee_bool_from_database(self):
        EveItemTax.objects.create(type_id=1, hauling_fee=True, flat_cost=0)
        EveItemTax.objects.create(type_id=2, hauling_fee=False, flat_cost=0)
        
        assert get_haul_fee_bool_from_database(1) is True
        assert get_haul_fee_bool_from_database(2) is False
        assert get_haul_fee_bool_from_database(999) is False

class TestUtilsLogic:
    def test_getqtys(self):
        parsed = [{'name': 'A', 'quantity': 10}, {'name': 'B', 'quantity': 5}]
        assert getqtys(parsed) == [10, 5]
        assert getqtys([]) == []

    def test_generate_api_input(self):
        parsed = [{'name': 'A', 'quantity': 10}, {'name': 'B', 'quantity': 5}]
        expected = "A 10\nB 5\n"
        assert generate_api_input(parsed) == expected
        assert generate_api_input([]) == ""

