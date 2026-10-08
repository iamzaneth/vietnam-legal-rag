"""Discovery hints must not confuse cited bodies or source IDs with metadata."""
import unittest
from vietnam_legal_rag.evaluation.validation_sampler import candidate_metadata


class ValidationSamplerTests(unittest.TestCase):
    def test_local_issuer_wins_over_central_citations_in_title(self):
        for slug in ('chi-thi-so-16-2010-ct-ubnd-ve-thuc-hien-nghi-dinh-51-2010-nd-cp--93024',
                     'chi-thi-so-10-2003-ct-ub-v-v-thuc-hien-thong-tu-05-2003-tt-bxd--70072'):
            self.assertEqual(candidate_metadata('https://vbpl.vn/van-ban/chi-tiet/' + slug, '', 0)['scope_hint'], 'dia_phuong')

    def test_central_title_mentioning_local_bodies_does_not_select_local(self):
        url = 'https://vbpl.vn/van-ban/chi-tiet/nghi-dinh-so-51-2010-nd-cp-ve-quyen-han-cua-ubnd--123'
        self.assertEqual(candidate_metadata(url, '', 0)['scope_hint'], 'trung_uong')

    def test_numeric_document_identity_is_not_an_issuance_year(self):
        url = 'https://vbpl.vn/van-ban/chi-tiet/luat-sua-doi-so-39-lct-hdnn8--2068'
        self.assertIsNone(candidate_metadata(url, '', 0)['year_hint'])
        url = 'https://vbpl.vn/van-ban/chi-tiet/luat-so-60-2005-qh11--16726'
        self.assertEqual(candidate_metadata(url, '', 0)['year_hint'], 2005)
