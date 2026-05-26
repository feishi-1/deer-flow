# Admin.NET → DeerFlow SSO 集成指南

## 概览

将 Admin.NET 作为 DeerFlow 的外部身份提供者 (IdP)，通过 JWT 令牌实现单点登录。

### 完整流程

```
                            ┌──────────────────────┐
  ① 点击 SSO 按钮           │                      │
       ─────────────►       │     DeerFlow          │
                            │  (localhost:2027)     │
                            │                      │
                            └──────┬───────────────┘
                                   │
                   ② 重定向到 Admin.NET + sso_callback
                http://admin.net:7799/#/login?...&sso_callback=...

                                   ▼
                            ┌──────────────────────┐
                            │                      │
                            │     Admin.NET         │
                            │  (192.168.100.138     │
                            │   :7799)              │
                            │                      │
                            │  ③ 用户输入账号密码    │
                            │  ④ 登录成功            │
                            │  ⑤ 生成 HMAC-SHA256   │
                            │     JWT (用户信息)    │
                            │                      │
                            └──────┬───────────────┘
                                   │
                   ⑥ 重定向到 DeerFlow SSO 端点
                   /api/v1/auth/sso?token=<jwt>

                                   ▼
                            ┌──────────────────────┐
                            │     DeerFlow          │
                            │  ⑦ 验证 JWT           │
                            │  ⑧ 创建/链接用户      │
                            │  ⑨ 设置 session cookie │
                            │  ⑩ 进入工作区         │
                            └──────────────────────┘
```

---

## 一、DeerFlow 侧配置（已完成）

### `.env` 配置

```bash
SSO_ENABLED=true
SSO_PROVIDER_JWT_SECRET=3c1cbc3f546eda35168c3aa3cb91780fbe703f0996c6d123ea96dc85c70bbc0a
SSO_PROVIDER_NAME=admin_net
SSO_PROVIDER_DISPLAY_NAME=Admin.NET 登录
SSO_PROVIDER_ALGORITHM=HS256
SSO_PROVIDER_AUTO_CREATE_USER=true
SSO_PROVIDER_DEFAULT_ROLE=user
SSO_PROVIDER_TOKEN_MAX_AGE=300
SSO_PROVIDER_ICON=building
SSO_PROVIDER_LOGIN_URL=http://192.168.100.138:7799/index.html#/login?redirect=/&params={}
```

### JWT Claims 映射

| Admin.NET 字段 → | JWT Claim  | DeerFlow 目标字段         |
|-------------------|------------|-------------------------|
| `userId`          | `UserId`   | `oauth_id` (外部用户标识)  |
| `account`         | `Account`  | `email` 前缀 (`{Account}@sso.deerflow.internal`) |
| `realName`        | `RealName` | `display_name`           |
| `orgName`         | `OrgName`  | `org_name`               |
| `tenantId`        | `TenantId` | `external_tenant_id`     |

---

## 二、Admin.NET 侧修改

### 准备工作

```bash
# 在 Admin.NET 的 Web/ 目录下
cd Admin.NET/Web/
pnpm add jose
```

### 修改 1：添加环境变量

**文件：`Web/.env`**

在文件末尾追加：

```env
# DeerFlow SSO 集成
VITE_DEERFLOW_SSO_ENABLED = true
VITE_DEERFLOW_SSO_SECRET = 3c1cbc3f546eda35168c3aa3cb91780fbe703f0996c6d123ea96dc85c70bbc0a
```

> **注意**：如果项目使用了 `Web/.env.development` 或 `Web/.env.production`，也需要在对应文件中添加。

### 修改 2：创建 SSO 工具函数

**新建文件：`Web/src/utils/deerflow-sso.ts`**

