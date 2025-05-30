from app.helpers.response import Response

from ..factories.user_factory import mimesis


class TestResponse:
    def test_build_success(self):
        response = Response()

        success = True
        data = {
            mimesis.random.randstr(length=1): mimesis.random.randints(
                amount=1, a=0, b=9
            )[0]
        }
        errors = {
            mimesis.random.randstr(length=1): mimesis.random.randints(
                amount=1, a=0, b=9
            )[0]
        }

        response_body, returned_response_code = response.build(
            success=success, data=data, errors=errors
        )
        assert returned_response_code == 200
        assert response_body["success"] == success
        assert response_body["data"] == data
        assert response_body["errors"] == errors

    def test_success(self):
        response = Response()

        data = {
            mimesis.random.randstr(length=1): mimesis.random.randints(
                amount=1, a=0, b=9
            )[0]
        }

        response_body, returned_response_code = response.success(data)
        assert returned_response_code == 200
        assert response_body["success"]
        assert response_body["data"] == data
        assert "errors" not in response_body

    def test_errors(self):
        response = Response()

        errors = {
            mimesis.random.randstr(length=1): mimesis.random.randints(
                amount=1, a=0, b=9
            )[0]
        }

        response_body, returned_response_code = response.errors(errors)
        assert returned_response_code == 200
        assert not response_body["success"]
        assert response_body["errors"] == errors
        assert "data" not in response_body

        response_body, returned_response_code = response.errors(errors, 400)
        assert returned_response_code == 400
