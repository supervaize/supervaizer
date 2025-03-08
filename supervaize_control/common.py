import json
import traceback
import demjson3

from pydantic import BaseModel


class SvBaseModel(BaseModel):
    """
    Base model for all Supervaize models.
    """

    @property
    def to_dict(self):
        return self.model_dump()

    @property
    def to_json(self):
        return self.model_dump_json()


class ApiResult:
    def __init__(self, message: str, detail: dict | str, code: str):
        self.message = message
        self.code = str(code)
        self.detail = detail

    def __str__(self) -> str:
        return self.json_return

    def __repr__(self) -> str:
        return f"{self.__class__.__name__} {self.json_return}"

    @property
    def dict(self) -> dict:
        return {key: value for key, value in self.__dict__.items()}

    @property
    def json_return(self) -> str:
        return json.dumps(self.dict)


class ApiSuccess(ApiResult):
    def __init__(self, message: str, detail: dict | str, code: str = 200):
        super().__init__(message, detail, code)
        if isinstance(detail, str):
            result = demjson3.decode(detail, return_errors=True)
            self.detail = result.object
            self.id = result.object.get("id") or None
            self.log_message = f"✅ {message} : {self.id}"
        else:
            self.detail = detail
            self.log_message = f"✅ {message}"


class ApiError(ApiResult):
    def __init__(
        self,
        message: str,
        code: str = "",
        detail: dict = {},
        exception: Exception | None = None,
        url: str = "",
        payload: dict = {},
    ):
        super().__init__(message, detail, code)
        self.exception = exception
        self.url = url
        self.payload = payload
        self.log_message = f"❌ {message} : {self.exception}"

    @property
    def dict(self) -> dict:
        if self.exception:
            exception_dict = {
                "type": type(self.exception).__name__,
                "message": str(self.exception),
                "traceback": traceback.format_exc(),
                "attributes": {},
            }
            if (
                response := hasattr(self.exception, "response")
                and self.exception.response
            ):
                self.code = str(response.status_code) or ""

                try:
                    response_text = self.exception.response.text
                    exception_dict["response"] = json.loads(response_text)
                except json.JSONDecodeError:
                    pass
            for attr in dir(self.exception):
                try:
                    if (
                        not attr.startswith("__")
                        and not callable(attribute := getattr(self.exception, attr))
                        and getattr(self.exception, attr)
                    ):
                        try:
                            exception_dict["attributes"][attr] = json.loads(
                                str(attribute)
                            )
                        except json.JSONDecodeError:
                            pass
                except Exception:
                    pass

        result = {
            "message": self.message,
            "code": self.code,
            "url": self.url,
            "payload": self.payload,
            "detail": self.detail,
        }
        if self.exception:
            result["exception"] = exception_dict
        return result


def singleton(cls):
    """Decorator to create a singleton class"""
    instances = {}

    def get_instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return get_instance
