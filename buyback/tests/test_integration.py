import pytest
from unittest.mock import patch, Mock
from django.contrib.auth.models import User
from buyback.models import EveItemTax


@pytest.fixture
def mock_janice_api_response():
    """Fixture providing a mock response from the Janice API."""
    return [
        {
            'itemType': {
                'eid': 34,
                'name': 'Tritanium',
                'volume': 0.01,
                'category': {'id': 25, 'name': 'Material'},
                'group': {'id': 18, 'name': 'Mineral'}
            },
            'immediatePrices': {
                'buyPrice5DayMedian': 1000.0
            }
        },
        {
            'itemType': {
                'eid': 35,
                'name': 'Pyerite',
                'volume': 0.01,
                'category': {'id': 25, 'name': 'Material'},
                'group': {'id': 18, 'name': 'Mineral'}
            },
            'immediatePrices': {
                'buyPrice5DayMedian': 500.0
            }
        }
    ]


@pytest.fixture
def mock_janice_api(mock_janice_api_response):
    """Fixture that mocks the Janice API requests.post call."""
    with patch('buyback.views.requests.post') as mock_post:
        mock_response = Mock()
        mock_response.json.return_value = mock_janice_api_response
        mock_post.return_value = mock_response
        yield mock_post


class TestBuybackCalculationFlow:
    """Integration tests for the main buyback calculation flow."""

    def test_buyback_calculation_flow(self, client, db, mock_janice_api, mock_janice_api_response):
        """Test the complete buyback calculation flow from POST to response."""
        # Create an EveItemTax entry for Tritanium
        EveItemTax.objects.create(
            type_id=34,
            type_name='Tritanium',
            jita_buy_percentage=50.0,  # 50%
            flat_cost=0,
            hauling_fee=False,
            category_id=25,
            category_name='Material',
            group_id=18,
            group='Mineral'
        )

        # POST item data to index view
        response = client.post('/buyback/', {'item_name': 'Tritanium\t100'})

        # Verify response is successful
        assert response.status_code == 200

        # Verify API was called
        assert mock_janice_api.called
        call_args = mock_janice_api.call_args
        assert 'https://janice.e-351.com/api/rest/v2/pricer?market=2' in str(call_args[0])

        # Verify context contains processed items
        assert 'processed_items' in response.context
        processed_items = response.context['processed_items']
        assert len(processed_items) == 1

        # Verify calculation logic
        item = processed_items[0]
        assert item['item_name'] == 'Tritanium'
        assert item['quantity'] == 100
        assert item['market_price'] == 1000.0
        # Note: The code multiplies tax_rate by 100, then calculate_buyback_price divides by 100
        # So: buyback_price = market_price * tax_rate = 1000 * 50.0 = 50000.0
        assert item['buyback_price'] == 50000.0
        assert item['buyback_price_itemtotal'] == 5000000.0  # 50000 * 100
        assert item['market_price_itemtotal'] == 100000.0  # 1000 * 100

        # Verify totals
        assert 'totals_info' in response.context
        totals = response.context['totals_info']
        assert totals[0] == 5000000.0  # gtotal_buyback (50000 * 100)
        assert totals[1] == 100000.0  # gtotal_market
        assert totals[2] == 5000.0  # geff_rate (5000000 / 100000 * 100 = 5000%)

    def test_buyback_with_new_item_creates_eve_item_tax(self, client, db, mock_janice_api):
        """Test that new items from API create EveItemTax records."""
        # No EveItemTax exists initially
        assert EveItemTax.objects.filter(type_id=34).count() == 0

        # POST item that doesn't exist in DB
        response = client.post('/buyback/', {'item_name': 'Tritanium\t100'})

        # Verify EveItemTax was created
        eve_item = EveItemTax.objects.get(type_id=34)
        assert eve_item.type_name == 'Tritanium'
        assert eve_item.jita_buy_percentage == 0.0  # Default value
        assert eve_item.needs_review is True  # Should be marked for review

    def test_buyback_multiple_items(self, client, db, mock_janice_api):
        """Test buyback calculation with multiple items."""
        # Create EveItemTax entries
        EveItemTax.objects.create(
            type_id=34,
            type_name='Tritanium',
            jita_buy_percentage=50.0,
            flat_cost=0,
            hauling_fee=False,
            category_id=25,
            category_name='Material',
            group_id=18,
            group='Mineral'
        )
        EveItemTax.objects.create(
            type_id=35,
            type_name='Pyerite',
            jita_buy_percentage=60.0,
            flat_cost=0,
            hauling_fee=False,
            category_id=25,
            category_name='Material',
            group_id=18,
            group='Mineral'
        )

        # POST multiple items
        response = client.post('/buyback/', {'item_name': 'Tritanium\t100\nPyerite\t200'})

        assert response.status_code == 200
        processed_items = response.context['processed_items']
        assert len(processed_items) == 2

        # Verify totals are correct
        totals = response.context['totals_info']
        # Tritanium: 1000 * 50.0 * 100 = 5000000
        # Pyerite: 500 * 60.0 * 200 = 6000000
        # Total buyback: 11000000
        # Total market: (1000 * 100) + (500 * 200) = 200000
        assert totals[0] == 11000000.0  # gtotal_buyback
        assert totals[1] == 200000.0  # gtotal_market


