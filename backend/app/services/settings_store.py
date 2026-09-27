"""把用户在前端填的 LLM 配置写回 backend/.env。

只更新已有的键或追加到文件末尾，其余内容（含注释）原样保留。
``.env`` 已在 ``.gitignore`` 里，Key 不会进版本库。
"""

from __future__ import annotations

from app.config import ENV_FILE, get_logger

log = get_logger(__name__)


def update_env_file(updates: dict[str, str]) -> list[str]:
    """返回实际写入的键列表（值为 None 的键跳过）。"""
    payload = {key: value for key, value in updates.items() if value is not None}
    if not payload:
        return []

    lines: list[str] = []
    if ENV_FILE.exists():
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines()

    remaining = dict(payload)
    output: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in remaining:
                output.append(f"{key}={remaining.pop(key)}")
                continue
        output.append(line)

    for key, value in remaining.items():
        output.append(f"{key}={value}")

    ENV_FILE.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    log.info("已写入 %s：%s", ENV_FILE.name, ", ".join(payload))
    return list(payload)
