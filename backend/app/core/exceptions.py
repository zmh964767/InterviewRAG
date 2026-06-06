"""自定义异常类"""


class AppError(Exception):
    """应用基础异常"""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppError):
    """资源未找到"""

    def __init__(self, resource: str, resource_id: str):
        super().__init__(
            message=f"{resource} '{resource_id}' 未找到",
            status_code=404,
        )


class ValidationError(AppError):
    """参数校验失败"""

    def __init__(self, detail: str):
        super().__init__(message=detail, status_code=400)


class ExternalServiceError(AppError):
    """外部服务调用失败"""

    def __init__(self, service: str, detail: str):
        super().__init__(
            message=f"{service} 调用失败: {detail}",
            status_code=502,
        )


class IngestError(AppError):
    """数据导入失败"""

    def __init__(self, detail: str):
        super().__init__(message=f"数据导入失败: {detail}", status_code=422)
