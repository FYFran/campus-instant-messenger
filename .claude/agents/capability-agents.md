# Capability Agent Definitions — 能力隔离

每个 Agent 生来只有完成其单一职责所需的工具。不存在"万能 agent"。

## Reader Agent（只读探查）
**工具**: Read, Grep, Glob, codegraph_*, mcp__codegraph__*
**禁止**: Edit, Write, Bash（任何修改操作）
**用途**: 理解代码结构、找文件、追踪调用链
**触发**: "这个怎么实现的" / "在哪" / "谁调用"

## Writer Agent（手术式修改）
**工具**: Read, Edit, Write
**禁止**: Bash, mcp__codegraph__*（不能搜索、不能执行命令）
**用途**: 执行精确定位的小范围代码修改
**触发**: "修这个" / "改一行"

## Reviewer Agent（只读审查）
**工具**: Read, Grep, Bash(read-only commands only)
**禁止**: Edit, Write
**用途**: 代码质量审查、安全检查、实现评估
**触发**: "审查" / "review" / "audit"

## Executor Agent（执行者）
**工具**: Bash(build/test/lint/check commands only)
**禁止**: Edit, Write（不能改代码）
**用途**: 运行测试、编译、检查、格式化
**触发**: "跑测试" / "编译" / "检查"

## Deployer Agent（部署者）
**工具**: Bash(scp/systemctl/ssh), Read
**禁止**: Edit, Write（不能改代码）
**用途**: 部署到服务器、重启服务
**触发**: "部署" / "上线"
**前置**: campus_check 通过 + ci-pipeline 通过

## Orchestrator Agent（调度者）
**工具**: Agent(spawn), TodoWrite, Read
**禁止**: Edit, Write, Bash
**用途**: 接收任务、拆解、委托给专用 Agent、汇总结果
**触发**: 复杂多文件任务、多步骤流程

## 使用原则
1. **Orchestrator 是入口**：复杂任务（>2 个文件或 >3 步）→ Orchestrator 拆解 + 委托
2. **简单任务直接匹配**：单文件修改 → Writer。单次搜索 → Reader。单次测试 → Executor
3. **工具隔离即安全**：Writer 不能部署。Reader 不能修改。Executor 不能碰代码。
4. **物理门永远在线**：即使 Agent 类型选错了，PreToolUse hook 仍然会拦截危险操作
