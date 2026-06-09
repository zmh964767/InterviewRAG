# 后端安全规范

> InterviewRAG 后端安全防护标准

---

## 路径遍历防护

**规则**：任何接受用户输入构造文件路径的端点，必须校验输入格式。

```python
# ❌ 错误：用户输入直接进路径
file_path = RESULTS_DIR / "history" / f"{ts}.json"

# ✅ 正确：正则校验后才拼路径
import re
_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}$")

if ts:
    if not _TS_RE.match(ts):
        raise HTTPException(status_code=400, detail="ts 参数格式无效")
    file_path = RESULTS_DIR / "history" / f"{ts}.json"
```

**已知危险输入**：`../../backend/.env`、`../../../etc/passwd`、`..%2F..%2F`（URL 编码）

---

## CORS 配置

**规则**：`allow_origins` 必须是显式 origin 列表，不用 `["*"]`。

```python
# ❌ 错误：任何网站可调用 API
CORSMiddleware(allow_origins=["*"], allow_credentials=True, ...)

# ✅ 正确：限制为前端实际域名
CORSMiddleware(
    allow_origins=["http://localhost:3000"],  # 生产用环境变量
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**生产环境**：用 `os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")` 配置。

---

## SSRF 防护（URL 导入）

**规则**：`ingest_url` 端点必须校验目标 URL。

```python
import ipaddress, socket
from urllib.parse import urlparse

def _is_safe_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    try:
        ip = ipaddress.ip_address(socket.gethostbyname(parsed.hostname))
        return ip.is_global  # 拒绝 127.x、10.x、192.168.x、169.254.x
    except (ValueError, socket.gaierror):
        return False
```

**危险地址**：`http://169.254.169.254/`（云元数据）、`http://127.0.0.1:8080/`（本地服务）

---

## 导入卫生

**规则**：所有 `import` 语句必须在模块顶层，不能在函数内部。

```python
# ❌ 错误：函数内 import（导致 NameError bug）
def stream_generator():
    except asyncio.CancelledError:  # NameError: 'asyncio' is not defined

# ✅ 正确：顶层 import
import asyncio

def stream_generator():
    except asyncio.CancelledError:  # 正常工作
```

**原因**：函数内 import 容易遗漏，特别是从其他文件复制代码时。顶层 import 让 linter 和 IDE 自动检查。

---

## 敏感数据处理

**规则**：
- API Key 只存在 `.env`，不 commit 到 git
- `.gitignore` 必须包含 `.env`
- 后端不返回内部路径、堆栈、SQL 语句给客户端

```python
# ✅ 错误信息不泄露内部细节
raise HTTPException(status_code=500, detail="服务器内部错误")

# ❌ 不要这样
raise HTTPException(status_code=500, detail=f"File not found: {file_path}")
```

---

## 并发安全

**规则**：不要把请求相关的数据存在实例属性上（单例服务会被并发覆盖）。

```python
# ❌ 错误：单例 RAGService 的实例属性被并发请求覆盖
class RAGService:
    def query_stream(self, question):
        self._last_sources = sources  # 并发时被覆盖
        yield chunk

# ✅ 正确：用包装类把数据挂到生成器对象上
class _StreamWithSources:
    def __init__(self, gen, sources):
        self._gen = gen
        self.sources = sources  # 每个请求独立
    async def __aiter__(self):
        async for chunk in self._gen:
            yield chunk
```

---

## 代码审查清单

- [ ] 用户输入构造文件路径时有正则/白名单校验
- [ ] CORS 不是 `["*"]`
- [ ] URL 导入有私有 IP 检查
- [ ] 所有 import 在模块顶层
- [ ] 单例服务无请求级状态存实例属性
- [ ] 错误信息不泄露内部路径/堆栈
