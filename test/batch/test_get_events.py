import pytest
from bs4 import BeautifulSoup

from batch.get_events import _parse_date_range, _extract_events_from_p, _is_in_collapsed_region


class TestParseDateRange:
    """日付範囲テキストから開始日と終了日を取り出す"""

    @pytest.mark.parametrize("name,text,expected_start,expected_end", [
        (
            "年月日〜年月日のフルフォーマット",
            "2024/3/1〜2024/3/31",
            "2024/03/01",
            "2024/03/31",
        ),
        (
            "年月日〜月日の省略フォーマット（同年内）",
            "2024/3/1〜3/31",
            "2024/03/01",
            "2024/03/31",
        ),
        (
            "年をまたぐ省略フォーマット（翌年扱い）",
            "2024/12/1〜1/31",
            "2024/12/01",
            "2025/01/31",
        ),
        (
            "全角チルダ（～）での区切り",
            "2024/3/1～2024/3/31",
            "2024/03/01",
            "2024/03/31",
        ),
        (
            "1桁月日のゼロ埋め",
            "2024/1/5〜2024/1/9",
            "2024/01/05",
            "2024/01/09",
        ),
    ])
    def test_日付範囲を開始日と終了日に分割する(self, name, text, expected_start, expected_end):
        # When
        start, end = _parse_date_range(text)

        # Then
        assert start == expected_start
        assert end == expected_end

    @pytest.mark.parametrize("name,text", [
        ("区切り文字なし", "2024/3/1"),
        ("開始日が数値でない", "不明〜2024/3/31"),
        ("空文字", ""),
    ])
    def test_解析できない場合は空文字のペアを返す(self, name, text):
        # When
        start, end = _parse_date_range(text)

        # Then
        assert start == ""


class TestExtractEventsFromP:
    """pタグのテキストからイベント情報を抽出する"""

    def _make_p(self, html: str):
        soup = BeautifulSoup(f"<p>{html}</p>", "html.parser")
        return soup.find("p")

    def test_イベント名と日付範囲を抽出する(self):
        # Given: イベント名と日付範囲を含むpタグ
        p = self._make_p("新イベント（2024/3/1〜2024/3/31）")

        # When
        events = _extract_events_from_p(p)

        # Then: イベント情報が正しく抽出される
        assert len(events) == 1
        assert events[0]["title"] == "新イベント"
        assert events[0]["start"] == "2024/03/01"
        assert events[0]["end"] == "2024/03/31"

    def test_複数のイベントを連続して抽出する(self):
        # Given: 複数のイベントが並ぶpタグ
        p = self._make_p(
            "イベントA（2024/3/1〜2024/3/15）イベントB（2024/3/16〜2024/3/31）"
        )

        # When
        events = _extract_events_from_p(p)

        # Then: 両方のイベントが抽出される
        assert len(events) == 2
        assert events[0]["title"] == "イベントA"
        assert events[1]["title"] == "イベントB"

    def test_日付範囲がない場合はイベントを抽出しない(self):
        # Given: 日付範囲を含まないpタグ
        p = self._make_p("ただのお知らせテキスト")

        # When
        events = _extract_events_from_p(p)

        # Then
        assert events == []

    def test_カテゴリプレフィックスがタイトルから除去される(self):
        # Given: 「期間限定イベント」プレフィックス付きタイトル
        p = self._make_p("期間限定イベント新イベント（2024/3/1〜2024/3/31）")

        # When
        events = _extract_events_from_p(p)

        # Then: プレフィックスが除去された純粋なタイトルになっている
        assert events[0]["title"] == "新イベント"

    def test_終了日が省略形式でも抽出できる(self):
        # Given: 年省略の終了日
        p = self._make_p("イベントC（2024/12/20〜1/10）")

        # When
        events = _extract_events_from_p(p)

        # Then
        assert events[0]["start"] == "2024/12/20"
        assert events[0]["end"] == "2025/01/10"


class TestIsInCollapsedRegion:
    """折りたたみ領域内にある要素かどうかを判定する"""

    def test_display_noneのrgn_content内の要素はTrue(self):
        # Given: display:none のrgn-contentを持つ構造
        html = """
        <div class="rgn-content" style="display: none;">
            <p id="target">コンテンツ</p>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        target = soup.find(id="target")

        # When
        result = _is_in_collapsed_region(target)

        # Then
        assert result is True

    def test_display_noneのない要素はFalse(self):
        # Given: 通常の表示要素
        html = """
        <div class="rgn-content" style="display: block;">
            <p id="target">コンテンツ</p>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        target = soup.find(id="target")

        # When
        result = _is_in_collapsed_region(target)

        # Then
        assert result is False

    def test_rgn_content以外のdisplay_noneはFalse(self):
        # Given: rgn-content クラスを持たない非表示要素
        html = """
        <div style="display: none;">
            <p id="target">コンテンツ</p>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        target = soup.find(id="target")

        # When
        result = _is_in_collapsed_region(target)

        # Then: rgn-content でないので False
        assert result is False
