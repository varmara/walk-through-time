"""A thread's order (pipeline/layerdata.py: in_date_order): by the date of what each item tells, an undated item
staying after the one listed before it; or, with "sort: as listed", the order it is written in."""
import unittest

from pipeline.layerdata import in_date_order


def thread(as_listed=False):
    pins = [{"when": "1900"}, {"text": "no date here"}, {"when": "1280"}, {"when": "2015"}]
    items = [["The Roman ford", ["p0"], {}], ["The old Manor House", ["p1"], {}],
             ["The manor of Wilford", ["p2"], {}], ["Trams", ["p3"], {}]]
    L = {"kind": "topics", "groups": [{"key": "w", "items": items}], **({"asListed": True} if as_listed else {})}
    in_date_order([L], {}, pins, {}, {})
    return [it[0] for it in L["groups"][0]["items"]]


class Order(unittest.TestCase):
    def test_by_date_an_undated_item_stays_after_the_one_before_it(self):
        self.assertEqual(thread(), ["The manor of Wilford", "The Roman ford", "The old Manor House", "Trams"])

    def test_as_listed_keeps_the_written_order(self):
        self.assertEqual(thread(True), ["The Roman ford", "The old Manor House", "The manor of Wilford", "Trams"])
