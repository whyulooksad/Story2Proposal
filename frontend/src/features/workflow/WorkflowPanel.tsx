import type { RunDetail } from "../../types/run";

const labels: Record<string, string> = {
  orchestrator: "orchestrator",
  architect: "architect",
  section_writer: "section_writer",
  reasoning_evaluator: "reasoning_evaluator",
  data_fidelity_evaluator: "data_fidelity_evaluator",
  visual_evaluator: "visual_evaluator",
  review_controller: "review_controller",
  refiner: "refiner",
  renderer: "renderer",
};

export function WorkflowPanel({ run }: { run: RunDetail }) {
  const steps = Object.keys(labels);

  return (
    <section className="panel workflow-panel">
      <div className="panel-header">
        <h2>流程状态</h2>
        <div className="panel-kicker">当前节点：{run.currentNode}</div>
      </div>
      <div className="step-grid">
        {steps.map((step) => (
          <div key={step} className={step === run.currentNode ? "step-card active" : "step-card"}>
            <div className="step-card-dot" />
            <span>{labels[step]}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
