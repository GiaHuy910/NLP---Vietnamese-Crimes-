import React, { useState } from "react";

function App() {
  const [input, setInput] = useState("");
  const [entityResult, setEntityResult] = useState<any>(null);
  const [triggerResult, setTriggerResult] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<
    "entities" | "triggers" | "timeline" | "event-table" | "graph"
  >("entities");
  const [loading, setLoading] = useState(false);

  const MAX_WORDS = 256;
  const words = input.trim() ? input.trim().split(/\s+/) : [];
  const wordCount = words.length;
  const isExceeded = wordCount > MAX_WORDS;

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setInput(value);
  };

  const handleSendProcess = async () => {
    if (!input || isExceeded) return;
    setLoading(true);
    setEntityResult(null);
    setTriggerResult(null);
    try {
      const [response1, response2] = await Promise.all([
        fetch("http://localhost:8000/api/process", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: input }),
        }),
        fetch("http://localhost:8000/api/process/event-trigger", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: input }),
        }),
      ]);

      const data1 = await response1.json();
      const data2 = await response2.json();

      setEntityResult(data1);
      setTriggerResult(data2);
    } catch (error) {
      console.error(error);
      setEntityResult({
        error: "Cannot connect to backend server (http://localhost:8000)",
      });
    } finally {
      setLoading(false);
    }
  };

  // Hàm highlight Entities
  const renderHighlightedEntities = (text: string, entities: any[]) => {
    if (!entities || entities.length === 0) return text;
    const sortedEntities = [...entities].sort((a, b) => a.start - b.start);
    const elements = [];
    let lastIndex = 0;

    sortedEntities.forEach((ent, index) => {
      if (ent.start > lastIndex) {
        elements.push(text.substring(lastIndex, ent.start));
      }

      let badgeClass = "bg-secondary";
      if (ent.label === "PERSON") badgeClass = "bg-primary";
      else if (ent.label === "LOCATION") badgeClass = "bg-success";
      else if (ent.label === "MONEY") badgeClass = "bg-warning text-dark";
      else if (ent.label === "ORGANIZATION" || ent.label === "ORG")
        badgeClass = "bg-danger";
      else if (ent.label === "TIME") badgeClass = "bg-info text-dark";
      else if (ent.label === "DRUG") badgeClass = "bg-purple text-white";

      elements.push(
        <span
          key={index}
          className={`badge ${badgeClass} mx-1 px-2 py-1 align-baseline`}
          style={{ fontSize: "0.95rem" }}
        >
          {text.substring(ent.start, ent.end)}
          <span
            className="ms-1 badge bg-light text-dark"
            style={{ fontSize: "0.65rem" }}
          >
            {ent.label}
          </span>
        </span>,
      );
      lastIndex = Math.max(lastIndex, ent.end);
    });
    if (lastIndex < text.length) {
      elements.push(text.substring(lastIndex));
    }
    return elements;
  };

  // Hàm highlight Triggers
  const renderHighlightedTriggers = (text: string, triggers: any[]) => {
    if (!triggers || triggers.length === 0) return text;
    const sortedTriggers = [...triggers].sort((a, b) => a.start - b.start);
    const elements = [];
    let lastIndex = 0;

    sortedTriggers.forEach((trg, index) => {
      if (trg.start > lastIndex) {
        elements.push(text.substring(lastIndex, trg.start));
      }
      elements.push(
        <span
          key={index}
          className="badge bg-warning text-dark mx-1 px-2 py-1 align-baseline"
          style={{ fontSize: "0.95rem" }}
        >
          {text.substring(trg.start, trg.end)}
          <span
            className="ms-1 badge bg-dark text-white"
            style={{ fontSize: "0.65rem" }}
          >
            {trg.event_type}
          </span>
        </span>,
      );
      lastIndex = Math.max(lastIndex, trg.end);
    });
    if (lastIndex < text.length) {
      elements.push(text.substring(lastIndex));
    }
    return elements;
  };

  // Trích xuất Timeline
  const extractTimelineEvents = (text: string, entities: any[]) => {
    if (!entities || !text) return [];
    return entities
      .filter((ent) => ent.label === "TIME")
      .map((ent) => {
        const snippetStart = Math.max(0, ent.start - 40);
        const snippetEnd = Math.min(text.length, ent.end + 120);
        let context = text.substring(snippetStart, snippetEnd).trim();
        if (snippetStart > 0) context = "..." + context;
        if (snippetEnd < text.length) context = context + "...";
        return { timeText: ent.text, start: ent.start, context };
      })
      .sort((a, b) => a.start - b.start);
  };

  // Xây dựng Bảng sự kiện (Kết hợp Triggers và các thực thể xung quanh trong bán kính 150 ký tự)
  const buildEventTableData = () => {
    if (!triggerResult?.triggers || !entityResult?.entities) return [];
    return triggerResult.triggers.map((trg: any) => {
      // Tìm các thực thể xuất hiện gần trigger này (trong khoảng ±150 ký tự)
      const associatedEntities = entityResult.entities.filter(
        (ent: any) => Math.abs(ent.start - trg.start) < 150,
      );
      return {
        triggerText: trg.text,
        eventType: trg.event_type,
        span: `${trg.start} - ${trg.end}`,
        entities: associatedEntities,
      };
    });
  };

  return (
    <div
      className="min-vh-100 vw-100 d-flex flex-column align-items-center py-5 overflow-auto"
      style={{ background: "rgba(19, 16, 40, 0.94)" }}
    >
      <div
        className="d-flex flex-column align-items-center p-4"
        style={{
          width: "90%",
          maxWidth: "850px",
          background: "rgba(19, 16, 40, 0.94)",
          border: "solid 4px rgba(5, 20, 55, 0.94)",
          boxShadow:
            "rgba(0, 0, 0, 0.25) 0 10px 15px -3px, rgba(0, 0, 0, 0.1) 0 4px 6px -2px",
          borderRadius: "12px",
        }}
      >
        <h3 className="text-white mb-4">NLP - Vietnamese Crimes Analysis</h3>

        <div className="w-100 mb-4">
          <div className="d-flex justify-content-between align-items-center mb-1 px-1">
            <span className="text-muted small">Input text content</span>
            <span
              className={`small fw-bold ${isExceeded ? "text-danger" : "text-info"}`}
            >
              {wordCount} / {MAX_WORDS} words{" "}
              {isExceeded && "⚠️ (Exceeds limit!)"}
            </span>
          </div>

          <div className="input-group d-flex justify-content-between align-items-center">
            <input
              type="text"
              className={`form-control rounded-0 ${isExceeded ? "border-danger text-danger" : ""}`}
              placeholder="Enter crime news or article text..."
              value={input}
              onChange={handleChange}
              onKeyDown={(e) =>
                e.key === "Enter" && !isExceeded && handleSendProcess()
              }
            />
            <button
              className={`btn ${input && !loading && !isExceeded ? "btn-primary" : "disabled btn-secondary"} rounded-0`}
              type="button"
              onClick={handleSendProcess}
              disabled={loading || !input || isExceeded}
            >
              {loading ? "Processing..." : "Process"}
            </button>
            <button className="btn btn-info rounded-0" type="button">
              Add file
            </button>
          </div>

          {isExceeded && (
            <div className="text-danger small mt-1 px-1">
              Warning: Input text has exceeded the maximum limit of {MAX_WORDS}{" "}
              words!
            </div>
          )}
        </div>

        {/* Khu vực kết quả với 5 nút Tabs */}
        {(entityResult || triggerResult) && (
          <div className="w-100 mt-2 p-3 bg-dark border border-secondary rounded text-start text-white">
            <div className="d-flex flex-wrap justify-content-between align-items-center border-bottom pb-2 mb-3 gap-2">
              <h6 className="text-info m-0">Analysis Result:</h6>

              {/* Nhóm 5 nút Tabs chuyển đổi */}
              <div className="btn-group btn-group-sm flex-wrap" role="group">
                <button
                  type="button"
                  className={`btn ${activeTab === "entities" ? "btn-primary" : "btn-outline-secondary"}`}
                  onClick={() => setActiveTab("entities")}
                >
                  Entities
                </button>
                <button
                  type="button"
                  className={`btn ${activeTab === "triggers" ? "btn-primary" : "btn-outline-secondary"}`}
                  onClick={() => setActiveTab("triggers")}
                >
                  Triggers
                </button>
                <button
                  type="button"
                  className={`btn ${activeTab === "timeline" ? "btn-primary" : "btn-outline-secondary"}`}
                  onClick={() => setActiveTab("timeline")}
                >
                  Timeline
                </button>
                <button
                  type="button"
                  className={`btn ${activeTab === "event-table" ? "btn-primary" : "btn-outline-secondary"}`}
                  onClick={() => setActiveTab("event-table")}
                >
                  Event Table
                </button>
              </div>
            </div>

            {/* Tab 1: Entities */}
            {activeTab === "entities" && (
              <div>
                {entityResult?.error ? (
                  <div className="text-danger">{entityResult.error}</div>
                ) : entityResult ? (
                  <div>
                    <p className="mb-2 text-light small">
                      Status:{" "}
                      <span className="text-success">
                        {entityResult.status}
                      </span>{" "}
                      | Message: {entityResult.message}
                    </p>
                    <div className="mb-3 p-3 bg-black rounded border border-secondary">
                      <strong className="text-light d-block mb-2">
                        Highlighted Entities:
                      </strong>
                      <div className="fs-6 lh-lg">
                        {renderHighlightedEntities(
                          entityResult.input_text,
                          entityResult.entities,
                        )}
                      </div>
                    </div>
                    {entityResult.entities?.length > 0 && (
                      <div className="table-responsive">
                        <table className="table table-dark table-striped table-bordered table-sm mb-0">
                          <thead>
                            <tr>
                              <th>Text</th>
                              <th>Label</th>
                              <th>Span</th>
                            </tr>
                          </thead>
                          <tbody>
                            {entityResult.entities.map(
                              (ent: any, idx: number) => (
                                <tr key={idx}>
                                  <td>
                                    <code>{ent.text}</code>
                                  </td>
                                  <td>
                                    <span className="badge bg-info text-dark">
                                      {ent.label}
                                    </span>
                                  </td>
                                  <td>
                                    {ent.start} - {ent.end}
                                  </td>
                                </tr>
                              ),
                            )}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                ) : null}
              </div>
            )}

            {/* Tab 2: Triggers */}
            {activeTab === "triggers" && (
              <div>
                {triggerResult ? (
                  <div>
                    <div className="mb-3 p-3 bg-black rounded border border-secondary">
                      <strong className="text-light d-block mb-2">
                        Highlighted Event Triggers:
                      </strong>
                      <div className="fs-6 lh-lg">
                        {renderHighlightedTriggers(
                          triggerResult.input_text,
                          triggerResult.triggers,
                        )}
                      </div>
                    </div>
                    {triggerResult.triggers?.length > 0 && (
                      <div className="table-responsive">
                        <table className="table table-dark table-striped table-bordered table-sm mb-0">
                          <thead>
                            <tr>
                              <th>Text</th>
                              <th>Event Type</th>
                              <th>Span</th>
                            </tr>
                          </thead>
                          <tbody>
                            {triggerResult.triggers.map(
                              (trg: any, idx: number) => (
                                <tr key={idx}>
                                  <td>
                                    <code>{trg.text}</code>
                                  </td>
                                  <td>
                                    <span className="badge bg-warning text-dark">
                                      {trg.event_type}
                                    </span>
                                  </td>
                                  <td>
                                    {trg.start} - {trg.end}
                                  </td>
                                </tr>
                              ),
                            )}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-muted">No data.</div>
                )}
              </div>
            )}

            {/* Tab 3: Timeline */}
            {activeTab === "timeline" && (
              <div>
                <strong className="text-light d-block mb-3">
                  Chronological Event Timeline:
                </strong>
                {entityResult?.entities ? (
                  (() => {
                    const events = extractTimelineEvents(
                      entityResult.input_text,
                      entityResult.entities,
                    );
                    if (events.length === 0)
                      return (
                        <div className="text-muted">
                          No time entities found.
                        </div>
                      );
                    return (
                      <div className="position-relative ps-4 border-start border-info border-2 my-2">
                        {events.map((ev, idx) => (
                          <div key={idx} className="mb-4 position-relative">
                            <span
                              className="position-absolute bg-info rounded-circle"
                              style={{
                                width: "12px",
                                height: "12px",
                                left: "-31px",
                                top: "4px",
                              }}
                            />
                            <div className="bg-black p-3 rounded border border-secondary">
                              <span className="badge bg-info text-dark fs-6 mb-2">
                                {ev.timeText}
                              </span>
                              <div className="text-light small lh-base">
                                {ev.context}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    );
                  })()
                ) : (
                  <div className="text-muted">No data.</div>
                )}
              </div>
            )}

            {/* Tab 4: Event Table */}
            {activeTab === "event-table" && (
              <div>
                <strong className="text-light d-block mb-3">
                  Structured Event Table (Triggers & Associated Entities):
                </strong>
                {triggerResult?.triggers ? (
                  <div className="table-responsive">
                    <table className="table table-dark table-striped table-bordered table-sm mb-0">
                      <thead>
                        <tr>
                          <th>Event Type (Trigger)</th>
                          <th>Trigger Span</th>
                          <th>Involved Entities</th>
                        </tr>
                      </thead>
                      <tbody>
                        {buildEventTableData().map((item: any, idx: number) => (
                          <tr key={idx}>
                            <td>
                              <span className="badge bg-warning text-dark">
                                {item.eventType}
                              </span>
                              <div className="small mt-1">
                                <code>{item.triggerText}</code>
                              </div>
                            </td>
                            <td>{item.span}</td>
                            <td>
                              {item.entities.length > 0 ? (
                                <div className="d-flex flex-wrap gap-1">
                                  {item.entities.map((e: any, eIdx: number) => (
                                    <span
                                      key={eIdx}
                                      className="badge bg-secondary"
                                    >
                                      {e.text}{" "}
                                      <small className="text-info">
                                        ({e.label})
                                      </small>
                                    </span>
                                  ))}
                                </div>
                              ) : (
                                <span className="text-muted small">
                                  No close entities
                                </span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="text-muted">No trigger data available.</div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
