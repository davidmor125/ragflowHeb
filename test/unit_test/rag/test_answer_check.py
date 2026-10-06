from rag.answer_check import check_answer, warning_line


def _ck(text):
    return {"content_with_weight": text}


class TestNumbers:
    def test_supported_numbers_pass(self):
        r = check_answer("העמלה היא 12 ₪ ותקרת ההפקדה 150,000 ש\"ח [ID:0].",
                         [_ck("<table><tr><td>משיכת מזומן</td><td>12 ₪</td></tr></table>"), _ck("עד 150000 ש\"ח")])
        assert r["status"] == "ok" and r["unsupported_numbers"] == []

    def test_wrong_amount_is_flagged(self):
        r = check_answer("העמלה על משיכת מזומן בסניף היא 15 ₪ [ID:0].", [_ck("משיכת מזומן בסניף: 12 ₪")])
        assert r["status"] == "warn" and r["unsupported_numbers"] == ["15"]

    def test_old_index_split_numbers_still_match(self):
        # chunks indexed before the span-join fix read "1 5 0,000"
        r = check_answer("עד 150,000 ₪ [ID:0]", [_ck("עד 1 5 0,000 ש \" ח")])
        assert r["unsupported_numbers"] == []

    def test_numbers_from_the_question_are_not_flagged(self):
        r = check_answer("סכום של 5,000 ₪ נמוך מהסף של 10,000 ₪ [ID:0].", [_ck("הסף הוא 10,000 ₪")],
                         question="האם הפקדה של 5,000 ₪ מדווחת?")
        assert r["status"] == "ok"

    def test_rates_dates_codes(self):
        chunks = [_ck("ריבית 3.2% עד 01/01/2026, אסמכתא 090-2012-006, פריים + 1.40%")]
        r = check_answer("ריבית 3.2% בתוקף עד 01/01/2026 (אסמכתא 090-2012-006), פריים + 1.40 [ID:0]", chunks)
        assert r["status"] == "ok" and r["numbers_checked"] == 4

    def test_list_markers_are_ignored(self):
        r = check_answer("1. פנייה לסניף\n2. מילוי טופס [ID:0]", [_ck("פנייה לסניף ומילוי טופס")])
        assert r["status"] == "ok" and r["numbers_checked"] == 0

    def test_source_file_name_is_not_a_number(self):
        r = check_answer("למשך תקופה של שבע שנים [ID:0]. 19868.html", [_ck("שבע שנים")])
        assert r["status"] == "ok" and r["numbers_checked"] == 0

    def test_number_is_not_matched_inside_a_longer_one(self):
        r = check_answer("הקוד הוא 810 [ID:0]", [_ck("ס.פ 8100")])
        assert r["unsupported_numbers"] == ["810"]


class TestCitationsAndNoAnswer:
    def test_answer_without_citation_is_flagged(self):
        r = check_answer("יש לפנות לסניף.", [_ck("יש לפנות לסניף")])
        assert r["status"] == "warn" and "no_citation" in r["reasons"]

    def test_no_information_answer(self):
        r = check_answer("המידע אינו קיים בנהלים שצורפו.", [_ck("משהו אחר 77")])
        assert r["status"] == "no_answer"

    def test_no_information_other_phrasings(self):
        for a in ("המסמכים שהועברו לא מכילים פרטים על הלוואה ייעודית לטיפולי פוריות.",
                  "אין בנהלים אזכור לשקל דיגיטלי.", "הפרטים אינם מופיעים בנהלים."):
            assert check_answer(a, [_ck("משהו אחר")])["status"] == "no_answer", a

    def test_warning_line(self):
        r = check_answer("העמלה היא 15 ₪", [_ck("12 ₪")])
        line = warning_line(r)
        assert "15" in line and "לא נמצאו" in line and "אינה מצטטת" in line
        assert warning_line({"status": "ok"}) == ""
