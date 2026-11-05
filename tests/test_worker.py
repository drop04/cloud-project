from worker import build_prompt, shard_lines


def test_sharding_is_a_partition():
    lines = [str(i) for i in range(10)]
    a, b, c = (shard_lines(lines, i, 3) for i in range(3))
    assert sorted(a + b + c, key=int) == lines and not (set(a) & set(b))
    assert a == ["0", "3", "6", "9"]


def test_prompt_keeps_json_braces():
    out = build_prompt('{"k": 1}\nCommand: {command}', "hi")
    assert out.endswith("Command: hi") and '{"k": 1}' in out
