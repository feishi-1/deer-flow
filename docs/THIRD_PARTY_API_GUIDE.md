# DeerFlow 第三方 API 接入指南

## 概述

DeerFlow 提供了完整的第三方 API 接入能力，允许外部应用通过 OpenAI 兼容的 API 接口访问 DeerFlow 的 AI 能力。本文档介绍如何申请 API Key、使用 API 以及管理租户配额。

## 目录

- [快速开始](#快速开始)
- [认证方式](#认证方式)
- [SSO 单点登录](#sso-单点登录)
- [API 端点](#api-端点)
- [速率限制与配额](#速率限制与配额)
- [错误处理](#错误处理)
- [管理面板](#管理面板)
- [SDK 示例](#sdk-示例)
- [最佳实践](#最佳实践)
- [故障排查](#故障排查)

---

## 快速开始

### 1. 获取 API Key

联系 DeerFlow 管理员创建租户账号，管理员将为您生成一个 API Key：

```
sk-a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8s9T0u1V2w
```

**⚠️ 重要提示：** API Key 仅在创建时显示一次，请妥善保管。

### 2. 发起第一个请求

使用 OpenAI SDK 或任何支持 OpenAI API 的客户端：

```python
from openai import OpenAI

client = OpenAI(
    api_key="sk-YOUR_API_KEY",
    base_url="https://your-deerflow-instance.com/v1"
)

response = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "user", "content": "Hello, DeerFlow!"}
    ]
)

print(response.choices[0].message.content)
```

---

## 认证方式

所有 `/v1/*` 端点使用 **Bearer Token** 认证：

```http
Authorization: Bearer sk-YOUR_API_KEY
```

### 认证流程

1. 客户端在 `Authorization` 头中携带 API Key
2. `ApiKeyAuthMiddleware` 验证 Key 格式和有效性
3. 查询数据库验证 Key 哈希
4. 检查租户状态（active/suspended/revoked）
5. 检查过期时间
6. 将租户上下文注入请求

### 错误响应

```json
{
  "error": {
    "message": "Invalid API key",
    "type": "invalid_api_key",
    "param": null,
    "code": "invalid_api_key"
  }
}
```

---

## SSO 单点登录

DeerFlow 支持通过 JWT 令牌实现单点登录（SSO），允许外部身份系统（如 Admin.NET）的用户无缝登录。

### 配置

在 `.env` 文件中添加以下环境变量：

```bash
# 启用 SSO
SSO_ENABLED=true
# SSO Provider JWT 签名密钥（HMAC-SHA256）
SSO_PROVIDER_JWT_SECRET=your-shared-secret-key

# 可选配置
SSO_PROVIDER_NAME=admin_net              # Provider 标识，默认 admin_net
SSO_PROVIDER_DISPLAY_NAME=Admin.NET 登录   # 登录页面显示名称
SSO_PROVIDER_ALGORITHM=HS256             # JWT 签名算法，默认 HS256
SSO_PROVIDER_AUTO_CREATE_USER=true       # 首次 SSO 登录自动创建用户
SSO_PROVIDER_DEFAULT_ROLE=user           # 自动创建用户的角色
SSO_PROVIDER_TOKEN_MAX_AGE=300           # Token 最大有效期（秒）
SSO_PROVIDER_ICON=building               # 登录页按钮图标
SSO_PROVIDER_LOGIN_URL=https://admin.example.com/#/login  # 外部登录页 URL
```

### 端点

#### 1. 获取 SSO Providers

**端点：** `GET /api/v1/auth/sso/providers`

**认证：** 无（公开端点）

**响应：**

```json
[
  {
    "name": "admin_net",
    "display_name": "Admin.NET 登录",
    "icon": "building",
    "login_url": "https://admin.example.com/#/login"
  }
]
```

**说明：** 前端登录页面调用此端点判断是否显示 SSO 登录按钮。

#### 2. SSO 登录（JWT 令牌验证）

**端点：** `GET /api/v1/auth/sso` 或 `POST /api/v1/auth/sso`

**认证：** 需提供有效的 HMAC-SHA256 JWT 令牌

**查询参数（GET）：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `token` | string | 是 | 由外部 IdP 签发的 JWT 令牌 |
| `next` | string | 否 | 登录成功后跳转的页面，默认 `/workspace` |
| `provider` | string | 否 | SSO Provider 名称，默认 `admin_net` |

**请求示例：**

```bash
# 带 JWT 令牌的 SSO 登录跳转
curl "https://your-deerflow-instance.com/api/v1/auth/sso?token=<JWT_TOKEN>&next=%2Fworkspace"
```

**响应：**

- **302 Redirect**: 重定向到 `next` 参数指定的页面
- **Set-Cookie**: 设置 `access_token` 会话 Cookie

**错误响应：**

| HTTP 状态码 | 错误代码 | 说明 |
|------------|---------|------|
| 401 | `token_expired` | JWT 已过期 |
| 401 | `invalid_signature` | JWT 签名无效 |
| 401 | `token_too_old` | Token 超过有效期（默认 300 秒） |
| 400 | `unknown_provider` | SSO Provider 未找到 |
| 403 | `user_not_registered` | 用户未注册且未启用自动创建 |

### JWT 令牌格式

外部 IdP（如 Admin.NET）需要签发包含以下声明的 HMAC-SHA256 JWT：

```json
{
  "UserId": "admin001",        // 外部用户 ID（必填）
  "Account": "zhangsan",        // 用户名/账号（必填）
  "RealName": "张三",           // 真实姓名
  "NickName": "小张",           // 昵称
  "OrgName": "XX 公司",         // 组织名称
  "OrgId": "org_001",          // 组织 ID
  "TenantId": "t_001",         // 租户 ID
  "AccountType": "1",          // 账号类型
  "LoginMode": "sso",          // 登录模式
  "iat": 1705300000,           // 签发时间
  "exp": 1705300300            // 过期时间
}
```

**声明映射关系：**

| JWT Claim | DeerFlow 字段 | 说明 |
|-----------|--------------|------|
| `UserId` | `oauth_id` | 外部用户唯一标识 |
| `Account` | `email` (本地部分) | 生成为 `{Account}@sso.deerflow.internal` |
| `RealName` / `NickName` | `display_name` | 优先使用 RealName，其次 NickName，最后 Account |
| `OrgName` | `org_name` | 用户所属组织 |
| `TenantId` | `external_tenant_id` | 外部租户 ID |

### Admin.NET 集成示例

Admin.NET 部署 SSO 时需要以下环境变量：

```bash
SSO_ENABLED=true
SSO_PROVIDER_JWT_SECRET=<与 DeerFlow 相同的密钥>
SSO_PROVIDER_NAME=admin_net
SSO_PROVIDER_DISPLAY_NAME=Admin.NET 登录
```

**登录流程：**

1. 用户在 Admin.NET 中登录
2. Admin.NET 生成包含用户信息的 HMAC-SHA256 JWT
3. 跳转到 `https://deerflow-instance.com/api/v1/auth/sso?token=<JWT>`
4. DeerFlow 验证令牌并创建/链接用户
5. 浏览器被重定向到 DeerFlow 工作区

**JWT 生成示例（Python）：**

```python
import jwt
import time

secret = "your-shared-secret-key"
payload = {
    "UserId": "admin001",
    "Account": "zhangsan",
    "RealName": "张三",
    "OrgName": "XX 公司",
    "iat": int(time.time()),
    "exp": int(time.time()) + 300,
}
token = jwt.encode(payload, secret, algorithm="HS256")
redirect_url = f"https://deerflow-instance.com/api/v1/auth/sso?token={token}"
```

---

## API 端点

### 1. Chat Completions (OpenAI 兼容)

**端点：** `POST /v1/chat/completions`

**标准 OpenAI 字段：**

```json
{
  "model": "gpt-4",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"}
  ],
  "stream": false,
  "temperature": 0.7,
  "max_tokens": 1000
}
```

**DeerFlow 扩展字段：**

```json
{
  "model": "gpt-4",
  "messages": [...],
  "stream": true,
  
  // DeerFlow 特有功能
  "thread_id": "thread-123",              // 多轮对话 ID
  "thinking_enabled": true,               // 启用思维链
  "reasoning_effort": "high",             // 推理强度
  "agent_name": "my-custom-agent",        // 自定义 Agent
  "subagent_enabled": true,               // 启用子 Agent
  "max_concurrent_subagents": 3,          // 最大并发子 Agent
  "skills": ["web_search", "code_exec"],  // 启用的技能
  "sandbox_enabled": true,                // 启用沙箱
  "is_plan_mode": false                   // 规划模式
}
```

**响应格式（非流式）：**

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1677652288,
  "model": "gpt-4",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! How can I help you today?"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 20,
    "total_tokens": 30
  }
}
```

**响应格式（流式）：**

```
data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1677652288,"model":"gpt-4","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1677652288,"model":"gpt-4","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1677652288,"model":"gpt-4","choices":[{"index":0,"delta":{"content":"!"},"finish_reason":null}]}

data: {"id":"chatcmpl-abc123","object":"chat.completion.chunk","created":1677652288,"model":"gpt-4","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

---

### 2. Models List

**端点：** `GET /v1/models`

**响应：**

```json
{
  "object": "list",
  "data": [
    {
      "id": "gpt-4",
      "object": "model",
      "created": 0,
      "owned_by": "deerflow"
    },
    {
      "id": "claude-3-5-sonnet",
      "object": "model",
      "created": 0,
      "owned_by": "deerflow"
    }
  ]
}
```

**说明：** 返回的模型列表根据租户的 `allowed_models` 配置过滤。

---

### 3. Memory Management

**端点：** `GET /v1/memory`

**查询参数：**
- `user_id` (可选): 用户 ID，默认为 "default"

**响应：**

```json
{
  "memory": {
    "version": "1.0",
    "lastUpdated": "2024-01-15T10:30:00Z",
    "user": {
      "workContext": {
        "summary": "Working on API integration",
        "updatedAt": "2024-01-15T10:30:00Z"
      },
      "personalContext": {
        "summary": "Prefers concise responses",
        "updatedAt": "2024-01-15T09:00:00Z"
      }
    },
    "facts": [
      {
        "id": "fact-1",
        "content": "User is a Python developer",
        "createdAt": "2024-01-10T08:00:00Z"
      }
    ]
  }
}
```

---

### 4. Skills List

**端点：** `GET /v1/skills`

**响应：**

```json
{
  "skills": [
    {
      "name": "web_search",
      "description": "Search the web for information",
      "enabled": true
    },
    {
      "name": "code_execution",
      "description": "Execute code in a sandbox",
      "enabled": true
    },
    {
      "name": "file_operations",
      "description": "Read and write files",
      "enabled": false
    }
  ]
}
```

---

### 5. Usage Statistics

**端点：** `GET /v1/usage`

**查询参数：**
- `start_date` (可选): ISO 8601 格式，如 `2024-01-01T00:00:00Z`
- `end_date` (可选): ISO 8601 格式

**响应：**

```json
{
  "usage": {
    "total_requests": 1250,
    "total_tokens": 450000,
    "total_prompt_tokens": 200000,
    "total_completion_tokens": 250000
  }
}
```

---

### 6. Files (文件上传)

文件上传 API 允许在对话中附加文件。上传的文件按租户和会话（thread_id）隔离存储。

#### 上传文件

**端点：** `POST /v1/files`

**请求格式：** `multipart/form-data`

**参数：**
- `file` (必填): 文件内容
- `purpose` (可选): 用途，默认 `"assistants"`
- `thread_id` (可选): 关联的会话 ID，不提供则自动生成

**请求示例：**

```bash
curl -X POST http://localhost:2026/v1/files \
  -H "Authorization: Bearer sk-YOUR_API_KEY" \
  -F "file=@report.csv" \
  -F "purpose=assistants" \
  -F "thread_id=my-conversation-123"
```

**响应：**

```json
{
  "id": "file-abc123def456789012ab",
  "object": "file",
  "bytes": 2048,
  "created_at": 1705312000,
  "filename": "report.csv",
  "purpose": "assistants",
  "thread_id": "my-conversation-123"
}
```

**限制：**
- 单文件最大 50MB
- 文件名不能以 `.` 开头

#### 列出文件

**端点：** `GET /v1/files`

**查询参数：**
- `thread_id` (可选): 按会话过滤
- `purpose` (可选): 按用途过滤

**响应：**

```json
{
  "object": "list",
  "data": [
    {
      "id": "file-abc123def456789012ab",
      "object": "file",
      "bytes": 2048,
      "created_at": 1705312000,
      "filename": "report.csv",
      "purpose": "assistants",
      "thread_id": "my-conversation-123"
    }
  ]
}
```

#### 获取文件信息

**端点：** `GET /v1/files/{file_id}`

**响应：**

```json
{
  "id": "file-abc123def456789012ab",
  "object": "file",
  "bytes": 2048,
  "created_at": 1705312000,
  "filename": "report.csv",
  "purpose": "assistants",
  "thread_id": "my-conversation-123"
}
```

#### 删除文件

**端点：** `DELETE /v1/files/{file_id}`

**响应：**

```json
{
  "id": "file-abc123def456789012ab",
  "object": "file",
  "deleted": true
}
```

#### 在对话中引用文件

上传文件后，可以通过 `file_ids` 字段在 `/v1/chat/completions` 的消息中引用：

```json
{
  "model": "gpt-4",
  "messages": [
    {
      "role": "user",
      "content": "请分析这个数据文件",
      "file_ids": ["file-abc123def456789012ab"]
    }
  ]
}
```

**文件处理规则：**
- **文本文件**（.txt, .py, .json, .md, .csv, .yaml 等）：内容自动内联到对话上下文
- **二进制文件**（.pdf, .png, .zip 等）：以文件名和大小引用传递给模型

---

## 速率限制与配额

### 速率限制

每个租户有两个维度的速率限制：

1. **RPM (Requests Per Minute)**: 每分钟最大请求数
2. **TPM (Tokens Per Minute)**: 每分钟最大 Token 数

**响应头：**

```http
X-RateLimit-Limit-Requests: 100
X-RateLimit-Remaining-Requests: 95
X-RateLimit-Limit-Tokens: 200000
X-RateLimit-Remaining-Tokens: 185000
```

**超限响应（429）：**

```json
{
  "error": {
    "message": "Rate limit exceeded: 100 requests per minute",
    "type": "rate_limit_exceeded",
    "param": null,
    "code": "rate_limit_exceeded"
  }
}
```

**响应头：**

```http
Retry-After: 30
```

### 月度配额

每个租户可设置月度配额：

1. **Monthly Tokens**: 每月最大 Token 数
2. **Monthly Requests**: 每月最大请求数

配额在每月 1 号自动重置。

**超限响应（429）：**

```json
{
  "error": {
    "message": "Monthly token quota exceeded: 1000000 tokens/month",
    "type": "quota_exceeded",
    "param": null,
    "code": "quota_exceeded"
  }
}
```

---

## 错误处理

### 错误格式

所有错误遵循 OpenAI 格式：

```json
{
  "error": {
    "message": "Error description",
    "type": "error_type",
    "param": null,
    "code": "error_code"
  }
}
```

### 常见错误码

| HTTP 状态码 | 错误类型 | 说明 |
|------------|---------|------|
| 401 | `invalid_api_key` | API Key 无效或已过期 |
| 403 | `api_key_disabled` | API Key 已被暂停 |
| 403 | `api_key_expired` | API Key 已过期 |
| 403 | `model_not_allowed` | 模型不在允许列表中 |
| 429 | `rate_limit_exceeded` | 超过速率限制 |
| 429 | `quota_exceeded` | 超过月度配额 |
| 500 | `internal_error` | 服务器内部错误 |
| 503 | `service_unavailable` | 服务暂时不可用 |

---

## 管理面板

### 管理员端点

**前提条件：** 需要管理员权限（cookie-based 认证）

#### 1. 创建租户

**端点：** `POST /api/admin/tenants`

**请求体：**

```json
{
  "name": "Acme Corp",
  "description": "Acme Corporation API Access",
  "rate_limit_rpm": 100,
  "rate_limit_tpm": 200000,
  "quota_monthly_tokens": 1000000,
  "quota_monthly_requests": 50000,
  "max_concurrent_runs": 5,
  "allowed_models": ["gpt-4", "claude-3-5-sonnet"],
  "expires_at": "2025-12-31T23:59:59Z"
}
```

**响应：**

```json
{
  "tenant": {
    "id": "tenant-abc123",
    "name": "Acme Corp",
    "status": "active",
    "api_key_prefix": "sk-a1B2c3",
    "rate_limit_rpm": 100,
    "rate_limit_tpm": 200000,
    "created_at": "2024-01-15T10:00:00Z"
  },
  "api_key": "sk-a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8s9T0u1V2w",
  "warning": "Save this API key now. It will not be shown again."
}
```

#### 2. 列出所有租户

**端点：** `GET /api/admin/tenants`

**查询参数：**
- `status` (可选): `active`, `suspended`, `revoked`
- `limit` (可选): 默认 100
- `offset` (可选): 默认 0

**响应：**

```json
{
  "tenants": [
    {
      "id": "tenant-abc123",
      "name": "Acme Corp",
      "status": "active",
      "api_key_prefix": "sk-a1B2c3",
      "rate_limit_rpm": 100,
      "rate_limit_tpm": 200000,
      "created_at": "2024-01-15T10:00:00Z"
    }
  ],
  "total": 1
}
```

#### 3. 更新租户配置

**端点：** `PATCH /api/admin/tenants/{tenant_id}`

**请求体：**

```json
{
  "rate_limit_rpm": 200,
  "rate_limit_tpm": 400000,
  "quota_monthly_tokens": 2000000
}
```

#### 4. 轮换 API Key

**端点：** `POST /api/admin/tenants/{tenant_id}/rotate`

**响应：**

```json
{
  "api_key": "sk-NEW_KEY_HERE",
  "api_key_prefix": "sk-x9Y8z7",
  "warning": "Save this API key now. It will not be shown again."
}
```

**⚠️ 注意：** 旧 Key 立即失效。

#### 5. 暂停/恢复租户

**暂停：** `POST /api/admin/tenants/{tenant_id}/suspend`

**恢复：** `POST /api/admin/tenants/{tenant_id}/resume`

#### 6. 删除租户

**端点：** `DELETE /api/admin/tenants/{tenant_id}`

**⚠️ 警告：** 此操作不可逆，将删除所有相关数据。

#### 7. 查看租户用量

**端点：** `GET /api/admin/usage/tenants/{tenant_id}`

**查询参数：**
- `start_date` (可选): ISO 8601 格式
- `end_date` (可选): ISO 8601 格式
- `limit` (可选): 默认 1000

**响应：**

```json
{
  "tenant_id": "tenant-abc123",
  "stats": {
    "total_requests": 1250,
    "total_tokens": 450000,
    "total_prompt_tokens": 200000,
    "total_completion_tokens": 250000
  },
  "records": [
    {
      "id": 1,
      "created_at": "2024-01-15T10:30:00Z",
      "model_name": "gpt-4",
      "total_tokens": 150,
      "endpoint": "/v1/chat/completions",
      "status_code": 200
    }
  ],
  "count": 1250
}
```

#### 8. 查看配额历史

**端点：** `GET /api/admin/usage/quota/{tenant_id}`

**查询参数：**
- `limit` (可选): 默认 12（最近 12 个月）

**响应：**

```json
{
  "tenant_id": "tenant-abc123",
  "periods": [
    {
      "id": 1,
      "period_start": "2024-01-01T00:00:00Z",
      "period_end": "2024-02-01T00:00:00Z",
      "tokens_used": 450000,
      "requests_used": 1250
    },
    {
      "id": 2,
      "period_start": "2024-02-01T00:00:00Z",
      "period_end": "2024-03-01T00:00:00Z",
      "tokens_used": 380000,
      "requests_used": 980
    }
  ]
}
```

#### 9. 全局用量汇总

**端点：** `GET /api/admin/usage/summary`

**查询参数：**
- `start_date` (可选)
- `end_date` (可选)

**响应：**

```json
{
  "summary": [
    {
      "tenant_id": "tenant-abc123",
      "tenant_name": "Acme Corp",
      "status": "active",
      "stats": {
        "total_requests": 1250,
        "total_tokens": 450000,
        "total_prompt_tokens": 200000,
        "total_completion_tokens": 250000
      }
    }
  ]
}
```

---

## SDK 示例

### Python (OpenAI SDK)

```python
from openai import OpenAI

client = OpenAI(
    api_key="sk-YOUR_API_KEY",
    base_url="https://your-deerflow-instance.com/v1"
)

# 基础对话
response = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "user", "content": "Hello!"}
    ]
)
print(response.choices[0].message.content)

# 流式响应
stream = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "user", "content": "Tell me a story"}
    ],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")

# 使用 DeerFlow 扩展功能
response = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "user", "content": "Search for latest AI news"}
    ],
    extra_body={
        "thinking_enabled": True,
        "skills": ["web_search"],
        "thread_id": "my-conversation-123"
    }
)

# 文件上传并在对话中引用
file = client.files.create(
    file=open("data.csv", "rb"),
    purpose="assistants"
)
print(f"Uploaded: {file.id}")

response = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {
            "role": "user",
            "content": "分析这个 CSV 文件的数据",
            "file_ids": [file.id]
        }
    ],
    extra_body={"thread_id": file.thread_id}
)
print(response.choices[0].message.content)
```

### JavaScript/TypeScript

```typescript
import OpenAI from 'openai';

const client = new OpenAI({
  apiKey: 'sk-YOUR_API_KEY',
  baseURL: 'https://your-deerflow-instance.com/v1',
});

// 基础对话
const response = await client.chat.completions.create({
  model: 'gpt-4',
  messages: [
    { role: 'user', content: 'Hello!' }
  ],
});
console.log(response.choices[0].message.content);

// 流式响应
const stream = await client.chat.completions.create({
  model: 'gpt-4',
  messages: [
    { role: 'user', content: 'Tell me a story' }
  ],
  stream: true,
});

for await (const chunk of stream) {
  process.stdout.write(chunk.choices[0]?.delta?.content || '');
}

// 使用 DeerFlow 扩展功能
const response = await client.chat.completions.create({
  model: 'gpt-4',
  messages: [
    { role: 'user', content: 'Search for latest AI news' }
  ],
  thinking_enabled: true,
  skills: ['web_search'],
  thread_id: 'my-conversation-123',
} as any); // TypeScript 需要类型断言

// 文件上传并在对话中引用
const file = await client.files.create({
  file: fs.createReadStream('data.csv'),
  purpose: 'assistants',
});
console.log(`Uploaded: ${file.id}`);

const fileResponse = await client.chat.completions.create({
  model: 'gpt-4',
  messages: [
    {
      role: 'user',
      content: '分析这个 CSV 文件',
      file_ids: [file.id],
    }
  ],
  thread_id: file.thread_id,
} as any);
```

### cURL

```bash
# 基础请求
curl https://your-deerflow-instance.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-YOUR_API_KEY" \
  -d '{
    "model": "gpt-4",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ]
  }'

# 流式请求
curl https://your-deerflow-instance.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-YOUR_API_KEY" \
  -d '{
    "model": "gpt-4",
    "messages": [
      {"role": "user", "content": "Tell me a story"}
    ],
    "stream": true
  }'

# 使用 DeerFlow 扩展功能
curl https://your-deerflow-instance.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-YOUR_API_KEY" \
  -d '{
    "model": "gpt-4",
    "messages": [
      {"role": "user", "content": "Search for latest AI news"}
    ],
    "thinking_enabled": true,
    "skills": ["web_search"],
    "thread_id": "my-conversation-123"
  }'

# 上传文件
curl -X POST https://your-deerflow-instance.com/v1/files \
  -H "Authorization: Bearer sk-YOUR_API_KEY" \
  -F "file=@data.csv" \
  -F "purpose=assistants" \
  -F "thread_id=my-conversation-123"

# 在对话中引用文件
curl https://your-deerflow-instance.com/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-YOUR_API_KEY" \
  -d '{
    "model": "gpt-4",
    "messages": [
      {
        "role": "user",
        "content": "分析这个数据文件",
        "file_ids": ["file-abc123def456789012ab"]
      }
    ],
    "thread_id": "my-conversation-123"
  }'

# 列出文件
curl https://your-deerflow-instance.com/v1/files \
  -H "Authorization: Bearer sk-YOUR_API_KEY"

# 删除文件
curl -X DELETE https://your-deerflow-instance.com/v1/files/file-abc123def456789012ab \
  -H "Authorization: Bearer sk-YOUR_API_KEY"
```

---

## 最佳实践

### 1. 安全性

- ✅ **永远不要**在客户端代码中硬编码 API Key
- ✅ 使用环境变量存储 API Key
- ✅ 定期轮换 API Key
- ✅ 为不同环境使用不同的 API Key
- ✅ 监控异常使用模式

### 2. 错误处理

```python
from openai import OpenAI, APIError, RateLimitError

client = OpenAI(
    api_key="sk-YOUR_API_KEY",
    base_url="https://your-deerflow-instance.com/v1"
)

try:
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello!"}]
    )
except RateLimitError as e:
    # 处理速率限制
    retry_after = e.response.headers.get('Retry-After', 60)
    print(f"Rate limited. Retry after {retry_after} seconds")
except APIError as e:
    # 处理其他 API 错误
    print(f"API error: {e.message}")
```

### 3. 多轮对话

使用 `thread_id` 维护对话上下文：

```python
thread_id = "user-123-session-456"

# 第一轮
response1 = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "My name is Alice"}],
    extra_body={"thread_id": thread_id}
)

# 第二轮（AI 会记住 Alice）
response2 = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "What's my name?"}],
    extra_body={"thread_id": thread_id}
)
```

### 4. 监控用量

定期检查用量统计：

```python
import requests

response = requests.get(
    "https://your-deerflow-instance.com/v1/usage",
    headers={"Authorization": "Bearer sk-YOUR_API_KEY"}
)

usage = response.json()["usage"]
print(f"Total tokens used: {usage['total_tokens']}")
print(f"Total requests: {usage['total_requests']}")
```

---

## 故障排查

### 问题：401 Unauthorized

**可能原因：**
- API Key 格式错误
- API Key 已过期
- API Key 已被撤销

**解决方案：**
1. 检查 API Key 格式（应为 `sk-` 开头）
2. 联系管理员确认 Key 状态
3. 如需要，请求轮换 Key

### 问题：429 Rate Limit Exceeded

**可能原因：**
- 超过 RPM 限制
- 超过 TPM 限制
- 超过月度配额

**解决方案：**
1. 检查响应头中的 `Retry-After`
2. 实现指数退避重试
3. 联系管理员提升限额

### 问题：403 Model Not Allowed

**可能原因：**
- 请求的模型不在 `allowed_models` 列表中

**解决方案：**
1. 使用 `GET /v1/models` 查看可用模型
2. 联系管理员添加所需模型

---

## 支持与反馈

如有问题或建议，请联系：

- **技术支持：** support@your-company.com
- **文档反馈：** docs@your-company.com
- **GitHub Issues：** https://github.com/your-org/deerflow/issues

---

## 更新日志

### v1.0.0 (2024-01-15)

- ✨ 初始版本发布
- ✨ OpenAI 兼容的 Chat Completions API
- ✨ 速率限制和配额管理
- ✨ 多租户隔离
- ✨ 管理面板 API
- ✨ DeerFlow 扩展功能（思维链、技能、沙箱等）

### v1.1.0 (2024-01-20)

- ✨ 新增 Files API（POST/GET/DELETE /v1/files）
- ✨ 支持在 chat completions 消息中通过 file_ids 引用上传文件
- ✨ 文本文件自动内联到对话上下文
- ✨ 文件按租户和会话隔离存储

### v1.2.0 (2024-05-26)

- ✨ 新增 SSO 单点登录支持
- ✨ 支持 HMAC-SHA256 JWT 令牌验证
- ✨ 自动创建 SSO 用户并映射外部身份属性
- ✨ 可配置的 SSO Provider 显示名称和图标
- ✨ 防重放攻击的 Token 有效期限制

---

**文档版本：** v1.2.0  
**最后更新：** 2024-05-26
