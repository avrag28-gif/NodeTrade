import time

from nodetrade.api import LicenseStore


def test_license_store_binds_key_to_account(tmp_path):
    store = LicenseStore(tmp_path / "licenses.db")
    store.provision("123", "secret-key", "server-secret")

    assert store.verify("123", "secret-key", "server-secret")
    assert not store.verify("999", "secret-key", "server-secret")
    assert not store.verify("123", "wrong-key", "server-secret")
    assert not store.verify("123", "secret-key", "wrong-server-secret")


def test_expired_license_is_rejected(tmp_path):
    store = LicenseStore(tmp_path / "licenses.db")
    store.provision("123", "secret-key", "server-secret", expires_at=int(time.time()) - 1)

    assert not store.verify("123", "secret-key", "server-secret")
