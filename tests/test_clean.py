import json
from clean import check, clean, serialise


def rec(i, text, obj):
    return {"id": i, "text": text, "teacher_raw": obj if isinstance(obj, str) else json.dumps(obj)}


GOOD = {"intent": "weather_query", "date": None, "time": None, "place": "london"}


def test_each_rejection_reason():
    assert check(rec("1", "weather in london", "not json")) == "a"
    assert check(rec("1", "weather in london", {"intent": "weather_query"})) == "b"
    assert check(rec("1", "weather in london", {**GOOD, "intent": "play_music"})) == "c"
    assert check(rec("1", "weather in london", {**GOOD, "place": "paris"})) == "d"
    assert check(rec("1", "weather in london", GOOD)) is None


def test_counts_add_up_and_duplicates_keep_smallest_id():
    rows = [rec("C2", "weather in london", GOOD), rec("C1", "weather in london", GOOD),
            rec("C3", "x", "oops"), rec("C4", "weather in london please", {**GOOD})]
    kept, c = clean(rows)
    assert [r["id"] for r in kept] == ["C1", "C4"]
    assert c["input"] == 4 and c["a"] == 1 and c["duplicates"] == 1 and c["kept"] == 2


def test_output_is_deterministic():
    rows = [rec("C2", "b london", GOOD), rec("C1", "a london", GOOD)]
    assert serialise(clean(rows)[0]) == serialise(clean(list(reversed(rows)))[0])
