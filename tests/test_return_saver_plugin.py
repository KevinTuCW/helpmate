from helpmate.plugins import TurnContext
from helpmate.plugins.return_saver import negotiate


class Response:
    status_code = 200

    def json(self):
        return {"status": "offer_made", "reply": "Offer ready",
                "session_id": "S-rs", "stage": "S5_execute", "offer": None}


def test_order_id_in_customer_confirmation_is_forwarded():
    captured = {}

    def post(url, **kwargs):
        captured.update(kwargs["json"])
        return Response()

    reply = negotiate(
        TurnContext(question="Yes, it is ORD-1001", tenant_id="public",
                    customer_id="C-001", session_id="H-1", ext_session_id="S-rs",
                    tool_args={}),
        base="http://return-saver", key="dev", timeout=1, post=post,
    )

    assert reply.handled is True
    assert captured["session_id"] == "S-rs"
    assert captured["confirm_order_id"] == "ORD-1001"
