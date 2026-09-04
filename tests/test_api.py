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


def test_session_is_bound_to_account_and_expires(tmp_path):
    store = LicenseStore(tmp_path / "licenses.db")
    store.provision("123", "secret-key", "server-secret")
    token = store.create_session("123", "secret-key", "server-secret")
    assert token
    assert store.authenticate(token, "123")
    assert not store.authenticate(token, "999")


def test_event_idempotency(tmp_path):
    store = LicenseStore(tmp_path / "licenses.db")
    assert store.accept_event_once("123", "deal:42")
    assert not store.accept_event_once("123", "deal:42")
    assert store.accept_event_once("999", "deal:42")
