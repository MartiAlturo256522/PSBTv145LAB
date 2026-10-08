"""Local crypto-psbt QR text receiver, independent of camera and wallet libraries."""
from enum import IntEnum
from helpers.ur2.ur_decoder import URDecoder
from helpers.ur2.crypto_psbt import unwrap_psbt_cbor


class DecodeQRStatus(IntEnum):
    PART_COMPLETE = 1
    PART_EXISTING = 2
    COMPLETE = 3
    FALSE = 4
    INVALID = 5


class DecodeQR:
    def __init__(self):
        self.decoder = URDecoder()
        self.complete = False

    def add_data(self, data):
        if data is None:
            return DecodeQRStatus.FALSE
        if self.complete:
            return DecodeQRStatus.COMPLETE
        if isinstance(data, bytes):
            try:
                data = data.decode('utf-8')
            except UnicodeDecodeError:
                return DecodeQRStatus.INVALID
        if not isinstance(data, str) or not data.lower().startswith('ur:crypto-psbt/'):
            return DecodeQRStatus.INVALID
        added = self.decoder.receive_part(data)
        if self.decoder.is_complete():
            if self.decoder.is_failure():
                return DecodeQRStatus.INVALID
            self.complete = True
            return DecodeQRStatus.COMPLETE
        return DecodeQRStatus.PART_COMPLETE if added else DecodeQRStatus.PART_EXISTING

    def get_psbt(self):
        if not self.complete:
            return None
        raw = unwrap_psbt_cbor(self.decoder.result_message().cbor)
        if not raw.startswith(b'psbt\xff'):
            raise ValueError('invalid PSBT magic')
        return raw

    get_data_psbt = get_psbt
