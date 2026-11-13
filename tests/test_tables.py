"""The story check reads an article's tables too (pipeline/s04_curated.py: table_text): the 'Listed buildings in …'
articles keep every building's date and description in one."""
import unittest

from pipeline.s04_curated import table_text


class Tables(unittest.TestCase):
    def test_cells_and_template_fields(self):
        wt = """{| class="wikitable sortable"
|-
! Name and location !! Photograph !! Date !! Notes
|-
| Church of St George<br>{{coord|52.9}} || [[File:x.jpg|150px]] || 14th century || The church, [[Grade I|listed]], was restored in 1877 and 1885.
| style="text-align:center"| II*
{{EH listed building row
| name = Dovecote, Manor Farm
| date = 1677
| notes = The dovecote is in red brick, octagonal in plan.
}}
|}"""
        t = table_text(wt)
        for words in ("Church of St George", "14th century", "restored in 1877 and 1885", "listed", "II*",
                      "Dovecote, Manor Farm", "1677", "octagonal"):
            self.assertIn(words, t)
        self.assertNotIn("coord", t)
        t2 = table_text("""|-
| Workshops || {{sort|1840|{{circa|1840}}}} || Cottages of {{circa|1829}}, {{nowrap|now a museum}}.{{sfn|Pevsner|1979}}
| {{sort|1300|14th century}}""")
        for words in ("c. 1840", "c. 1829", "now a museum", "14th century"):
            self.assertIn(words, t2)
        self.assertNotIn("Pevsner", t2)
        self.assertNotIn("style", t)


if __name__ == "__main__":
    unittest.main()
