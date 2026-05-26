# Admin.NET → DeerFlow SSO 集成指南

## 概览

将 Admin.NET 作为 DeerFlow 的外部身份提供者 (IdP)，通过 JWT 令牌实现单点登录。

### 完整流程

```
                            ┌──────────────────────┐
  ① 点击 SSO 按钮           │                      │
       ─────────────►       │     DeerFlow          │
                            │  (192.168.100.20      │
                            │   :2026)              │
                            └──────┬───────────────┘
                                   │
                   ② 重定向到 Admin.NET + sso_callback
              http://192.168.100.138:7799/index.html
              #/login?sso_callback={deerflow_sso_endpoint}

                                   ▼
                            ┌──────────────────────┐
                            │     Admin.NET         │
                            │  (192.168.100.138     │
                            │   :7799)              │
                            │                      │
                            │  ③ 用户输入账号密码    │
                            │  ④ 登录成功            │
                            │  ⑤ 调用用户信息 API    │
                            │  ⑥ 生成 HMAC-SHA256   │
                            │     JWT (用户信息)    │
                            └──────┬───────────────┘
                                   │
                   ⑦ 重定向到 DeerFlow SSO 端点
             {sso_callback}?token=<signed_jwt>

                                   ▼
                            ┌──────────────────────┐
                            │     DeerFlow          │
                            │  ⑧ 验证 JWT           │
                            │  ⑨ 创建/链接用户      │
                            │  ⑩ 设置 session cookie │
                            │  ⑪ 进入工作区         │
                            └──────────────────────┘
```

---

## 一、DeerFlow 侧配置

### 1.1 根目录 `.env`

```bash
# ── SSO Configuration ──────────────────────────────────────────────────────────
SSO_ENABLED=true
SSO_PROVIDER_JWT_SECRET=3c1cbc3f546eda35168c3aa3cb91780fbe703f0996c6d123ea96dc85c70bbc0a
SSO_PROVIDER_NAME=admin_net
SSO_PROVIDER_DISPLAY_NAME=Admin.NET 登录
SSO_PROVIDER_ALGORITHM=HS256
SSO_PROVIDER_AUTO_CREATE_USER=true
SSO_PROVIDER_DEFAULT_ROLE=user
SSO_PROVIDER_TOKEN_MAX_AGE=300
SSO_PROVIDER_ICON=building
SSO_PROVIDER_LOGIN_URL=http://192.168.100.138:7799/index.html#/login
```

> **注意**：`SSO_PROVIDER_LOGIN_URL` 使用 Admin.NET 的 hash 路由格式。DeerFlow 前端会自动拼接 `?sso_callback=...` 到该 URL 后面，形成最终地址：
> ```
> http://192.168.100.138:7799/index.html#/login?sso_callback=...
> ```

### 1.2 前端 `frontend/.env`（SSO 按钮展示）

```env
NEXT_PUBLIC_SSO_ENABLED=true
NEXT_PUBLIC_SSO_PROVIDER_NAME=admin_net
NEXT_PUBLIC_SSO_PROVIDER_DISPLAY_NAME=Admin.NET 登录
NEXT_PUBLIC_SSO_PROVIDER_ICON=building
NEXT_PUBLIC_SSO_PROVIDER_LOGIN_URL=http://192.168.100.138:7799/index.html#/login
```

> `NEXT_PUBLIC_*` 变量在 Next.js 构建时内联到客户端 JS。修改后需 `make build` 重建前端镜像。

### 1.3 前端 `frontend/next.config.js`（API 代理）

```js
// 在 rewrites() 函数开头添加（所有 if 块之前）
rewrites.push({
  source: "/sso-config",
  destination: "http://gateway:8001/api/v1/auth/sso/providers",
});
```

> 作用：浏览器请求 `/sso-config` → Next.js 内部代理到网关的 `/api/v1/auth/sso/providers`，绕过 Docker Desktop WSL2 代理的拦截。

### 1.4 JWT Claims 映射

