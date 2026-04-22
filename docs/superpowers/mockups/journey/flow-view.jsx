/* global React, Icon, JOURNEY_DATA, JOURNEY_FLOWS, ClusterDot */
/* Journey Flow mode — sequential user paths over the same node data. */

const JourneyFlowView = ({ initialFlowId = "sales-full" }) => {
  const [flowId, setFlowId] = React.useState(initialFlowId);
  const [currentStep, setCurrentStep] = React.useState(0);
  const [playing, setPlaying] = React.useState(false);

  const flow = window.JOURNEY_FLOWS.find(f => f.id === flowId);
  const step = flow.steps[currentStep];
  const node = window.JOURNEY_DATA.nodes.find(n => n.id === step.nodeId);

  React.useEffect(() => { setCurrentStep(0); }, [flowId]);
  React.useEffect(() => {
    if (!playing) return;
    const t = setTimeout(() => {
      if (currentStep < flow.steps.length - 1) setCurrentStep(s => s + 1);
      else setPlaying(false);
    }, 2200);
    return () => clearTimeout(t);
  }, [playing, currentStep, flow]);

  return (
    <div style={{ display: "flex", width: "100%", height: "100%", background: "var(--bg)", overflow: "hidden" }}>
      {/* ── Left: flow picker ──────────────────────────────────── */}
      <aside className="scroll-slim" style={{ width: 280, flexShrink: 0, background: "var(--card)", borderRight: "1px solid var(--border-light)", padding: "14px 12px", overflow: "auto" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "0 8px 10px" }}>
          <Icon name="rocket" size={14} style={{ color: "var(--accent)" }} />
          <div className="os-label" style={{ fontSize: 10 }}>Пути пользователей</div>
          <button className="btn btn--ghost btn--icon" style={{ marginLeft: "auto", padding: 4 }}><Icon name="plus" size={12} /></button>
        </div>

        {window.JOURNEY_FLOWS.map(f => {
          const isActive = f.id === flowId;
          return (
            <button key={f.id} onClick={() => setFlowId(f.id)} style={{
              display: "block", width: "100%", textAlign: "left", padding: "10px 12px", marginBottom: 6,
              background: isActive ? "var(--accent-subtle)" : "transparent",
              border: `1px solid ${isActive ? "rgba(194,65,12,0.3)" : "transparent"}`,
              borderRadius: 8, cursor: "pointer", fontFamily: "inherit",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                <span className={`role-chip ${f.role === "admin" ? "role-chip--admin" : ""}`} style={{ fontSize: 10 }}>{f.role}</span>
                <span style={{ marginLeft: "auto", fontSize: 10, color: "var(--text-subtle)", display: "inline-flex", alignItems: "center", gap: 3 }}>
                  <Icon name="clock" size={10} /> {f.estMinutes} мин
                </span>
              </div>
              <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text)", lineHeight: 1.3, marginBottom: 3 }}>{f.title}</div>
              <div style={{ fontSize: 11, color: "var(--text-muted)", display: "flex", alignItems: "center", gap: 4 }}>
                <Icon name="arrow-right" size={10} /> {f.steps.length} шагов
              </div>
            </button>
          );
        })}

        <div style={{ marginTop: 14, padding: 10, background: "var(--bg)", borderRadius: 8, border: "1px dashed var(--border)" }}>
          <div style={{ fontSize: 11, color: "var(--text-muted)", lineHeight: 1.5 }}>
            <strong style={{ color: "var(--text)" }}>Gap-analysis:</strong> 4 экрана не охвачены ни одним путём.
            <a href="#" onClick={e=>e.preventDefault()} style={{ display: "block", marginTop: 4, color: "var(--accent)", fontWeight: 600, textDecoration: "none" }}>Показать →</a>
          </div>
        </div>
      </aside>

      {/* ── Center: storyboard ─────────────────────────────────── */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        {/* Toolbar */}
        <div style={{ padding: "14px 20px", borderBottom: "1px solid var(--border-light)", background: "var(--card)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 18, fontWeight: 700, letterSpacing: "-0.01em", marginBottom: 2 }}>{flow.title}</div>
              <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{flow.persona} · {flow.description}</div>
            </div>
            <div style={{ display: "flex", gap: 6, padding: 2, background: "var(--sidebar)", borderRadius: 8 }}>
              <button className="btn btn--ghost btn--icon" style={{ padding: 6 }} onClick={() => setCurrentStep(s => Math.max(0, s - 1))}><Icon name="chevron-left" size={14} /></button>
              <button onClick={() => setPlaying(p => !p)} className="btn btn--sm" style={{ background: playing ? "var(--accent)" : "#fff", color: playing ? "#fff" : "var(--text)", fontWeight: 700, minWidth: 86 }}>
                <Icon name="play-circle" size={13} /> {playing ? "Пауза" : "Play"}
              </button>
              <button className="btn btn--ghost btn--icon" style={{ padding: 6 }} onClick={() => setCurrentStep(s => Math.min(flow.steps.length - 1, s + 1))}><Icon name="chevron-right" size={14} /></button>
            </div>
            <div style={{ fontSize: 12, color: "var(--text-muted)", fontVariantNumeric: "tabular-nums", minWidth: 60, textAlign: "right" }}>
              <strong style={{ color: "var(--text)", fontSize: 14 }}>{currentStep + 1}</strong> / {flow.steps.length}
            </div>
          </div>

          {/* Step ribbon */}
          <div className="scroll-slim" style={{ display: "flex", gap: 0, marginTop: 14, overflowX: "auto", paddingBottom: 2 }}>
            {flow.steps.map((s, i) => {
              const n = window.JOURNEY_DATA.nodes.find(x => x.id === s.nodeId);
              const isActive = i === currentStep;
              const isPast = i < currentStep;
              return (
                <React.Fragment key={i}>
                  <button onClick={() => setCurrentStep(i)} style={{
                    display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 4,
                    padding: "10px 12px", border: `1px solid ${isActive ? "var(--accent)" : "var(--border-light)"}`,
                    borderRadius: 8, background: isActive ? "var(--accent-subtle)" : (isPast ? "var(--success-bg)" : "#fff"),
                    cursor: "pointer", minWidth: 180, flexShrink: 0, fontFamily: "inherit", textAlign: "left",
                    opacity: isPast && !isActive ? 0.75 : 1,
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, width: "100%" }}>
                      <span style={{
                        width: 22, height: 22, borderRadius: 999,
                        background: isActive ? "var(--accent)" : (isPast ? "var(--success)" : "var(--sidebar)"),
                        color: isActive || isPast ? "#fff" : "var(--text-muted)",
                        fontSize: 11, fontWeight: 700, display: "grid", placeItems: "center",
                      }}>{isPast ? "✓" : i + 1}</span>
                      {n && <ClusterDot cluster={n.cluster} size={7} />}
                      {n && <code style={{ fontSize: 10, color: "var(--text-muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{n.route}</code>}
                    </div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text)", lineHeight: 1.3 }}>{s.action}</div>
                  </button>
                  {i < flow.steps.length - 1 && (
                    <div style={{ display: "flex", alignItems: "center", padding: "0 4px", color: "var(--text-subtle)", flexShrink: 0 }}>
                      <Icon name="arrow-right" size={14} />
                    </div>
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </div>

        {/* Current step stage */}
        <div className="canvas-bg scroll-slim" style={{ flex: 1, overflow: "auto", padding: "24px 32px", display: "flex", flexDirection: "column", gap: 20 }}>
          <div style={{ display: "flex", gap: 20, alignItems: "flex-start" }}>
            {/* Step info card */}
            <div className="os-card" style={{ width: 340, padding: 18, flexShrink: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                <span style={{ width: 32, height: 32, borderRadius: 999, background: "var(--accent)", color: "#fff", fontWeight: 700, fontSize: 15, display: "grid", placeItems: "center" }}>{currentStep + 1}</span>
                <div>
                  <div className="os-label" style={{ fontSize: 10 }}>Шаг {currentStep + 1} из {flow.steps.length}</div>
                  <div style={{ fontSize: 16, fontWeight: 700, letterSpacing: "-0.01em", lineHeight: 1.2 }}>{step.action}</div>
                </div>
              </div>
              {step.note && (
                <div style={{ fontSize: 13, color: "var(--text-muted)", lineHeight: 1.5, marginBottom: 14, padding: "8px 10px", background: "var(--bg)", borderRadius: 6, borderLeft: "3px solid var(--accent)" }}>
                  {step.note}
                </div>
              )}
              {node && (
                <>
                  <div className="os-label" style={{ fontSize: 10, marginBottom: 6 }}>Экран</div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                    <ClusterDot cluster={node.cluster} />
                    <code style={{ fontSize: 12, color: "var(--text-muted)" }}>{node.route}</code>
                  </div>
                  <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 10 }}>{node.title}</div>
                  <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", fontSize: 11, color: "var(--text-muted)" }}>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}><span className={`dot dot--${node.impl}`} />{node.impl}</span>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}><span className={`dot dot--${node.qa}`} />{node.qaCount[0]}/{node.qaCount[1]}</span>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 3 }}><Icon name="list-checks" size={11} />{node.stories}</span>
                  </div>
                  <div style={{ display: "flex", gap: 6, marginTop: 14 }}>
                    <button className="btn btn--secondary btn--sm" style={{ flex: 1, justifyContent: "center" }}><Icon name="external-link" size={12} /> Открыть</button>
                    <button className="btn btn--ghost btn--sm" style={{ flex: 1, justifyContent: "center" }}><Icon name="map" size={12} /> На карте</button>
                  </div>
                </>
              )}
            </div>

            {/* Mock screenshot preview */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, fontSize: 11, color: "var(--text-muted)" }}>
                <Icon name="camera" size={12} />
                <span>превью · {flow.role}</span>
                <span style={{ color: "var(--text-subtle)" }}>·</span>
                <span>22.04 03:14</span>
                <span className="os-badge os-badge--copper" style={{ marginLeft: "auto" }}>live preview</span>
              </div>
              <div style={{ position: "relative", aspectRatio: "16/9.2", background: "#fff", borderRadius: 10, border: "1px solid var(--border-light)", boxShadow: "var(--shadow-md)", overflow: "hidden" }}>
                <div style={{ position: "absolute", inset: 0, padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 12px", background: "var(--bg)", borderRadius: 6 }}>
                    <code style={{ fontSize: 11, color: "var(--text-muted)" }}>{node?.route || "—"}</code>
                    <span style={{ fontSize: 13, fontWeight: 600 }}>{node?.title || ""}</span>
                  </div>
                  <div style={{ flex: 1, background: "var(--bg)", borderRadius: 6, padding: 14, display: "flex", flexDirection: "column", gap: 8 }}>
                    <div style={{ height: 10, width: "35%", background: "#D6D3CE", borderRadius: 3 }} />
                    <div style={{ height: 6, width: "65%", background: "#E7E5E0", borderRadius: 2 }} />
                    <div style={{ height: 6, width: "48%", background: "#E7E5E0", borderRadius: 2 }} />
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8, marginTop: 10 }}>
                      <div style={{ height: 72, background: "var(--accent-subtle)", borderRadius: 6, border: "1px solid #FDE68A" }} />
                      <div style={{ height: 72, background: "#fff", borderRadius: 6, border: "1px solid var(--border-light)" }} />
                      <div style={{ height: 72, background: "#fff", borderRadius: 6, border: "1px solid var(--border-light)" }} />
                    </div>
                  </div>
                </div>
                {/* highlight ring for active action */}
                <div style={{
                  position: "absolute", left: "18%", top: "28%", width: "38%", height: 30,
                  border: "2.5px dashed var(--accent)", borderRadius: 6, pointerEvents: "none",
                  boxShadow: "0 0 0 6px rgba(194,65,12,0.1)",
                }} />
                <div style={{
                  position: "absolute", left: "calc(18% + 38%)", top: "calc(28% + 8px)",
                  background: "var(--accent)", color: "#fff", fontSize: 11, fontWeight: 700,
                  padding: "4px 10px", borderRadius: 4, whiteSpace: "nowrap",
                  transform: "translateX(6px)",
                }}>
                  <Icon name="mouse-pointer-click" size={11} /> {step.action}
                </div>
              </div>

              {/* progress bar */}
              <div style={{ marginTop: 14, height: 4, background: "var(--border-light)", borderRadius: 999, overflow: "hidden" }}>
                <div style={{ height: "100%", width: `${((currentStep + 1) / flow.steps.length) * 100}%`, background: "var(--accent)", transition: "width 0.3s" }} />
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginTop: 6, fontSize: 11, color: "var(--text-muted)" }}>
                <span>Прогресс</span>
                <span style={{ fontVariantNumeric: "tabular-nums" }}>{Math.round(((currentStep + 1) / flow.steps.length) * 100)}%</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

Object.assign(window, { JourneyFlowView });
