from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import setup_device as setup


class SetupTests(unittest.TestCase):
    def test_usb_setup_is_backed_up_and_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mount = root / 'Kindle'
            koreader = mount / 'koreader'
            ssh = koreader / 'settings/SSH'
            ssh.mkdir(parents=True)
            (mount / 'documents').mkdir()
            (koreader / 'dropbear').write_bytes(b'fixture')
            settings = koreader / 'settings.reader.lua'
            original = 'return {\n    ["language"] = "zh_CN",\n    ["SSH_port"] = "22",\n    ["SSH_allow_no_password"] = true,\n}\n'
            settings.write_text(original)
            (ssh / 'authorized_keys').write_text('# existing unrelated key kept\n')
            with patch.object(setup.kp, 'DATA', root / 'data'), patch('builtins.print'):
                setup.install_usb(mount)
                first = settings.read_bytes()
                key = (root / 'data/id_ed25519.pub').read_bytes()
                setup.install_usb(mount)
            self.assertEqual(settings.read_bytes(), first)
            self.assertEqual((root / 'data/id_ed25519.pub').read_bytes(), key)
            self.assertIn('["language"] = "zh_CN"', settings.read_text())
            self.assertIn('["SSH_key_only_auth"] = true', settings.read_text())
            self.assertIn('["SSH_allow_no_password"] = false', settings.read_text())
            auth = (ssh / 'authorized_keys').read_text()
            self.assertIn('# existing unrelated key kept', auth)
            self.assertEqual(auth.count('command="sh '), 1)
            backups = list((root / 'data/backups').glob('*/settings.reader.lua'))
            self.assertEqual(len(backups), 2)
            self.assertTrue(any(p.read_text() == original for p in backups))

    def test_wrong_mount_does_not_create_pairing_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(setup.kp, 'DATA', root / 'data'):
                with self.assertRaises(ValueError): setup.install_usb(root)
            self.assertFalse((root / 'data').exists())

    def test_unrecognized_settings_are_rejected(self):
        with self.assertRaises(ValueError): setup.updated_settings('unrecognized format')


if __name__ == '__main__':
    unittest.main()
