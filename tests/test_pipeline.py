"""Fast tests for reusable TrainFo pipeline behavior."""

import unittest

import pandas as pd

from src.trainfo_pipeline.downloader import parse_crossing
from src.trainfo_pipeline.transform import select_eight_streets


class PipelineTests(unittest.TestCase):
    def test_parse_crossing_extracts_name_and_fra_id(self):
        self.assertEqual(
            parse_crossing("Airport Blvd - 023228P"),
            ("Airport Blvd", "023228P"),
        )

    def test_select_eight_streets_filters_by_fra_id(self):
        frame = pd.DataFrame(
            {
                "FRA Number": ["288129A", "not-selected"],
                "Crossing Name": ["Commerce Street", "Other"],
            }
        )
        selected = select_eight_streets(frame, {"288129A"})
        self.assertEqual(selected["Crossing Name"].tolist(), ["Commerce Street"])


if __name__ == "__main__":
    unittest.main()
