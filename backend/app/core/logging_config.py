"""structlog 日志配置

配置 structlog processor chain，包装 stdlib logging。
所有应用日志输出为 JSON 格式，自动注入 request_id 等上下文字段。
"""

import logging
import structlog


def setup_logging(json_output: bool = True):
    """配置 structlog processor chain。

    Args:
        json_output: True 输出 JSON（生产环境），False 输出彩色控制台（开发环境）。
                     也可通过环境变量 STRUCTLOG_DEV=1 切换。
    """
    # ─── structlog native logger 配置 ───────────────────────────────────
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,       # 注入 request_id 等上下文
            structlog.stdlib.add_log_level,                # level 字段
            structlog.stdlib.add_logger_name,              # logger 字段
            structlog.processors.TimeStamper(fmt="iso"),   # ISO8601 时间戳
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,          # exc_info → traceback 字段
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # ─── 格式选择 ─────────────────────────────────────────────────────
    if json_output:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    # ─── stdlib root handler 替换 ─────────────────────────────────────
    # foreign_pre_chain 处理 stdlib logger（23 个未改造文件）的输出：
    # 自动添加 level / logger_name / timestamp，然后交给 JSONRenderer
    handler = logging.StreamHandler()
    handler.setFormatter(structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
        ],
    ))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
