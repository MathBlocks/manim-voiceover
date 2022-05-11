import os
import azure.cognitiveservices.speech as speechsdk
import json
import hashlib
from dotenv import load_dotenv

from ..speech_synthesizer import SpeechSynthesizer

load_dotenv()


class AzureSpeechSynthesizer(SpeechSynthesizer):
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
            audio_path = os.path.join(output_dir, data_hash + ".mp3")
            json_path = os.path.join(output_dir, data_hash + ".json")

            if os.path.exists(json_path):
                return json.loads(open(json_path, "r").read())
        else:
            audio_path = path
            json_path = os.path.splitext(path)[0] + ".json"

        speech_config = speechsdk.SpeechConfig(
            subscription=os.environ["AZURE_SUBSCRIPTION_KEY"],
            region=os.environ["AZURE_SERVICE_REGION"],
        )
        speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat[self.output_format]
        )
        audio_config = speechsdk.audio.AudioOutputConfig(filename=audio_path)

        speech_synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config, audio_config=audio_config
        )
        word_boundaries = []
        # speech_synthesizer.bookmark_reached.connect(lambda evt: print(
        #     "Bookmark reached: {}, audio offset: {}ms, bookmark text: {}.".format(evt, evt.audio_offset, evt.text)))
        def process_event(evt):
            result = {label[1:]: val for label, val in evt.__dict__.items()}
            result["boundary_type"] = result["boundary_type"].name
            result["audio_offset"] -= 219
            return result

        speech_synthesizer.synthesis_word_boundary.connect(
            lambda evt: word_boundaries.append(process_event(evt))
        )

        speech_synthesis_result = speech_synthesizer.speak_ssml(ssml)
        json_dict = {
            "ssml": ssml,
            "word_boundaries": word_boundaries,
            "original_audio": audio_path,
            "json_path": json_path,
        }

        # open(json_path, "w").write(json.dumps(json_dict, indent=2))

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

        return json_dict
