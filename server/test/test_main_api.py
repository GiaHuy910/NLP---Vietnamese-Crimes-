import unittest
from unittest.mock import patch

from fastapi import HTTPException

from server.src.main import ProcessRequest, detect_event_triggers, process_post
from server.src.ner_pipeline.errors import NERPipelineError


class ProcessEndpointTests(unittest.TestCase):
    def test_returns_entities_from_predict_sentence(self) -> None:
        entities = [
            {"text": "Nguyễn Văn A", "label": "PERSON", "start": 48, "end": 60}
        ]
        text = "Ngày 15/8, Công an đã khởi tố Nguyễn Văn A."

        with patch("server.src.main.predict_sentence", return_value=entities) as predict:
            response = process_post(ProcessRequest(text=text))

        predict.assert_called_once_with(text)
        self.assertEqual(response["input_text"], text)
        self.assertEqual(response["entities"], entities)
        self.assertEqual(response["status"], "success")

    def test_rejects_empty_text(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            process_post(ProcessRequest(text="  "))

        self.assertEqual(raised.exception.status_code, 400)

    def test_reports_missing_model_as_service_unavailable(self) -> None:
        with patch(
            "server.src.main.predict_sentence",
            side_effect=NERPipelineError("NER model is missing."),
        ):
            with self.assertRaises(HTTPException) as raised:
                process_post(ProcessRequest(text="Một câu tin tức."))

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(raised.exception.detail, "NER model is missing.")

    def test_returns_triggers_from_detect_triggers(self) -> None:
        triggers = [
            {
                "text": "khởi tố",
                "event_type": "KHOI_TO",
                "start": 29,
                "end": 36,
            }
        ]
        text = "Công an đã khởi tố Nguyễn Văn A."

        with patch(
            "server.src.main.detect_triggers", return_value=triggers
        ) as detect:
            response = detect_event_triggers(ProcessRequest(text=text))

        detect.assert_called_once_with(text)
        self.assertEqual(response["input_text"], text)
        self.assertEqual(response["triggers"], triggers)

    def test_event_trigger_endpoint_rejects_empty_text(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            detect_event_triggers(ProcessRequest(text="  "))

        self.assertEqual(raised.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
