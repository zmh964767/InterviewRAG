# 错误处理

> InterviewRAG 后端错误处理规范

---

## 自定义异常类

```python
# app/core/exceptions.py

class AppError(Exception):
    """应用基础异常"""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)

class NotFoundError(AppError):
    """资源未找到"""
    def __init__(self, resource: str, id: str):
        super().__init__(f"{resource} '{id}' 未找到", status_code=404)

class ValidationError(AppError):
    """参数校验失败"""
    def __init__(self, detail: str):
        super().__init__(detail, status_code=400)

class ExternalServiceError(AppError):
    """外部服务调用失败（智谱 API、ChromaDB 等）"""
    def __init__(self, service: str, detail: str):
        super().__init__(f"{service} 调用失败: {detail}", status_code=502)
```

---

## API 错误响应格式

```json
{
  "detail": "错误描述信息",
  "status_code": 400
}
```

---

## 全局异常处理器

```python
# app/main.py

from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "status_code": exc.status_code}
    )

@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    # 记录日志（不暴露内部错误给用户）
    logger.error(f"未处理异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误", "status_code": 500}
    )
```

---

## 规则

- 业务异常用 `AppError` 子类，不用原生 `Exception`
- 外部服务调用必须 try-catch，包装为 `ExternalServiceError`
- 500 错误不暴露堆栈信息给用户
- 所有异常必须记录日志

---

## 禁止事项

- ❌ 向用户暴露 Python 堆栈信息
- ❌ 用 HTTPException 直接抛（用自定义异常）
- ❌ 吞掉异常不记录日志
- ❌ 在 except 里用 bare `except:`