class TestHaulingFeeLogic:
    """Integration tests for hauling fee calculation."""

    def test_hauling_fee_logic(self, client, db, mock_janice_api):
        """Test that hauling fees are correctly added to buyback price."""
        # Create item with hauling fee enabled
        EveItemTax.objects.create(
            type_id=34,
            type_name='Tritanium',
            jita_buy_percentage=50.0,
            flat_cost=0,
            hauling_fee=True,  # Enable hauling fee
            category_id=25,
            category_name='Material',
            group_id=18,
            group='Mineral'
        )

        # POST item (volume 0.01, quantity 100)
        response = client.post('/buyback/', {'item_name': 'Tritanium\t100'})

        assert response.status_code == 200
        processed_items = response.context['processed_items']
        assert len(processed_items) == 1

        item = processed_items[0]
        assert item['haul_bool'] is True
        # Haul fee = 200 (rate) * 0.01 (volume) * 100 (quantity) = 200
        assert item['haul_fee'] == 200.0
        # Buyback price = (1000 * 50.0) + 200 = 50200
        assert item['buyback_price'] == 50200.0

    def test_no_hauling_fee_when_disabled(self, client, db, mock_janice_api):
        """Test that no hauling fee is added when disabled."""
        EveItemTax.objects.create(
            type_id=34,
            type_name='Tritanium',
            jita_buy_percentage=50.0,
            flat_cost=0,
            hauling_fee=False,  # Disabled
            category_id=25,
            category_name='Material',
            group_id=18,
            group='Mineral'
        )

        response = client.post('/buyback/', {'item_name': 'Tritanium\t100'})

        assert response.status_code == 200
        item = response.context['processed_items'][0]
        assert item['haul_bool'] is False
        assert item['haul_fee'] == 0.0
        assert item['buyback_price'] == 50000.0  # No haul fee added


class TestFlatCostLogic:
    """Integration tests for flat cost override logic."""

    def test_flat_cost_overrides_percentage(self, client, db, mock_janice_api):
        """Test that flat cost overrides percentage-based calculation."""
        EveItemTax.objects.create(
            type_id=34,
            type_name='Tritanium',
            jita_buy_percentage=50.0,
            flat_cost=750.0,  # Flat cost overrides
            hauling_fee=False,
            category_id=25,
            category_name='Material',
            group_id=18,
            group='Mineral'
        )

        response = client.post('/buyback/', {'item_name': 'Tritanium\t100'})

        assert response.status_code == 200
        item = response.context['processed_items'][0]
        # Should use flat_cost instead of percentage calculation
        assert item['buyback_price'] == 750.0
        assert item['buyback_price_itemtotal'] == 75000.0  # 750 * 100


class TestBulkTaxUpdate:
    """Integration tests for admin bulk tax update functionality."""

    @pytest.fixture
    def staff_user(self, db):
        """Create a staff user for admin tests."""
        return User.objects.create_user(
            username='staff',
            password='testpass123',
            is_staff=True
        )

    @pytest.fixture
    def test_items(self, db):
        """Create test items for bulk update tests."""
        category_id = 25
        group_id = 18
        items = []
        for i in range(3):
            item = EveItemTax.objects.create(
                type_id=34 + i,
                type_name=f'Test Item {i}',
                jita_buy_percentage=50.0,
                flat_cost=0,
                hauling_fee=False,
                category_id=category_id,
                category_name='Material',
                group_id=group_id,
                group='Mineral'
            )
            items.append(item)
        return items

    def test_bulk_tax_update(self, client, db, staff_user, test_items):
        """Test that bulk tax update works for staff users."""
        category_id = 25
        group_id = 18

        # Login as staff user
        client.force_login(staff_user)

        # POST to update Jita Buy Percentage
        response = client.post(
            f'/buyback/tax_edit/{category_id}/{group_id}/',
            {'jita_buy_percentage': 75.0}
        )

        assert response.status_code == 200

        # Verify all items in the group were updated
        updated_items = EveItemTax.objects.filter(
            category_id=category_id,
            group_id=group_id
        )
        assert updated_items.count() == 3
        for item in updated_items:
            assert item.jita_buy_percentage == 75.0

    def test_bulk_flat_cost_update(self, client, db, staff_user, test_items):
        """Test that bulk flat cost update works for staff users."""
        category_id = 25
        group_id = 18

        client.force_login(staff_user)

        # POST to update flat cost
        response = client.post(
            f'/buyback/tax_edit/{category_id}/{group_id}/',
            {'flat_cost': 1000.0}
        )

        assert response.status_code == 200

        # Verify all items were updated
        updated_items = EveItemTax.objects.filter(
            category_id=category_id,
            group_id=group_id
        )
        for item in updated_items:
            assert float(item.flat_cost) == 1000.0

    def test_bulk_update_requires_staff(self, client, db, test_items):
        """Test that non-staff users cannot access bulk update."""
        category_id = 25
        group_id = 18

        # Create regular user (not staff)
        regular_user = User.objects.create_user(
            username='regular',
            password='testpass123',
            is_staff=False
        )
        client.force_login(regular_user)

        # Attempt to POST to update endpoint
        response = client.post(
            f'/buyback/tax_edit/{category_id}/{group_id}/',
            {'jita_buy_percentage': 75.0}
        )

        # Should redirect to login or return 403
        assert response.status_code in [302, 403]

