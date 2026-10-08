from search_engine.chunking.postprocess import index_text


def test_cell_breaks_become_spaces():
    assert index_text("| 한국의 집<br>관광식당 | 비고 |") == "| 한국의 집 관광식당 | 비고 |"
    assert index_text("가<br><br>나<BR/>다") == "가 나 다"


def test_text_without_breaks_is_unchanged():
    assert index_text("본문\n\n\n\n다음") == "본문\n\n다음"
