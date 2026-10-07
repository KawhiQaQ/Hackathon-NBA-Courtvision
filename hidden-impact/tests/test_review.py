import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'cloud/api'))
from review import reviewed_result


class ReviewTests(unittest.TestCase):
    def test_known_wrong_identity_is_removed_without_overwriting_original(self):
        original={'job':'6d19f03b58941f8de021367f5db55ea3','events':[{'score':70}]}
        result=reviewed_result(original)
        self.assertEqual(result['events'],[])
        self.assertEqual(result['review']['status'],'rejected')
        self.assertEqual(original['events'][0]['score'],70)

    def test_rejection_is_scoped_to_exact_run(self):
        result=reviewed_result({'job':'new-run-same-video','events':[{'score':30}]})
        self.assertEqual(result['events'][0]['score'],30)
        self.assertEqual(result['review']['status'],'unverified')
