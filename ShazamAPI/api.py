from pydub import AudioSegment
from io import BytesIO
import requests
import uuid
import time
import json


from .algorithm import SignatureGenerator
from .signature_format import DecodedMessage

LANG = 'ru'
TIME_ZONE = 'Europe/Moscow'


class Endpoint:
    SCHEME = 'https'
    HOSTNAME = 'amp.shazam.com'

    def __init__(
        self,
        lang: str,
        time_zone: str
    ) -> None:
        self.lang = lang
        self.time_zone = time_zone

    @property
    def url(self) -> str:
        return (
            f'{self.SCHEME}://{self.HOSTNAME}'
            '/discovery/v5'
            f'/{self.lang}/{self.lang.upper()}'
            '/iphone/-/tag/{uuid_a}/{uuid_b}'
        )

    @property
    def params(self) -> dict:
        return {
            'sync': 'true',
            'webv3': 'true',
            'sampling': 'true',
            'connected': '',
            'shazamapiversion': 'v3',
            'sharehub': 'true',
            'hubv5minorversion': 'v5.1',
            'hidelb': 'true',
            'video': 'v3'
        }

    @property
    def headers(self) -> dict:
        return {
            "X-Shazam-Platform": "IPHONE",
            "X-Shazam-AppVersion": "14.1.0",
            "Accept": "*/*",
            "Accept-Language": self.lang,
            "Accept-Encoding": "gzip, deflate",
            "User-Agent": "Shazam/3685 CFNetwork/1197 Darwin/20.0.0"
        }


class Shazam:
    MAX_TIME_SECONDS = 8

    def __init__(
        self,
        songData: bytes,
        lang: str = LANG,
        time_zone: str = TIME_ZONE
    ):
        self.songData = songData
        self._endpoint = Endpoint(lang, time_zone)

    def recognizeSong(self) -> dict:
        self.audio = self.normalizateAudioData(self.songData)
        signatureGenerator = self.createSignatureGenerator(self.audio)
        while True:
        
            signature = signatureGenerator.get_next_signature()
            if not signature:
                break
            
            results = self.sendRecognizeRequest(signature)
            currentOffset = signatureGenerator.samples_processed / 16000
            
            yield currentOffset, results
    
    def sendRecognizeRequest(self, sig: DecodedMessage) -> dict:
        data = {
            'timezone': self._endpoint.time_zone,
            'signature': {
                'uri': sig.encode_to_uri(),
                'samplems':int(sig.number_samples / sig.sample_rate_hz * 1000)
                },
            'timestamp': int(time.time() * 1000),
            'context': {},
            'geolocation': {}
                }
        r = requests.post(
            self._endpoint.url.format(
                uuid_a=str(uuid.uuid4()).upper(),
                uuid_b=str(uuid.uuid4()).upper()
            ),
            params=self._endpoint.params,
            headers=self._endpoint.headers,
            json=data
        )
        
        # added status code check
        if r.status_code != 200:
            # Log or handle bad request here (status code 400)
            error_message = f"Request failed with status: {r.status_code}, Response content: {r.text}"
            raise Exception(error_message)
    
        return r.json()
    
    def normalizateAudioData(self, songData: bytes) -> AudioSegment:
        audio = AudioSegment.from_file(BytesIO(songData))
    
        audio = audio.set_sample_width(2)
        audio = audio.set_frame_rate(16000)
        audio = audio.set_channels(1)
        return audio
    
    def createSignatureGenerator(self, audio: AudioSegment) -> SignatureGenerator:
        signature_generator = SignatureGenerator()
        signature_generator.feed_input(audio.get_array_of_samples())
        signature_generator.MAX_TIME_SECONDS = self.MAX_TIME_SECONDS
        if audio.duration_seconds > 12 * 3:
            signature_generator.samples_processed += 16000 * (int(audio.duration_seconds / 16) - 6)
        return signature_generator
