# Atlas20 Batch Execution Protocol

每个 batch（roadmap 中的一组 task）按这个固定流程跑。已在 Batch 3/4/5 验证。

## 0. 前置检查

- `git status` 干净（允许 `.ccg/tasks/review-*/.turns.json` 等无关脏文件）
- 当前在目标 feature branch（如 `redesign/r3-premium`）
- 上一 batch 已 commit + 归档

## 1. Brief

写在 `.ccg/tasks/batch-N-<topic>/brief.md`。包括：

- **Goal** — 1 段说清楚 batch 在干嘛
- **Scope** — PR 大小估算（LOC + 测试数）
- **Inputs/Outputs** — 具体哪些文件读、哪些 schema 写
- **Algorithm** — 关键决策点（边界、cutoff、容错策略）
- **Tests** — 列出必须覆盖的行为（用编号 1. 2. 3. ...）
- **Out of scope** — 明确哪些往后推
- **Acceptance** — pytest count、frontend typecheck、smoke endpoint
- **Files expected to change** — 文件清单 + LOC 估算

Brief 的质量决定了 codex 的产出质量。**不要省略边界条件描述**。

## 2. Builder dispatch

```bash
"C:/Users/WW/.claude/bin/codeagent-wrapper.exe" --backend codex \
  --cwd "D:/Code/Atlas20" \
  --prompt-file ".ccg/tasks/batch-N-<topic>/builder-prompt.md" \
  --mode builder
```

通过 `Agent` 工具 `run_in_background=true` 跑 general-purpose subagent 包装上面那条命令。

`builder-prompt.md` 要求 codex：
1. 读 brief.md 实现全部 Scope
2. 写完跑 `python -m pytest tests/ -x -q` 自验
3. 跑前端 typecheck（如有 frontend 改动）
4. 自己跑一遍 review（gemini/claude/自查）并 apply 修复
5. 提交 commit message：`feat(api): <one-line summary>`
6. 报告 PASS/FAIL + 文件清单 + 测试增量

## 3. 落地后立即验证（Claude 直接跑）

不要相信 codex 说 PASS — 自己跑：

- `git log --oneline -3` — 确认 commit hash
- `git status --short` — 应该干净
- `python -m pytest tests/ -q | tail -5` — 测试数对得上 brief 估算
- `cd apps/web && npm run typecheck | tail -5`（如有前端改动）

如果有任何 mismatch 立即 SendMessage 给 codex 问情况。

## 4. Cross-validation（并行 2 个 reviewer）

**关键**：必须两个独立 session，不要省。

```
Agent A: subagent_type=feature-dev:code-reviewer, model=opus
Agent B: subagent_type=general-purpose, 包装 codex reviewer
```

两边各给 commit hash + 完整的 brief 路径 + REVIEW DIMENSIONS。要求：
- 评分 X/100
- Critical / Warning / Info 分类
- 是否 APPROVE / REQUEST_CHANGES

并行（同一个 message 多个 Agent tool calls）。

**注意**：
- Claude 侧 reviewer **必须用 `model: "opus"`**，否则上下文不够（曾用 sonnet 报 "1m context not enabled" 错）
- Codex 侧 reviewer 通过 stdin 传 prompt（`<<'EOF' ... EOF`），不要用 `--prompt-file`（曾因 `Start-Job` PowerShell 参数绑定失败导致 50min 卡死）
- 如果 codex reviewer 超过 20min 无响应，`TaskStop` 杀掉重派

## 5. Fix dispatch（如有 Warning/Critical）

把两边 reviewer 的 findings 合并到一个 `fixer-prompt.md`。每个 finding 包含：
- 具体文件路径 + 行号
- 问题描述
- 期望的修复方式（reassignment / 重构 / API 变化）
- 是否需要 regression test

Codex fixer 要求：**每个 finding 一个独立 commit**（不要合并），消息格式：
```
fix(api): batch N reviewer pass — <one-line summary>
```

或重构用：
```
refactor(api): batch N reviewer pass — <one-line summary>
```

或测试用：
```
test(api): batch N reviewer pass — <one-line summary>
```

每个 commit 后跑 pytest 确认绿。

## 6. 第二轮 cross-validation

派两个新的 reviewer agent（不要复用之前的）。Diff range 用 `<original-commit>..HEAD`。

要求 reviewer 明确标注每个原始 Warning：
- ✅ RESOLVED + evidence (file:line)
- ❌ STILL OPEN + 原因

如果引入新 finding，回到步骤 5；如果两边都 APPROVE + 0 findings，进步骤 7。

## 7. 收尾

- `TaskUpdate` 把当前 batch task 标 completed
- 不要自己 commit `.ccg/tasks/` 的归档（codex 在 fixer/builder 内自动做了）
- 写一个一句话的总结回给用户：commit list + 测试数 + cross-val 矩阵
- 准备下一 batch brief

## 关键教训（来自 Batch 1-5）

1. **不要在 brief 里写 codex 能自由发挥的部分**。例如 Batch 3 codex 自作主张加了 BTC_BH 排除逻辑——虽然没坏但越界。Brief 越精确，越好 review。

2. **NaN/inf 检查必须有 regression test**。Batch 3 reviewer 发现 `_as_float` 没拦截 inf，Batch 5 reviewer 又在另一个文件发现同样问题——这是高复发 class，每次都要在 brief 里点名。

3. **`_today()` 是项目唯一 datetime.now() 入口**。Batch 5 W3 是 `compare.py` 直接用 `datetime.now()` bypass 了 settings.anchor_date——这违反"determinism"原则。新加任何 service 都要走 `get_settings().model_copy(update={"anchor_date": _today()})`。

4. **`_common.py` 阈值**：data_access 里 helper 被 3+ 模块用就提到 `_common.py`。Batch 5 fixer 提了 7 个 helper。

5. **Codex reviewer 容易卡死**：如果用 PowerShell `Start-Job -ScriptBlock` 派 sub-process，会因参数绑定失败假装在跑。优先用 stdin pipe。

6. **codex 的 PASS 报告不可全信**：曾经报告显示 PASS 但实际 pytest 还没跑完，或自己内部 review 跳过了。Claude 必须自己跑一遍。

7. **每个 fix commit 单独提**，不要合并多个 fix 到一个 commit。这样 reviewer round 2 能精确对应每个 Warning。

8. **回归测试要写在 brief 里**：让 builder 直接产出，而不是等 fixer round 加。Batch 5 round 2 才补 options NaN test 是个浪费。

## 流程图

```
brief.md → codex builder → pytest verify
                ↓
       commit (feat/refactor)
                ↓
   Opus 4.7 reviewer  +  fresh codex reviewer  (并行)
                ↓
          findings.json
                ↓
        if Critical/Warning → fixer-prompt.md → codex fixer
                                    ↓
                               3+ fix commits
                                    ↓
                           round 2 cross-validation
                                    ↓
                             both APPROVE 0 findings?
                              ├── yes → next batch
                              └── no  → loop back to fixer
```
