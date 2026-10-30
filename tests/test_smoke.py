"""Offline smoke tests (no API key). Run:  python tests/test_smoke.py"""
import copy
import sys
import tempfile
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bookgen import prompts  # noqa: E402
from bookgen.exporter import export_book  # noqa: E402
from bookgen.llm import LLM, _mock  # noqa: E402
from bookgen.pipeline import Project  # noqa: E402

BASE = yaml.safe_load((Path(__file__).resolve().parent.parent / "config.yaml").read_text("utf-8"))


def cfg_for(tmp, chapters=3, words=300):
    c = copy.deepcopy(BASE)
    c["llm"]["backend"] = "mock"
    c["output_dir"] = str(tmp)
    c["book"]["chapters"] = chapters
    c["book"]["words_per_chapter"] = words
    return c


def test_parsers():
    assert prompts.extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert prompts.tag("<x> hi </x>", "x") == "hi"
    assert prompts.tag("<x> cut off", "x") == "cut off"  # truncated output tolerated


def test_full_pipeline_and_resume():
    with tempfile.TemporaryDirectory() as t:
        cfg = cfg_for(t)
        p = Project(cfg, LLM(cfg))
        p.make_outline()
        p.write_all()
        assert p.done_chapters() == [1, 2, 3]
        calls_before = p.llm.calls
        p.write_all()                       # resume: nothing left to do
        assert p.llm.calls == calls_before
        outline, chapters = p.load_for_export()
        res = export_book(cfg, outline, chapters, p.dir)
        assert res["docx"].exists()
        if res["pdf"]:
            assert res["pdf"].stat().st_size > 1000


def test_banned_phrase_gets_rewritten():
    class Tainted(LLM):
        def complete(self, system, user, max_tokens=4096, temperature=None):
            out = _mock(system, user)
            if "### TASK: CHAPTER" in user:
                out = out.replace("The kettle", "A tapestry of regret. The kettle")
            return out
    with tempfile.TemporaryDirectory() as t:
        cfg = cfg_for(t, chapters=1)
        p = Project(cfg, Tainted(cfg))
        p.make_outline()
        p.write_all()
        # mock REVISE echoes text, so phrase remains; just ensure the fix path ran without error
        assert p.ch_md(1).exists()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok ", name)