| Admin.NET 字段 → | JWT Claim  | DeerFlow 目标字段                  |
|-------------------|------------|-----------------------------------|
| `id`              | `UserId`   | `oauth_id` (外部用户标识)           |
| `account`         | `Account`  | `email` → `{Account}@sso.deerflow.internal` |
| `realName`        | `RealName` | `display_name`                    |
| `orgName`         | `OrgName`  | `org_name`                        |
| `tenantId`        | `TenantId` | `external_tenant_id`              |

---

## 二、Admin.NET 侧修改

### 2.1 代码分析

Admin.NET 前端采用 **Vue3 + Vue Router (hash 模式)**，关键文件：

| 文件 | 路径 |
|------|------|
| 登录页 | `Web/src/views/login/component/account.vue` |
| 路由控制 | `Web/src/router/backEnd.ts` (`initBackEndControlRoutes`) |
| HTTP 工具 | `Web/src/utils/axios-utils.ts` |
| 用户 API | `Web/src/api-services/api.ts` (`SysAuthApi`) |

**关键代码段落（`account.vue`）：**

- **OAuth token 处理**（`onMounted`，约 L150）：
  ```typescript
  const accessToken = route.query.token;
  if (accessToken) await saveTokenAndInitRoutes(accessToken);
  ```
  已有 OAuth token 接收逻辑，DeerFlow SSO 不直接复用它（因为我们需要先生成 token 再跳转）。

- **登录后跳转**（`signInSuccess`）：
  ```typescript
  if (route.query?.redirect) {
    router.push({
      path: <string>route.query?.redirect,
      query: ...,
    });
  } else {
    router.push('/');
  }
  ```
  读取 `redirect` 查询参数进行跳转，这是 SSO 回调的插入点。

- **Vue Router 路由解析**：Admin.NET 使用 hash 模式，URL 各部分的含义：
  ```
  http://192.168.100.138:7799/index.html#/login?sso_callback=...
  ├── origin ──┤├─ path ─┤├── hash ────────────────┤
                                       └── Vue Router query params
  ```
  `sso_callback` 放在 hash 内部（`#/login?` 之后），Vue Router 会自动解析为 `route.query.sso_callback`。

### 2.2 准备工作

```bash
cd Admin.NET/Web/
pnpm add jose
```

### 2.3 修改 1：添加环境变量

**文件：`Web/.env`**（以及 `Web/.env.development`、`Web/.env.production`）

```env
# DeerFlow SSO 集成
VITE_DEERFLOW_SSO_ENABLED = true
VITE_DEERFLOW_SSO_SECRET = 3c1cbc3f546eda35168c3aa3cb91780fbe703f0996c6d123ea96dc85c70bbc0a
```

### 2.4 修改 2：创建 SSO 工具函数

**新建文件：`Web/src/utils/deerflow-sso.ts`**

```typescript
import { SignJWT } from 'jose';

interface SsoUserInfo {
  userId: number;
  account: string;
  realName: string;
  orgName: string;
  tenantId?: number;
}

/**
 * 生成 DeerFlow SSO 所需的 HMAC-SHA256 JWT
 */
export async function generateDeerFlowSsoToken(user: SsoUserInfo): Promise<string> {
  const secretValue = (window as any).__env__?.VITE_DEERFLOW_SSO_SECRET;
  if (!secretValue) throw new Error('VITE_DEERFLOW_SSO_SECRET 未配置');

  const secret = new TextEncoder().encode(secretValue);
  const now = Math.floor(Date.now() / 1000);

  return new SignJWT({
    UserId: String(user.userId),
    Account: user.account,
    RealName: user.realName || '',
    NickName: '',
    OrgName: user.orgName || '',
    OrgId: '',
    TenantId: String(user.tenantId || ''),
    AccountType: '1',
    LoginMode: 'sso',
  })
    .setProtectedHeader({ alg: 'HS256' })
    .setIssuedAt(now)
    .setExpirationTime('5m')
    .sign(secret);
}
```