```typescript
import { SignJWT } from 'jose';

/**
 * Admin.NET 用户信息（与 SysAuthApi.apiSysAuthUserInfoGet() 返回值对齐）
 */
interface SsoUserInfo {
  userId: number;
  account: string;
  realName: string;
  orgName: string;
  tenantId?: number;
}

/**
 * 生成 DeerFlow SSO 所需的 HMAC-SHA256 JWT
 *
 * @param user — Admin.NET 用户信息
 * @returns 签名的 JWT 字符串
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

### 修改 3：登录页面增加 SSO 回调处理

**文件：`Web/src/views/login/component/account.vue`**

在 `<script lang="ts" setup>` 区域内：

#### 3.1 添加 imports（在现有 imports 下方）

```typescript
import { generateDeerFlowSsoToken } from '/@/utils/deerflow-sso';
import { getAPI } from '/@/utils/axios-utils';
import { SysAuthApi } from '/@/api-services/api';
```

#### 3.2 修改 `signInSuccess` 函数

找到 `signInSuccess` 函数（约第 208 行），替换为：

```typescript
// 登录成功后的跳转
const signInSuccess = (isNoPower: boolean | undefined) => {
  if (isNoPower) {
    ElMessage.warning('抱歉，您没有登录权限');
    clearTokens();
  } else if (route.query?.sso_callback) {
    // DeerFlow SSO 回调
    handleDeerFlowSsoRedirect();
  } else {
    // 初始化登录成功时间问候语
    let currentTimeInfo = currentTime.value;
    // 登录成功，跳到转首页 如果是复制粘贴的路径，非首页/登录页，那么登录成功后重定向到对应的路径中
    if (route.query?.redirect) {
      router.push({
        path: <string>route.query?.redirect,
        query: Object.keys(<string>route.query?.params).length > 0 ? JSON.parse(<string>route.query?.params) : '',
      });
    } else {
      router.push('/');
    }

    // 登录成功提示
    const signInText = '欢迎回来！';
    ElMessage.success(`${currentTimeInfo}，${signInText}`);
    // 添加 loading，防止第一次进入界面时出现短暂空白
    NextLoading.start();
  }
};
```

#### 3.3 在 `signInSuccess` 上方添加 SSO 处理函数

```typescript
// DeerFlow SSO 回调处理
const handleDeerFlowSsoRedirect = async () => {
  try {
    // 获取当前登录用户的详细信息
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

---

## 三、验证

### 1. 确认 Admin.NET 启动正常

```bash
cd Admin.NET/Web/
pnpm run dev
```

### 2. 确认 DeerFlow 启动正常

登录页应显示 "Admin.NET 登录" 按钮。

### 3. 端到端测试

```bash
# 1. 访问 DeerFlow 登录页
open http://192.168.100.138:2027/login

# 2. 点击 "Admin.NET 登录" 按钮
#    → 浏览器跳转到 Admin.NET 登录页

# 3. 在 Admin.NET 输入账号密码登录
#    → 自动跳回 DeerFlow 工作区
```

### 4. 验证数据库

登录成功后，DeerFlow 数据库中应出现新用户：

```sql
SELECT email, display_name, org_name, oauth_provider, oauth_id
FROM users
WHERE oauth_provider = 'admin_net';
```

预期结果示例：
```
email: superadmin@sso.deerflow.internal
display_name: Admin.NET 管理员
org_name: Admin.NET Org
oauth_provider: admin_net
oauth_id: 1
```

---

## 四、关键参数说明

### `SSO_PROVIDER_LOGIN_URL` 格式

DeerFlow 前端登录页会自动拼接 `sso_callback` 参数：

```
{login_url}&sso_callback={encoded_deerflow_sso_endpoint}
```

完整 URL 示例（解码后）：

```
http://192.168.100.138:7799/index.html#/login
  ?redirect=/
  &params={}
  &sso_callback=http://192.168.100.138:2027/api/v1/auth/sso?provider=admin_net&next=%2Fworkspace
```

### `sso_callback` 参数

- 值格式：`http://{deerflow_host}/api/v1/auth/sso?provider=admin_net&next=%2Fworkspace`
- Admin.NET 登录成功后须在此 URL 后追加 `&token={signed_jwt}` 并重定向

### JWT Token 有效期

- 默认 300 秒（5 分钟），可通过 `SSO_PROVIDER_TOKEN_MAX_AGE` 调整
- Admin.NET 端的 `jose` 库生成时也需要匹配（已设置为 `5m`）

---

## 五、故障排查

| 现象                          | 可能原因                       | 解决                         |
|-------------------------------|-------------------------------|-----------------------------|
| DeerFlow 登录页无 SSO 按钮     | 网关未加载 `.env` 的 SSO 配置   | 重建 Docker 容器             |
| Admin.NET 跳转后 401           | JWT 签名密钥不一致              | 检查两端 `VITE_DEERFLOW_SSO_SECRET` = `SSO_PROVIDER_JWT_SECRET` |
| "Token too old" 错误          | JWT 生成到 DeerFlow 验证耗时过长 | 增大 `SSO_PROVIDER_TOKEN_MAX_AGE`，或确保时钟同步 |
| "Failed to decode token"      | JWT 格式错误                   | 确认使用 HS256 算法，claims 字段名大小写正确 |
| Admin.NET 无法获取用户信息      | Token 未正确存储                | 确认 `saveTokenAndInitRoutes` 已执行且 API 返回正常 |
