# 问卷模块升级同步说明

## 1. 本次同步的重点

这次同步把当前工作区里已经完成的问卷能力整理为一套可运行、可验证、可交接的版本，重点不只是“能生成问卷”，而是让问卷模块真正服务于竞品分析主流程的证据补强。

同步内容包括：

- 独立的 `Survey / Questionnaire` 工作台
- `PainPointResearchAgent`，用于从 Planner / Report / Claims 中提取待验证痛点
- 痛点验证型问卷生成，而不是通用满意度问卷
- 多格式反馈导入：`csv`、`xlsx`、`json`、`txt`、`md`
- 反馈分析结果结构化输出：
  - `pain_point_validation`
  - `pain_point_ranking`
  - `claim_validation_matrix`
  - `recommended_report_revisions`
- `SurveyEvidence` 自动转换为标准 `Evidence(source_type="survey")`
- 问卷工作台读取任务最新 Run 的 planner 快照，避免展示过期问卷规划

## 2. 相关文件

后端核心文件：

- `backend/app/agents/pain_point_research_agent.py`
- `backend/app/agents/questionnaire_agent.py`
- `backend/app/agents/survey_analysis_agent.py`
- `backend/app/schemas/survey.py`
- `backend/app/services/feedback_ingestion_service.py`
- `backend/app/services/survey_service.py`
- `backend/app/api/survey_routes.py`

前端核心文件：

- `frontend/src/components/survey/SurveyPanel.tsx`
- `frontend/src/pages/SurveyWorkspacePage.tsx`
- `frontend/src/api/client.ts`
- `frontend/src/api/types.ts`

测试：

- `backend/tests/test_survey_module.py`

## 3. 使用方式

### 3.1 启动后端

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

### 3.2 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问：

```text
http://127.0.0.1:5173
```

### 3.3 推荐体验路径

1. 在“竞品分析工作台”创建任务并先运行一次主 workflow
2. 切到“问卷分析工作台”
3. 选择同一个任务，查看最新 Run 对应的 `Planner 问卷规划`
4. 生成问卷，导出反馈模板或示例反馈
5. 上传真实反馈文件或示例反馈文件
6. 查看 `pain_point_validation`、`claim_validation_matrix` 和 `SurveyEvidence`

## 4. Planner 问卷规划的显示规则

这次同步后，问卷工作台不再盲目使用旧 fallback 数据。

当前规则：

- 优先读取任务最新 Run 的 `report.json_report.planner`
- 如果任务还没有 Run 或最新 Run 没有可用 planner 快照，才回退到本地 fallback planner context

因此页面上会出现两种正常情况：

### 情况 A：Planner 推荐问卷

页面会显示：

- `Objective`
- `Respondent type`
- `Question themes`
- `Hypotheses`
- `Guidance`

### 情况 B：Planner 不推荐问卷

页面会显示：

- `暂无明确目标`
- `暂无明确受访者`
- `暂无主题`
- `暂无假设`

这表示当前最新 Run 的 Planner 真实判断为不建议问卷，并不表示页面没有刷新。

## 5. 反馈文件支持

当前支持：

- `.csv`
- `.xlsx`
- `.json`
- `.txt`
- `.md`

导入后会进行字段映射与聚合分析，不保留原始逐行隐私数据用于前端展示。

## 6. 自检建议

同步后至少执行：

```bash
cd backend
pytest
```

或最少执行：

```bash
python -m pytest backend/tests/test_survey_module.py backend/tests/test_schema_and_workflow.py
```

前端构建检查：

```bash
cd frontend
npm run build
```

## 7. 已验证项

本次同步前已完成以下验证：

- `backend/tests/test_survey_module.py`
- `backend/tests/test_schema_and_workflow.py`
- 前端 `npm run build`
- 问卷工作台白屏修复验证
- 最新 Run 的 Planner 快照可正确反映到问卷工作台
- 示例反馈导出后可重新上传并生成有效 `SurveyEvidence`

## 8. 当前边界

- Survey 模块仍然是独立工作台，不直接挂入主竞品分析 DAG
- `CustomWorkflowRunner` 保持 legacy fallback，不额外扩展新的 Survey 主流程节点
- 问卷结果会生成标准 `Evidence`，但不会自动改写已有报告；页面会通过 `recommended_report_revisions` 提示如何回写
