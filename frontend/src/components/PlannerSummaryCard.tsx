import type { CollectorDiagnostics, WorkflowSummary } from "../types";
import { workflowContractSource } from "../lib/contractSelectors";

export function PlannerSummaryCard({
  workflowSummary,
  collectorDiagnostics,
}: {
  workflowSummary?: WorkflowSummary;
  collectorDiagnostics?: CollectorDiagnostics;
}) {
  const core = workflowSummary?.core;
  const extensions = workflowSummary?.extensions;
  const diagnostics = workflowSummary?.diagnostics;
  const survey = extensions?.survey;
  const questionnaireFollowUp = extensions?.questionnaire_follow_up;
  const domainPack = core?.domain_pack;
  const summaryContract = workflowContractSource(workflowSummary);
  const hasPlannerSummary = Boolean(
    core?.selected_dimensions?.length ||
    workflowSummary?.selected_dimensions?.length ||
    core?.intent_classification ||
    workflowSummary?.intent_classification ||
    core?.ambiguity_level ||
    workflowSummary?.ambiguity_level ||
    core?.scope_type ||
    workflowSummary?.scope_type ||
    core?.scope_size ||
    workflowSummary?.scope_size ||
    core?.candidate_competitors?.length ||
    workflowSummary?.candidate_competitors?.length ||
    typeof survey?.survey_needed === "boolean" ||
    typeof workflowSummary?.survey_needed === "boolean" ||
    core?.recommended_next_constraints?.length ||
    workflowSummary?.recommended_next_constraints?.length,
  );
  const hasCollectorGuidance = Boolean(
    collectorDiagnostics?.planner_query_hints_used ||
    collectorDiagnostics?.targeted_recollection_used ||
    collectorDiagnostics?.effective_query_count_by_competitor ||
    collectorDiagnostics?.effective_queries_preview_by_competitor,
  );

  if (!hasPlannerSummary && !hasCollectorGuidance) return null;

  return (
    <section className="mb-4 grid gap-3 lg:grid-cols-2">
      {hasPlannerSummary && (
        <div className="rounded border border-line bg-white p-4">
          <h2 className="mb-3 text-base font-semibold">Planner Summary</h2>
          <div className="grid gap-2 text-sm md:grid-cols-2">
            <SummaryItem label="workflow role" value={workflowSummary?.workflow_role ?? "-"} />
            <SummaryItem label="intent" value={core?.intent_classification ?? workflowSummary?.intent_classification ?? "-"} />
            <SummaryItem label="ambiguity" value={core?.ambiguity_level ?? workflowSummary?.ambiguity_level ?? "-"} />
            <SummaryItem label="scope type" value={core?.scope_type ?? workflowSummary?.scope_type ?? "-"} />
            <SummaryItem label="scope size" value={core?.scope_size ?? workflowSummary?.scope_size ?? "-"} />
            <SummaryItem label="domain pack" value={domainPack?.display_name ?? "-"} />
            <SummaryItem label="survey needed" value={formatBoolean(survey?.survey_needed ?? workflowSummary?.survey_needed)} />
            <SummaryItem label="survey recommended" value={formatBoolean(survey?.survey_recommended ?? workflowSummary?.survey_recommended)} />
            <SummaryItem label="run id" value={core?.run_id ?? workflowSummary?.run_id ?? "-"} />
          </div>
          {(extensions?.primary_workflow_kind || workflowSummary?.primary_workflow_kind || workflowSummary?.survey_integration_mode || diagnostics?.workflow_data_source || workflowSummary?.workflow_data_source) && (
            <div className="mt-3 rounded border border-line bg-panel p-3 text-xs leading-5 text-slate-700">
              {(extensions?.primary_workflow_kind || workflowSummary?.primary_workflow_kind) && <div>primary workflow: {extensions?.primary_workflow_kind ?? workflowSummary?.primary_workflow_kind}</div>}
              {workflowSummary?.survey_integration_mode && <div>survey integration: {workflowSummary.survey_integration_mode}</div>}
              {(diagnostics?.workflow_data_source || workflowSummary?.workflow_data_source) && <div>summary source: {diagnostics?.workflow_data_source ?? workflowSummary?.workflow_data_source}</div>}
              <div>frontend contract: {summaryContract}</div>
              {domainPack?.domain_pack_id && <div>domain pack id: {domainPack.domain_pack_id}</div>}
            </div>
          )}
          {!!(diagnostics?.runner_capability_notes ?? workflowSummary?.runner_capability_notes)?.length && (
            <div className="mt-3 rounded border border-line bg-panel p-3 text-xs leading-5 text-slate-700">
              <div className="mb-1 font-semibold">Architecture Notes</div>
              {(diagnostics?.runner_capability_notes ?? workflowSummary?.runner_capability_notes ?? []).map((item) => (
                <div key={item}>- {item}</div>
              ))}
            </div>
          )}
          <div className="mt-3">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Selected Dimensions</div>
            <div className="flex flex-wrap gap-2">
              {(workflowSummary?.selected_dimensions?.length
                ? workflowSummary.selected_dimensions
                : core?.selected_dimensions?.length
                  ? core.selected_dimensions
                : ["No planner-selected dimensions returned"]).map((dimension) => (
                <span
                  key={dimension}
                  className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-semibold text-accent"
                >
                  {dimension}
                </span>
              ))}
            </div>
          </div>
          {!!(core?.candidate_competitors?.length || workflowSummary?.candidate_competitors?.length) && (
            <div className="mt-3">
              <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Candidate Competitors</div>
              <div className="flex flex-wrap gap-2">
                {(workflowSummary?.candidate_competitors ?? (core?.candidate_competitors as Array<{ name?: string; confidence?: number }> | undefined) ?? []).slice(0, 4).map((item, index) => (
                  <span
                    key={`${item.name ?? "candidate"}-${index}`}
                    className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-700"
                  >
                    {item.name ?? "unknown"}
                    {typeof item.confidence === "number" ? ` (${Math.round(item.confidence * 100)}%)` : ""}
                  </span>
                ))}
              </div>
            </div>
          )}
          {!!(core?.recommended_next_constraints?.length || workflowSummary?.recommended_next_constraints?.length) && (
            <div className="mt-3 rounded border border-line bg-panel p-3 text-xs leading-5 text-slate-700">
              <div className="mb-1 font-semibold">Planner constraints</div>
              {(workflowSummary?.recommended_next_constraints ?? core?.recommended_next_constraints ?? []).slice(0, 3).map((item) => (
                <div key={item}>- {item}</div>
              ))}
            </div>
          )}
          {!!((core?.downstream_guidance?.writer?.length || workflowSummary?.downstream_guidance?.writer?.length)) && (
            <div className="mt-3 rounded border border-line bg-panel p-3 text-xs leading-5 text-slate-700">
              <div className="mb-1 font-semibold">Writer guidance</div>
              {(workflowSummary?.downstream_guidance?.writer ?? core?.downstream_guidance?.writer ?? []).slice(0, 3).map((item) => (
                <div key={item}>- {item}</div>
              ))}
            </div>
          )}
          {questionnaireFollowUp && (
            <div className="mt-3 rounded border border-line bg-panel p-3 text-xs leading-5 text-slate-700">
              <div className="mb-1 font-semibold">Questionnaire Follow-up</div>
              <div>launch mode: {questionnaireFollowUp.launch_mode ?? "follow_up_sidecar"}</div>
              <div>recommended: {formatBoolean(questionnaireFollowUp.recommended)}</div>
              <div>required: {formatBoolean(questionnaireFollowUp.required)}</div>
              <div>objective: {questionnaireFollowUp.objective ?? "-"}</div>
            </div>
          )}
        </div>
      )}

      {hasCollectorGuidance && (
        <div className="rounded border border-line bg-white p-4">
          <h2 className="mb-3 text-base font-semibold">Collector Guidance</h2>
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <SummaryItem
              label="planner hints used"
              value={collectorDiagnostics?.planner_query_hints_used ? "yes" : "no"}
            />
            <SummaryItem
              label="targeted recollection"
              value={collectorDiagnostics?.targeted_recollection_used ? "yes" : "no"}
            />
            <SummaryItem
              label="collector mode"
              value={collectorDiagnostics?.collector_mode_used ?? collectorDiagnostics?.collector_mode_requested ?? "-"}
            />
            <SummaryItem
              label="domain pack"
              value={collectorDiagnostics?.domain_pack_id ?? "-"}
            />
          </div>
          {!!collectorDiagnostics?.effective_query_count_by_competitor && (
            <div className="mt-3 space-y-2">
              {Object.entries(collectorDiagnostics.effective_query_count_by_competitor).map(([competitor, count]) => (
                <div key={competitor} className="rounded border border-line bg-panel p-3 text-sm">
                  <div className="font-semibold">{competitor}</div>
                  <div className="mt-1 text-xs text-slate-600">
                    effective query count: {count}
                    {typeof collectorDiagnostics?.planner_hint_query_count_by_competitor?.[competitor] === "number" && (
                      <span> | planner hint queries: {collectorDiagnostics.planner_hint_query_count_by_competitor[competitor]}</span>
                    )}
                    {typeof collectorDiagnostics?.targeted_query_count_by_competitor?.[competitor] === "number" && (
                      <span> | targeted queries: {collectorDiagnostics.targeted_query_count_by_competitor[competitor]}</span>
                    )}
                  </div>
                  {!!collectorDiagnostics?.targeted_queries_preview_by_competitor?.[competitor]?.length && (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {collectorDiagnostics.targeted_queries_preview_by_competitor[competitor].slice(0, 3).map((query) => (
                        <span key={query} className="rounded border border-amber-200 bg-amber-50 px-2 py-1 text-xs text-amber-800">
                          {query}
                        </span>
                      ))}
                    </div>
                  )}
                  {!!collectorDiagnostics?.effective_queries_preview_by_competitor?.[competitor]?.length && (
                    <div className="mt-2 flex flex-wrap gap-2">
                      {collectorDiagnostics.effective_queries_preview_by_competitor[competitor].slice(0, 3).map((query) => (
                        <span key={query} className="rounded border border-line bg-white px-2 py-1 text-xs text-slate-700">
                          {query}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function SummaryItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-line bg-panel px-3 py-2">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 font-semibold text-ink">{value}</div>
    </div>
  );
}

function formatBoolean(value: boolean | undefined): string {
  if (value === undefined) return "-";
  return value ? "yes" : "no";
}
