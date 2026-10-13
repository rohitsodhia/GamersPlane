from app.character_sheets.defaults import default_sheet_layout


def test_default_sheet_layout_returns_an_isolated_copy_each_call():
    first = default_sheet_layout()
    first["elements"].append({"type": "section", "content": []})

    assert default_sheet_layout() != first
