import pytest
from buyback.views import parse_user_input, calculate_buyback_price


class TestParseUserInput:
    """Test cases for parse_user_input function."""

    @pytest.mark.parametrize("input_data,expected", [
        # Tab-separated input (standard case)
        (
            "Tritanium\t1000",
            [{"name": "Tritanium", "quantity": 1000}]
        ),
        # Multiple items with tabs
        (
            "Tritanium\t1000\nPyerite\t500",
            [
                {"name": "Tritanium", "quantity": 1000},
                {"name": "Pyerite", "quantity": 500}
            ]
        ),
        # Space-separated input (manual entry)
        (
            "Tritanium 1000",
            [{"name": "Tritanium", "quantity": 1000}]
        ),
        # Space-separated with multiple words
        (
            "Tritanium Ore 1000",
            [{"name": "Tritanium Ore", "quantity": 1000}]
        ),
        # Input with comma formatting
        (
            "Tritanium\t1,000",
            [{"name": "Tritanium", "quantity": 1000}]
        ),
        # Input with dot formatting (non-US format)
        (
            "Tritanium\t1.000",
            [{"name": "Tritanium", "quantity": 1000}]
        ),
        # Missing quantity defaults to 1
        (
            "Tritanium",
            [{"name": "Tritanium", "quantity": 1}]
        ),
        # Empty quantity string defaults to 1
        (
            "Tritanium\t",
            [{"name": "Tritanium", "quantity": 1}]
        ),
        # Multiple items with mixed formats
        (
            "Tritanium\t1,000\nPyerite 500\nMegacyte",
            [
                {"name": "Tritanium", "quantity": 1000},
                {"name": "Pyerite", "quantity": 500},
                {"name": "Megacyte", "quantity": 1}
            ]
        ),
        # Whitespace handling
        (
            "  Tritanium  \t  1000  ",
            [{"name": "Tritanium", "quantity": 1000}]
        ),
    ])
    def test_parse_user_input(self, input_data, expected):
        """Test parse_user_input with various input formats."""
        result = parse_user_input(input_data)
        assert result == expected

    def test_parse_user_input_empty_string(self):
        """Test parse_user_input with empty string."""
        result = parse_user_input("")
        # Empty string still creates one line with empty name and default quantity
        assert result == [{'name': '', 'quantity': 1}]

    def test_parse_user_input_multiline_with_empty_lines(self):
        """Test parse_user_input handles empty lines gracefully."""
        input_data = "Tritanium\t1000\n\nPyerite\t500"
        result = parse_user_input(input_data)
        # Empty lines should create items with empty name and default quantity
        assert len(result) == 3
        assert result[0] == {"name": "Tritanium", "quantity": 1000}
        assert result[2] == {"name": "Pyerite", "quantity": 500}


class TestCalculateBuybackPrice:
    """Test cases for calculate_buyback_price function."""

    @pytest.mark.parametrize("item_price,tax_rate,expected", [
        # Standard calculation
        (1000.0, 50.0, 500.0),  # 1000 * (50/100) = 500
        # Zero tax rate
        (1000.0, 0.0, 0.0),
        # 100% tax rate
        (1000.0, 100.0, 1000.0),
        # High precision
        (1234.56, 75.5, 932.0928),  # 1234.56 * (75.5/100) = 932.0928
        # Small values
        (1.0, 10.0, 0.1),
    ])
    def test_calculate_buyback_price(self, item_price, tax_rate, expected):
        """Test calculate_buyback_price with various inputs."""
        result = calculate_buyback_price(item_price, tax_rate)
        assert abs(result - expected) < 0.0001  # Allow small floating point differences

