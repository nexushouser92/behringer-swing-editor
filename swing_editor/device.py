"""Talk to the Swing through any port with send/receive/drain (see midi_win.py).

Every message goes through protocol.check_outgoing() first, so nothing outside the allow-list can
be sent even by mistake.
"""
import time

from . import protocol
from .protocol import Ack, ProductInfo, SwingSettings, Value

REPLY_TIMEOUT = 0.5   # the Swing answers in well under 100 ms
RETRIES = 2


class DeviceError(Exception):
    """The Swing did not answer, or answered with something unexpected."""


class VerifyError(DeviceError):
    """After writing, the Swing reported a value different from the one sent."""

    def __init__(self, param_id, sent, received):
        p = protocol.param(param_id)
        super().__init__(f"{p.key}: wrote {sent}, the Swing reports {received}")
        self.param_id, self.sent, self.received = param_id, sent, received


def _send(port, message):
    port.send(protocol.check_outgoing(message))


def _wait_for(port, wanted, timeout):
    """First parsed reply for which wanted(reply) is true, skipping status and other messages."""
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        message = port.receive(remaining) if remaining > 0 else None
        if message is None:
            return None
        reply = protocol.parse(message)
        if reply is not None and wanted(reply):
            return reply


def _ask(port, message, wanted, what, timeout, retries):
    for _ in range(retries + 1):
        _send(port, message)
        reply = _wait_for(port, wanted, timeout)
        if reply is not None:
            return reply
    raise DeviceError(f"the Swing did not answer ({what})")


def read_product_info(port, timeout=REPLY_TIMEOUT, retries=RETRIES):
    """Return the two versions the Swing reports, e.g. ((1, 0, 0), (1, 1, 52))."""
    port.drain()
    reply = _ask(port, protocol.build_product_info_request(),
                 lambda r: isinstance(r, ProductInfo), "product info", timeout, retries)
    return reply.versions


def read_param(port, id_or_key, timeout=REPLY_TIMEOUT, retries=RETRIES):
    p = protocol.param(id_or_key)
    reply = _ask(port, protocol.build_read(p.id),
                 lambda r: isinstance(r, Value) and r.id == p.id, p.key, timeout, retries)
    return reply.value


def read_all(port, progress=None, timeout=REPLY_TIMEOUT, retries=RETRIES):
    """Read the 47 settings one by one. progress(done, total) is called after each one.

    A value outside the known table of an editable setting is a DeviceError: the app only edits
    settings it understands. Unconfirmed settings accept any value (they are never written).
    """
    port.drain()
    values = {}
    total = len(protocol.PARAMS)
    for i, p in enumerate(protocol.PARAMS, 1):
        value = read_param(port, p.id, timeout, retries)
        if p.confirmed and value not in p.allowed:
            raise DeviceError(f"{p.key}: the Swing reports {value}, which this app does not know")
        values[p.id] = value
        if progress:
            progress(i, total)
    return SwingSettings(values)


def write_param(port, id_or_key, value, verify=True, timeout=REPLY_TIMEOUT, retries=RETRIES):
    """Write one setting. The Swing acknowledges it; with verify, read it back and compare."""
    p = protocol.param(id_or_key)
    message = protocol.build_write(p.id, value)   # validates before anything is sent
    port.drain()
    _ask(port, message, lambda r: isinstance(r, Ack) and r.id == p.id, f"write {p.key}", timeout, retries)
    if not verify:
        return value
    received = read_param(port, p.id, timeout, retries)
    if received != value:
        raise VerifyError(p.id, value, received)
    return received


def write_settings(port, settings, current=None, verify=True, progress=None):
    """Write every editable setting of `settings` that differs from `current` (all editable ones
    without current). Unconfirmed settings are never written.

    Returns the list of ids written.
    """
    ids = settings.differences(current) if current is not None else [p.id for p in protocol.EDITABLE]
    for i, pid in enumerate(ids, 1):
        write_param(port, pid, settings[pid], verify)
        if progress:
            progress(i, len(ids))
    return ids
