#!/usr/bin/env python3
"""印刷用の PDF を作るスクリプトのテスト。

  python3 印刷用/test_build.py

一時ディレクトリに PDF を作って、ページ数・紙の大きさ（A5）・各ページの中身を確かめる。
本物の出力（印刷用/*.pdf）は書き換えない。ネットにはつながない（空港チャートは
印刷用/aip/ に落としてある写しを使う。無ければそのテストは飛ばす）。
"""
import importlib.util
import pathlib
import re
import tempfile
import unittest

import fitz  # PyMuPDF

HERE = pathlib.Path(__file__).resolve().parent
A5_PT = (148 / 25.4 * 72, 210 / 25.4 * 72)


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def assert_a5(test, doc):
    for i, page in enumerate(doc):
        test.assertAlmostEqual(page.rect.width, A5_PT[0], delta=1, msg=f"{i + 1} ページ目の幅")
        test.assertAlmostEqual(page.rect.height, A5_PT[1], delta=1, msg=f"{i + 1} ページ目の高さ")


class KneeboardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        out = pathlib.Path(cls.tmp.name)
        load("build_kneeboard").main(out)
        cls.doc = fitz.open(out / "ニーボード.pdf")
        cls.text = [p.get_text() for p in cls.doc]

    @classmethod
    def tearDownClass(cls):
        cls.doc.close()
        cls.tmp.cleanup()

    def test_両面1枚のA5(self):
        # ①非常時と②R44 手順（2026-11-07 に別の PDF だった手順をまとめた）
        self.assertEqual(len(self.doc), 2)
        assert_a5(self, self.doc)

    def test_非常時の面(self):
        t = self.text[0]
        for s in ["① 非常時", "7700", "7600", "7500", "121.5", "赤色の信号弾", "白の閃光"]:
            self.assertIn(s, t)
        # 外すよう指定されたもの
        for s in ["MAYDAY", "PAN-PAN", "要撃"]:
            self.assertNotIn(s, t)
        # 空港は空港チャートへ移した
        self.assertNotIn("RJOB", t)

    def test_非常時の面が下まで収まっている(self):
        # .page は overflow: hidden なので、はみ出すと最後の表が消える
        self.assertIn("右回り", self.text[0])

    def test_手順の面(self):
        t = self.text[1]
        for s in ["② R44 手順", "エンジン始動前", "停止手順"]:
            self.assertIn(s, t)


class ChartsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        mod = load("build_charts")
        missing = [i for i in mod.PICK if not (mod.AIP / f"{i}_chart.pdf").exists()]
        if missing or not (mod.AIP / "info.json").exists():
            raise unittest.SkipTest(f"AIP の写しが無い（{missing}）。先に build_charts.py --fetch")

        def no_fetch(name):
            raise AssertionError(f"テストでネットにつないだ: {name}")

        mod.fetch = no_fetch
        cls.tmp = tempfile.TemporaryDirectory()
        out = pathlib.Path(cls.tmp.name) / "空港チャート.pdf"
        mod.main(out)
        cls.pick = mod.PICK
        cls.doc = fitz.open(out)
        cls.text = [p.get_text() for p in cls.doc]

    @classmethod
    def tearDownClass(cls):
        cls.doc.close()
        cls.tmp.cleanup()

    def test_ページ数とA5(self):
        # 頭の 1 ページが空港一覧
        self.assertEqual(len(self.doc), 1 + sum(len(v) for v in self.pick.values()))
        assert_a5(self, self.doc)

    def test_各ページが選んだ図(self):
        # AIP のページの隅の番号と題で、取り違えていないかを見る
        want = []
        for icao in self.pick:
            want += [(icao, "ADC-1", None), (icao, "OTHER-1", "Visual REP")]
            want.append((icao, "OTHER-2", "Standard traffic pattern" if icao == "RJBK" else "LDG"))
        for i, (icao, label, title) in enumerate(want, start=1):
            t = self.text[i]
            with self.subTest(page=i + 1):
                self.assertRegex(t, rf"{icao} ?AD2\.24-{re.escape(label)}")
                if title:
                    self.assertIn(title, t)

    def test_空港一覧(self):
        # 2026-11-07 にニーボードから移した
        t = self.text[0]
        for s in ["空港一覧", "RJBK", "RJOB", "RJOA", "RJOT", "130.75", "124.3", "118.6", "118.3", "121.2", "127.25", "127.45"]:
            self.assertIn(s, t)
        # AIP に無い呼び方は使わない
        self.assertNotIn("予備", t)

    def test_空港一覧が下まで収まっている(self):
        self.assertIn("NOTAM", self.text[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
