# mcp_info

MCP 使用探索

## 准备

环境要求

```sh
pip install mcp[cli] httpx
```

LLM 配置
- 如，使用 DeepSeek API
- 更新 .env 文件里的 API_KEY 



## 使用


### 服务调试


启动 server Web 端

```sh
mcp dev server.py
```

弹出 Web 地址 http://127.0.0.1:6274 


### 启动终端服务

执行命令

```sh
uv run client.py server.py
```


## 其他