### 2.5 修改 3：登录页面增加 SSO 回调处理

**文件：`Web/src/views/login/component/account.vue`**

#### 3.1 添加 imports

在现有 `<script lang="ts" setup>` 的 import 区域末尾添加：

```typescript
import { generateDeerFlowSsoToken } from '/@/utils/deerflow-sso';
```

> `getAPI`、`SysAuthApi` 已在原文件中 import，无需重复添加。

#### 3.2 添加 SSO 回调处理函数

在 `signInSuccess` 函数**上方**添加：

```typescript
// DeerFlow SSO 回调处理
const handleDeerFlowSsoRedirect = async () => {
  try {
    // 获取当前登录用户的详细信息（此时 token 已存入 Session）
    const res = await getAPI(SysAuthApi).apiSysAuthUserInfoGet();
    const user = res.data.result;

    if (!user?.id || !user?.account) {
      ElMessage.error('SSO登录失败：无法获取用户信息');
      return;
    }

    // 生成 DeerFlow SSO JWT
    const token = await generateDeerFlowSsoToken({
      userId: user.id,
      account: user.account,
      realName: user.realName || '',
      orgName: user.orgName || '',
      tenantId: user.currentTenantId,
    });

    // 拼接重定向 URL
    const callbackUrl = route.query.sso_callback as string;
    const separator = callbackUrl.includes('?') ? '&' : '?';
    window.location.href = `${callbackUrl}${separator}token=${encodeURIComponent(token)}`;
  } catch (error) {
    console.error('DeerFlow SSO redirect failed:', error);
    ElMessage.error('SSO登录失败，请稍后重试');
  }
};
```

#### 3.3 修改 `signInSuccess` 函数

```typescript
const signInSuccess = (isNoPower: boolean | undefined) => {
  if (isNoPower) {
    ElMessage.warning('抱歉，您没有登录权限');
    clearTokens();
  } else if (route.query?.sso_callback) {
    // DeerFlow SSO 回调 → 生成 JWT 并重定向回 DeerFlow
    handleDeerFlowSsoRedirect();
  } else {
    // 正常登录流程（保持不变）
    let currentTimeInfo = currentTime.value;
    if (route.query?.redirect) {
      router.push({
        path: <string>route.query?.redirect,
        query: Object.keys(<string>route.query?.params).length > 0 ? JSON.parse(<string>route.query?.params) : '',
      });
    } else {
      router.push('/');
    }
    const signInText = '欢迎回来！';
    ElMessage.success(`${currentTimeInfo}，${signInText}`);
    NextLoading.start();
  }
};
```

**关键点**：`route.query.sso_callback` 是 Vue Router 从 hash URL query 解析出来的参数，格式为：
```
http://192.168.100.20:2026/api/v1/auth/sso?provider=admin_net&next=%2Fworkspace
```

Admin.NET 登录成功后在此 URL 尾部追加 `?token=<jwt>`（或 `&token=<jwt>`），然后 `window.location.href` 跳转。

---

## 三、端到端测试

### 3.1 验证 SSO API 端点

```bash
# DeerFlow 侧（确认 SSO 配置生效）
curl http://192.168.100.20:2026/sso-config
# 预期返回：
# [{"name":"admin_net","display_name":"Admin.NET 登录","icon":"building","login_url":"http://..."}]
```

### 3.2 浏览器测试

1. 访问 DeerFlow 登录页：`http://192.168.100.20:2026/login`
2. 硬刷新（`Ctrl+Shift+R`）确保加载最新 JS
3. 点击 **"Admin.NET 登录"** 按钮
4. 浏览器跳转到 Admin.NET 登录页（URL 中携带 `sso_callback`）
5. 在 Admin.NET 输入账号密码登录
6. 自动跳回 DeerFlow 工作区

### 3.3 验证数据库

```sql
SELECT email, display_name, org_name, oauth_provider, oauth_id
FROM users
WHERE oauth_provider = 'admin_net';
```

