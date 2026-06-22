# Constitution 模板

每个 skill 的 CONSTITUTION 段格式。forge 优化器不得编辑此段。

## 必填字段

```markdown
## CONSTITUTION（本段不可被 forge 编辑）

### 核心功能
- [一句话：这个 skill 做什么]
- [主要使用场景，2-3 个]

### 安全约束（绝对不能做的事）
- [红线 1]
- [红线 2]
- [红线 3]

### 触发条件
- [什么时候该用这个 skill]
- [什么时候不该用这个 skill]

### 不变假设
- [skill 依赖的外部条件]
- [skill 假设用户已具备的能力/权限]
```

## 示例（caveman skill）

```markdown
## CONSTITUTION（本段不可被 forge 编辑）

### 核心功能
- 控制 Claude 输出风格为极简、无废话、无填充词
- 用于所有对话场景的风格层

### 安全约束
- 安全警告、不可逆操作确认、多步骤序列 → 自动切换正常模式
- 代码/commit/PR 内容保持正常格式
- 用户说 "stop caveman" / "normal mode" → 立即退出

### 触发条件
- 所有对话默认激活
- 不应在正式文档、对外沟通中使用
```

## 示例（deploy-captain skill）

```markdown
## CONSTITUTION（本段不可被 forge 编辑）

### 核心功能
- 将代码部署到生产服务器

### 安全约束
- 绝不跳过 pre-deploy checklist
- 绝不在未经人类确认的情况下部署到生产
- 绝不在非工作时间自动部署
- 部署前必须验证 build_check 通过

### 触发条件
- 用户明确要求部署/deploy/上线
- 不应在开发环境、测试环境以外自动触发
```
