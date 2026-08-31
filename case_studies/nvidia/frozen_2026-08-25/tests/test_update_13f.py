from scripts.update_13f import normalize


def test_13f_parser_handles_equity_row_and_blank_put_call() -> None:
    raw = """
    <table><tr>
      <td>NVIDIA TEST ISSUER</td><td>COM</td><td>123456789</td><td></td>
      <td>1,234</td><td>56</td><td>SH</td><td></td><td>SOLE</td><td></td>
      <td>56</td><td>0</td><td>0</td>
    </tr></table>
    """
    rows = normalize(raw)
    assert rows == [
        {
            "issuer": "NVIDIA TEST ISSUER",
            "title_of_class": "COM",
            "cusip": "123456789",
            "figi": None,
            "value_usd": 1234,
            "shares_or_principal": 56,
            "amount_type": "SH",
            "put_call": None,
            "investment_discretion": "SOLE",
            "other_manager": None,
            "voting_sole": 56,
            "voting_shared": 0,
            "voting_none": 0,
        }
    ]
