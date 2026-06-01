# 问卷模块 MVP 交付说明

## 实现范围

本次实现的是独立的 Survey / Questionnaire 模块，不进入竞品分析主 workflow，也不修改 CollectorAgent、AnalystAgent、ReportWriterAgent 的核心逻辑。

新增能力：

- QuestionnaireAgent：基于 report / claims 生成问卷，并根据用户修改要求返工问卷。
- SurveyAnalysisAgent：基于后端统计后的问卷反馈 JSON 生成分析洞察。
- Survey 专用 Schema、数据库表、service、API、CSV 导出和 CSV 上传解析。
- 前端 SurveyPanel：生成问卷、修改问卷、导出 CSV、上传反馈 CSV、展示分析与 SurveyEvidence 摘要。
- 独立 LLM 配置：`SURVEY_LLM_API_KEY` 等环境变量。

## 数据流

```text
Report completed
-> User clicks 生成问卷
-> POST /api/tasks/{task_id}/runs/{run_id}/survey/generate
-> QuestionnaireAgent
-> Survey draft
-> revise / export.csv / responses upload
-> backend CSV statistics
-> SurveyAnalysisAgent
-> SurveyAnalysis + SurveyEvidence summary
-> SurveyPanel display
```

## API Key 配置

在 `.env` 或 `backend/.env` 中配置：

```env
SURVEY_LLM_PROVIDER=openai_compatible
SURVEY_LLM_API_KEY=your_api_key_here
SURVEY_LLM_BASE_URL=https://api.openai.com/v1
SURVEY_LLM_MODEL=gpt-4o-mini
SURVEY_LLM_TEMPERATURE=0.3
SURVEY_LLM_TIMEOUT_SECONDS=60
```

前端不会接收或展示 API Key。未配置 `SURVEY_LLM_API_KEY` 时，问卷接口返回清晰错误，不影响主报告页面运行。

## 运行方式

后端：

```bash
cd /Users/leessang/Desktop/cis-agent-demo/backend
uvicorn app.main:app --reload
```

前端：

```bash
cd /Users/leessang/Desktop/cis-agent-demo/frontend
npm install
npm run dev
```

然后打开 Vite 输出的本地地址，先运行一个 task/report，再在报告下方使用 Survey Panel。

## CSV 说明

导出模板接口：

```text
GET /api/surveys/{survey_id}/export.csv
```

上传反馈 CSV 时，表头需要包含每道题的 `field_name`。后端会先统计：

- single_choice：选项数量、比例、最高频选项
- multiple_choice：支持逗号、分号、顿号、`|` 拆分
- rating：均值、中位数、最大值、最小值、分布
- number：均值、中位数、最大值、最小值
- text：非空文本样例

LLM 只接收统计后的 JSON，不直接分析原始 CSV。

## 关键文件

- `backend/app/schemas/survey.py`
- `backend/app/agents/questionnaire_agent.py`
- `backend/app/agents/survey_analysis_agent.py`
- `backend/app/services/survey_llm_client.py`
- `backend/app/services/survey_service.py`
- `backend/app/api/survey_routes.py`
- `backend/app/utils/csv_exporter.py`
- `backend/app/utils/csv_parser.py`
- `frontend/src/components/survey/SurveyPanel.tsx`
- `backend/tests/test_survey_module.py`
