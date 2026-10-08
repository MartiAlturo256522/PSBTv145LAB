"""Receiver's QR processing classes; image capture and seed dependencies omitted."""
import re
import logging
from enum import IntEnum
from helpers.ur2.ur_decoder import URDecoder
logger = logging.getLogger(__name__)

class QRType:
    """
    Used with DecodeQR and EncodeQR to communicate qr encoding type
    """
    # PSBT types
    PSBT__UR2 = "psbt__ur2"

    # Seed types
    SEED__COMPACTSEEDQR = "seed__compactseedqr"

    INVALID = "invalid"


class DecodeQRStatus(IntEnum):
    """
    Used in DecodeQR to communicate status of adding qr frame/segment
    """

    PART_COMPLETE = 1
    PART_EXISTING = 2
    COMPLETE = 3
    FALSE = 4
    INVALID = 5

class DecodeQR:
    """
    Used to process images or string data from animated qr codes.
    """

    def __init__(self):
        self.complete = False
        self.qr_type = None
        self.decoder = None

    def add_image(self, image):
        data = DecodeQR.extract_qr_data(image, is_binary=True)

        if data is None:
            return DecodeQRStatus.FALSE

        return self.add_data(data)

    def add_data(self, data):
        if data is None:
            return DecodeQRStatus.FALSE

        qr_type = DecodeQR.detect_segment_type(data)

        if self.qr_type is None:
            self.qr_type = qr_type

            if self.qr_type == QRType.PSBT__UR2:
                self.decoder = URDecoder()
            elif self.qr_type == QRType.SEED__COMPACTSEEDQR:
                self.decoder = SeedQrDecoder()
            else:
                return DecodeQRStatus.INVALID

        elif self.qr_type != qr_type:
            raise Exception("QR Fragment Unexpected Type Change")

        if not self.decoder:
            # Did not find any recognizable format
            return DecodeQRStatus.INVALID

        # Seed Detected
        if self.qr_type == QRType.SEED__COMPACTSEEDQR:
            qr_str = data
            rt = self.decoder.add(qr_str, self.qr_type)
            self.complete = True
            return rt
        if self.qr_type == QRType.PSBT__UR2:
            if isinstance(data, bytes):
                qr_str = data.decode("utf-8")
            else:
                qr_str = data
            added_part = self.decoder.receive_part(qr_str)
            if self.decoder.is_complete():
                self.complete = True
                return DecodeQRStatus.COMPLETE
            if added_part:
                return DecodeQRStatus.PART_COMPLETE
            else:
                return DecodeQRStatus.PART_EXISTING

    def get_psbt(self):
        if self.complete:
            return self.get_data_psbt()
        return None

    def get_data_psbt(self):
        if self.complete:
            if self.qr_type == QRType.PSBT__UR2:
                return self.decoder.result_message().cbor

        return None

    def get_seed_phrase(self):
        if self.is_seed:
            return self.decoder.get_seed_phrase()

    def get_qr_data(self) -> dict:
        """
        This provides a single access point for external code to retrieve the QR data,
        regardless of which decoder is actually instantiated.
        """
        # TODO: Implement this approach across all decoders
        return self.decoder.get_qr_data()

    def get_percent_complete(self, weight_mixed_frames: bool = False) -> int:
        if not self.decoder:
            return 0

        if self.qr_type == QRType.PSBT__UR2:
            return int(
                self.decoder.estimated_percent_complete(
                    weight_mixed_frames=weight_mixed_frames
                )
                * 100
            )

        elif self.decoder.total_segments == 1:
            # The single frame QR formats are all or nothing
            if self.decoder.complete:
                return 100
            else:
                return 0

        else:
            return 0

    @property
    def is_complete(self) -> bool:
        return self.complete

    @property
    def is_invalid(self) -> bool:
        return self.qr_type == QRType.INVALID

    @property
    def is_psbt(self) -> bool:
        return self.qr_type == QRType.PSBT__UR2

    @property
    def is_seed(self):
        return self.qr_type == QRType.SEED__COMPACTSEEDQR


    @staticmethod
    def extract_qr_data(image, is_binary: bool = False) -> str:
        if image is None:
            return None

        barcodes = pyzbar.decode(image, symbols=[ZBarSymbol.QRCODE], binary=is_binary)

        for barcode in barcodes:
            # Only pull and return the first barcode
            return barcode.data

    @staticmethod
    def detect_segment_type(s):

        if isinstance(s, bytes):
            if len(s) == 16:
                return QRType.SEED__COMPACTSEEDQR
            try:
                s = s.decode("utf-8")
            except Exception:
                return QRType.INVALID

        # PSBT
        if re.search("^UR:CRYPTO-PSBT/", s, re.IGNORECASE):
            return QRType.PSBT__UR2

            
        return QRType.INVALID
