"""Real reference byte ranges and local startup regression coverage."""
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings


class IgvReferenceTests(TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.fasta = self.root / 'GRCh37.fa'
        self.fasta.write_bytes(b'>chr1\nACGTACGT\n')
        self.index = self.root / 'GRCh37.fa.fai'
        self.index.write_bytes(b'chr1\t8\t6\t8\t9\n')
        self.config = override_settings(PRONTO_IGV_REFERENCE_FILES={
            'GRCh37': {'fasta': str(self.fasta), 'index': str(self.index)}})
        self.config.enable()
        self.addCleanup(self.config.disable)
        self.user = get_user_model().objects.create_user(username='reference-reader')

    def test_reference_bytes_require_an_active_login(self):
        url = '/igv/references/GRCh37/fasta/'
        assert self.client.get(url, HTTP_RANGE='bytes=6-9').status_code == 401
        self.client.force_login(self.user)
        self.user.is_active = False
        self.user.save()
        assert self.client.get(url, HTTP_RANGE='bytes=6-9').status_code == 401

    def test_igv_reads_exact_local_sequence_ranges_and_index(self):
        self.client.force_login(self.user)
        response = self.client.get('/igv/references/GRCh37/fasta/', HTTP_RANGE='bytes=6-9')
        assert response.status_code == 206
        assert response['Content-Range'] == 'bytes 6-9/15'
        assert response['Content-Length'] == '4'
        assert response['Accept-Ranges'] == 'bytes'
        assert b''.join(response.streaming_content) == b'ACGT'
        response = self.client.get('/igv/references/GRCh37/index/')
        assert response.status_code == 200
        assert b''.join(response.streaming_content) == self.index.read_bytes()
        head = self.client.head('/igv/references/GRCh37/fasta/')
        assert head.status_code == 200 and head['Content-Length'] == '15'
        assert head.content == b''
        head = self.client.head('/igv/references/GRCh37/fasta/', HTTP_RANGE='bytes=6-9')
        assert head.status_code == 206 and head['Content-Range'] == 'bytes 6-9/15'

    def test_full_fasta_and_invalid_ranges_are_rejected(self):
        self.client.force_login(self.user)
        for header in (None, 'bytes=99-', 'bytes=0-1,4-6', 'bytes='+'9'*5000+'-'):
            response = self.client.get('/igv/references/GRCh37/fasta/',
                                       **({'HTTP_RANGE': header} if header else {}))
            assert response.status_code == 416
            assert response['Content-Range'] == 'bytes */15'

    def test_unknown_or_missing_references_do_not_disclose_paths(self):
        self.client.force_login(self.user)
        for path in ('GRCh38/fasta', 'unknown/fasta', 'GRCh37/private'):
            response = self.client.get('/igv/references/'+path+'/')
            assert response.status_code == 404
            assert str(self.root).encode() not in response.content
        self.fasta.unlink()
        assert self.client.get('/igv/references/GRCh37/fasta/', HTTP_RANGE='bytes=0-1').status_code == 404

    def test_reference_symlink_is_not_followed(self):
        self.client.force_login(self.user)
        destination = self.root / 'other.fa'
        self.fasta.rename(destination)
        try:
            self.fasta.symlink_to(destination)
        except OSError:
            self.skipTest('Creating symlinks requires Windows developer mode')
        assert self.client.get('/igv/references/GRCh37/fasta/', HTTP_RANGE='bytes=0-1').status_code == 404

    def test_local_startup_finds_complete_pairs_without_enabling_alignment_saving(self):
        from importlib import reload
        from unittest.mock import patch
        from pronto_web import local_settings, settings
        reference_dir = self.root / '.local-web' / 'references'
        reference_dir.mkdir(parents=True)
        (reference_dir/'GRCh37.fa').write_bytes(self.fasta.read_bytes())
        (reference_dir/'GRCh37.fa.fai').write_bytes(self.index.read_bytes())
        (reference_dir/'GRCh38.fa').write_bytes(self.fasta.read_bytes())  # incomplete pair
        try:
            with patch.object(settings, 'BASE_DIR', self.root):
                config = reload(local_settings)
                assert config.PRONTO_IGV_REFERENCES['GRCh37'] == {
                    'fastaURL': '/igv/references/GRCh37/fasta/',
                    'indexURL': '/igv/references/GRCh37/index/'}
                assert config.PRONTO_IGV_REFERENCE_FILES['GRCh37']['fasta'] == str(reference_dir/'GRCh37.fa')
                assert not all(config.PRONTO_IGV_REFERENCES['GRCh38'].values())
                assert not config.PRONTO_ALIGNMENT_POLICY_APPROVED
        finally:
            reload(local_settings)