预期结果：

```
email: superadmin@sso.deerflow.internal
display_name: 超级管理员
org_name: Admin.NET
oauth_provider: admin_net
oauth_id: 1
```

---

## 四、URL 流转详解

### 4.1 完整 URL 链

| 步骤 | URL | 说明 |
|------|-----|------|
| ① 点击 SSO 按钮 | DeerFlow 构造跳转 URL | `login_url + "?sso_callback=" + callback` |
| ② 跳转到 Admin.NET | `http://192.168.100.138:7799/index.html#/login?sso_callback=http://192.168.100.20:2026/api/v1/auth/sso?provider=admin_net&next=%2Fworkspace` | Admin.NET 加载登录页，Vue Router 解析 `sso_callback` |
| ③ 登录成功后 | Admin.NET 调用 `apiSysAuthUserInfoGet()` 获取用户信息 | 生成 JWT |
| ④ 重定向回 DeerFlow | `http://192.168.100.20:2026/api/v1/auth/sso?provider=admin_net&next=%2Fworkspace&token=<jwt>` | DeerFlow 验证 JWT → 创建/链接用户 → 设置 session → 302 到 `/workspace` |
| ⑤ 进入工作区 | `http://192.168.100.20:2026/workspace` | 用户已登录 |

### 4.2 Admin.NET Hash 路由说明

Admin.NET 使用 Vue Router hash 模式，URL 格式为：
```
http://{host}:{port}/index.html#/{route}?{query}
```

- `#/login` 是 Vue Router 的 hash 路由
- `?sso_callback=...` 是 hash 路由的 query 参数
- Vue Router 通过 `route.query.sso_callback` 访问

**DeerFlow 侧的 login_url 只需配置到 `#/login`**，前端会自动拼接 query 参数。

---

## 五、故障排查

| 现象 | 可能原因 | 解决 |
|------|---------|------|
| DeerFlow 登录页无 SSO 按钮 | 前端容器未使用最新镜像 | `make build` 重建，硬刷新浏览器 |
| | `.env` 中的 `#` 被 Docker env_file 截断 | 使用 `frontend/.env` 中的 `NEXT_PUBLIC_*` 变量（构建时内联） |
| Admin.NET 收到 `sso_callback` 但未触发 | URL hash 格式不对 | 确认 `login_url` 以 `#/login` 结尾 |
| Admin.NET 跳转后 DeerFlow 返回 401 | JWT 签名密钥不一致 | 检查 `VITE_DEERFLOW_SSO_SECRET` = `SSO_PROVIDER_JWT_SECRET` |
| "Token too old" 错误 | JWT 超时 | 增大 `SSO_PROVIDER_TOKEN_MAX_AGE`，确保时钟同步 |
| "Failed to decode token" | JWT 格式错误 | 确认使用 HS256，claims 字段名大小写正确 |
| "SSO登录失败：无法获取用户信息" | Admin.NET token 未正确存储 | 确认 `saveTokenAndInitRoutes` 已执行 |

---

## 六、配置速查表

| 配置项 | 所在文件 | 值 |
|--------|---------|-----|
| DeerFlow 共享密钥 | 根目录 `.env` | `SSO_PROVIDER_JWT_SECRET=3c1c...` |
| Admin.NET 地址 | 根目录 `.env` | `SSO_PROVIDER_LOGIN_URL=http://192.168.100.138:7799/index.html#/login` |
| DeerFlow SSO 端点 | Admin.NET `account.vue` | `/api/v1/auth/sso?provider=admin_net&next=%2Fworkspace` |
| Admin.NET SSO 密钥 | Admin.NET `Web/.env` | `VITE_DEERFLOW_SSO_SECRET=3c1c...` |
| 前端 SSO 展示 | DeerFlow `frontend/.env` | `NEXT_PUBLIC_SSO_*` |
| API 代理 | DeerFlow `frontend/next.config.js` | `/sso-config` → `gateway:8001/api/v1/auth/sso/providers` |
