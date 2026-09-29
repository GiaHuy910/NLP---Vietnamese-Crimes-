import React, { useState } from "react";

function App() {
  const [input, setInput] = useState("");

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setInput(value);
  };
  const handleSendProcess = async () => {
    try {
      const response = await fetch("http://localhost:3001/api/process", {
        method: "GET",
        body: JSON.stringify(input),
      });
      const data = await response.json();
      console.log(data);
    } catch (error) {
      console.log(error);
    }
  };
  return (
    <div
      className="vh-100 vw-100 d-flex align-items-center justify-content-center"
      style={{
        background: "rgba(19, 16, 40, 0.94) ",
        border: "rgba(19, 16, 40, 0.94)",
        accentColor: "rgba(19, 16, 40, 0.94)",
      }}
    >
      <div
        className="d-flex align-items-center justify-content-center"
        style={{
          width: "85%",
          height: "85%",
          background: "rgba(19, 16, 40, 0.94) ",
          border: "solid 8px rgba(5, 20, 55, 0.94)",
          accentColor: "rgba(3, 11, 110, 0.94)",
          boxShadow:
            "rgba(0, 0, 0, 0.1) 0 10px 15px -3px, rgba(0, 0, 0, 0.05) 0 4px 6px -2px;",
        }}
      >
        <div>
          <div className="input-group d-flex justify-content-between align-items-center">
            <input
              type="text"
              className="form-control rounded-0 w-50"
              placeholder="Type in news"
              aria-label="Recipient's username with two button addons"
              onChange={handleChange}
            />
            <button
              className={`btn ${input ? "btn-primary" : "disabled btn-secondary"} btn-primary rounded-0 `}
              type="button"
              onClick={handleSendProcess}
            >
              Process
            </button>
            <button className="btn btn-info rounded-0" type="button">
              Add file
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
