import pytest
from django.urls import reverse
from buyback.models import EveItemTax
from buyback.views import some_function
from django.contrib.auth.models import User

def test_some_function(caplog):
    """Test the standalone logging function."""
    import logging
    caplog.set_level(logging.DEBUG)
    some_function()
    assert "This is a debug message" in caplog.text
    assert "This is a critical message" in caplog.text

@pytest.mark.django_db
class TestViews:
    @pytest.fixture
    def staff_user(self):
        return User.objects.create_user(username='staff', password='password', is_staff=True)

    @pytest.fixture
    def client_staff(self, client, staff_user):
        client.force_login(staff_user)
        return client

    def test_all_item_tax_view(self, client):
        EveItemTax.objects.create(
            type_id=1, type_name="Test Item", jita_buy_percentage=10, flat_cost=0, hauling_fee=False
        )
        url = reverse('buyback:all_item_tax')
        response = client.get(url)
        assert response.status_code == 200
        assert "Test Item" in response.content.decode()

    def test_update_inventory_view(self, client):
        EveItemTax.objects.create(
             type_id=2, type_name="Test Inv Item", jita_buy_percentage=10, flat_cost=0, hauling_fee=False
        )
        url = reverse('buyback:update_inventory')
        response = client.get(url)
        assert response.status_code == 200
        # Template does not show items, just a link.
        assert "href" in response.content.decode()

    def test_collapsible_tree_view(self, client):
        EveItemTax.objects.create(
            type_id=3, type_name="Tree Item", category_id=1, category_name="Cat1",
            group_id=10, group="Grp1", jita_buy_percentage=10, flat_cost=0
        )
        url = reverse('buyback:collapsible_tree')
        response = client.get(url)
        assert response.status_code == 200
        assert "Cat1" in response.content.decode()
        assert "Grp1" in response.content.decode()

    def test_category_list_view_staff(self, client_staff):
        EveItemTax.objects.create(category_id=1, category_name="CatStaff", type_id=4, type_name="T4", flat_cost=0)
        url = reverse('buyback:category-list')
        response = client_staff.get(url)
        assert response.status_code == 200
        assert "CatStaff" in response.content.decode()

    def test_category_list_view_no_auth(self, client):
        url = reverse('buyback:category-list')
        response = client.get(url)
        assert response.status_code != 200 # Should redirect to login

    def test_group_list_view_staff(self, client_staff):
        EveItemTax.objects.create(category_id=1, group_id=10, group="GrpStaff", type_id=5, type_name="T5", flat_cost=0)
        url = reverse('buyback:group-list', args=[1])
        response = client_staff.get(url)
        assert response.status_code == 200
        assert "GrpStaff" in response.content.decode()

    def test_item_list_view_staff_get(self, client_staff):
        EveItemTax.objects.create(category_id=1, group_id=10, type_id=6, type_name="ItemStaff", jita_buy_percentage=10, flat_cost=0)
        url = reverse('buyback:item-list', args=[1, 10])
        response = client_staff.get(url)
        assert response.status_code == 200
        assert "ItemStaff" in response.content.decode()

    def test_item_list_view_staff_post_flat_cost(self, client_staff):
        item = EveItemTax.objects.create(category_id=1, group_id=10, type_id=7, type_name="ItemFlat", jita_buy_percentage=10, flat_cost=0)
        url = reverse('buyback:item-list', args=[1, 10])
        data = {'flat_cost': '1000', 'save_flat_cost': 'Save'} 
        response = client_staff.post(url, data)
        assert response.status_code == 200
        item.refresh_from_db()
        assert item.flat_cost == 1000

    def test_item_list_view_staff_post_percentage(self, client_staff):
        item = EveItemTax.objects.create(category_id=1, group_id=10, type_id=8, type_name="ItemPerc", jita_buy_percentage=10, flat_cost=0)
        url = reverse('buyback:item-list', args=[1, 10])
        data = {'jita_buy_percentage': '50', 'save_jita_buy_percentage': 'Save'}
        response = client_staff.post(url, data)
        assert response.status_code == 200
        item.refresh_from_db()
        assert item.jita_buy_percentage == 50
