from app.services.progress import handle_message


class PreviewService:
    def __init__(self) -> None:
        self.calls = []

    def apply_preview(self, node_id, image, mime, width, height, step, total):
        self.calls.append((node_id, image, mime, width, height, step, total))


def test_kj_preview_event_is_forwarded_to_the_job_service() -> None:
    service = PreviewService()
    handle_message(
        service,
        {
            "type": "kj_preview_override",
            "data": {
                "node_id": "101",
                "image": "YWJj",
                "mime": "image/jpeg",
                "w": 352,
                "h": 640,
                "step": 3,
                "total": 20,
            },
        },
    )
    assert service.calls == [("101", "YWJj", "image/jpeg", 352, 640, 3, 20)]
