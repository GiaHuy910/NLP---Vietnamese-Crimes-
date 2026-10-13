import React, { useState } from "react";

function App() {
  const [input, setInput] = useState("");
  const [responseResult, setResponseResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setInput(value);
  };

  const handleSendProcess = async () => {
    if (!input) return;
    setLoading(true);
    setResponseResult(null);
    try {
      const response = await fetch("http://localhost:3001/api/process", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ text: input }),
      });
      const data = await response.json();
      console.log(data);
      setResponseResult(data);
    } catch (error) {
      console.error(error);
      setResponseResult({ error: "Cannot connect to backend server (http://localhost:3001)" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="vh-100 vw-100 d-flex align-items-center justify-content-center"
      style={{
        background: "rgba(19, 16, 40, 0.94)",
        border: "rgba(19, 16, 40, 0.94)",
        accentColor: "rgba(19, 16, 40, 0.94)",
      }}
    >
      <div
        className="d-flex flex-column align-items-center justify-content-center p-4"
        style={{
          width: "85%",
          maxWidth: "800px",
          background: "rgba(19, 16, 40, 0.94)",
          border: "solid 4px rgba(5, 20, 55, 0.94)",
          accentColor: "rgba(3, 11, 110, 0.94)",
          boxShadow:
            "rgba(0, 0, 0, 0.25) 0 10px 15px -3px, rgba(0, 0, 0, 0.1) 0 4px 6px -2px",
          borderRadius: "12px",
        }}
      >
        <h3 className="text-white mb-4">NLP - Vietnamese Crimes Analysis</h3>
        <div className="w-100 mb-4">
          <div className="input-group d-flex justify-content-between align-items-center">
            <input
              type="text"
              className="form-control rounded-0"
              placeholder="Enter crime news or article text..."
              aria-label="News content"
              value={input}
              onChange={handleChange}
              onKeyDown={(e) => e.key === "Enter" && handleSendProcess()}
            />
            <button
              className={`btn ${input && !loading ? "btn-primary" : "disabled btn-secondary"} rounded-0`}
              type="button"
              onClick={handleSendProcess}
              disabled={loading || !input}
            >
              {loading ? "Processing..." : "Process"}
            </button>
            <button className="btn btn-info rounded-0" type="button">
              Add file
            </button>
          </div>
        </div>

        {responseResult && (
          <div className="w-100 mt-2 p-3 bg-dark border border-secondary rounded text-start text-white">
            <h6 className="text-info border-bottom pb-2">Analysis Result from Server:</h6>
            <pre className="text-light m-0" style={{ whiteSpace: "pre-wrap" }}>
              {JSON.stringify(responseResult, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;

