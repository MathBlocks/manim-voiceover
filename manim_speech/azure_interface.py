import os
import azure.cognitiveservices.speech as speechsdk
import json
import hashlib
from dotenv import load_dotenv

from .speech_synthesizer import SpeechSynthesizer

load_dotenv()


class AzureTTS(SpeechSynthesizer):
    def __init__(
        self,
        voice="en-US-AriaNeural",
        # style="newscast-casual",
        style=None,
        output_format="Audio48Khz192KBitRateMonoMp3",
        **kwargs,
    ):
        self.voice = voice
        self.style = style
        self.output_format = output_format
        SpeechSynthesizer.__init__(self, **kwargs)

    def _synthesize_text(self, text, output_dir=None, path=None):
        inner = text
        if output_dir is None:
            output_dir = self.output_dir

        if self.style is not None:
            inner = r"""<mstts:express-as style="%s">
                    %s
                </mstts:express-as>""" % (
                self.style,
                inner,
            )

        ssml = r"""<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis"
            xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="en-US">
            <voice name="%s">
                %s
            </voice>
        </speak>
        """ % (
            self.voice,
            inner,
        )
        data = {"ssml": ssml, "config": self.__dict__}
        data_hash = self.get_data_hash(data)

        # Get the file extension from output_format
        if self.output_format[-3:] == "Mp3":
            file_extension = ".mp3"
        else:
            raise Exception("Unrecognized output format")

        if path is None:
            path = os.path.join(output_dir, data_hash + file_extension)

            if os.path.exists(path):
                return path

        speech_config = speechsdk.SpeechConfig(
            subscription=os.environ["AZURE_SUBSCRIPTION_KEY"],
            region=os.environ["AZURE_SERVICE_REGION"],
        )
        speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat[self.output_format]
        )
        audio_config = speechsdk.audio.AudioOutputConfig(filename=path)

        speech_synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config, audio_config=audio_config
        )
        speech_synthesis_result = speech_synthesizer.speak_ssml(ssml)

        if (
            speech_synthesis_result.reason
            == speechsdk.ResultReason.SynthesizingAudioCompleted
        ):
            pass
        elif speech_synthesis_result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = speech_synthesis_result.cancellation_details
            print("Speech synthesis canceled: {}".format(cancellation_details.reason))
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                if cancellation_details.error_details:
                    print(
                        "Error details: {}".format(cancellation_details.error_details)
                    )
            raise Exception("Speech synthesis failed")

        return path