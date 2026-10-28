import React, { useState, useEffect, useRef } from "react";

interface Entity {
  text: string;
  label: string;
  start: number;
  end: number;
}

interface Trigger {
  text: string;
  event_type: string;
  start: number;
  end: number;
}

interface Argument {
  role: string;
  entity: Entity;
}

interface EventItem {
  event_type: string;
  trigger: Trigger;
  arguments: Argument[];
}

interface AnalysisResult {
  id?: string;
  timestamp?: string;
  message: string;
  input_text: string;
  status: string;
  model_used?: string;
  entities: Entity[];
  triggers: Trigger[];
  events: EventItem[];
  char_count?: number;
  word_count?: number;
}

interface HistoryItem {
  id: string;
  timestamp: string;
  preview: string;
  result: AnalysisResult;
}

const SAMPLE_TEXTS = [
  {
    title: "1. Khởi tố & Bắt giữ (Lừa đảo)",
    text: "Ngày 15/8, Công an quận Đống Đa đã khởi tố Nguyễn Văn A về hành vi lừa đảo chiếm đoạt tài sản số tiền 500 triệu đồng tại Hà Nội.",
  },
  {
    title: "2. Chuyên án Ma túy",
    text: "Tối 20/10, lực lượng Cảnh sát điều tra tội phạm về ma túy Công an TP.HCM đã bắt giữ Trần Thị B tại bến xe Miền Đông, thu giữ 2 bánh heroin và 1000 viên ma túy đá.",
  },
  {
    title: "3. Cướp giật tài sản",
    text: "Chiều 12/9, tại đường Nguyễn Huệ quận 1, đối tượng Lê Văn C đã dùng dao găm đâm bị thương anh Hoàng Văn D để cướp chiếc xe máy Honda SH trị giá 85 triệu đồng.",
  },
  {
    title: "4. Xét xử sơ thẩm",
    text: "Sáng 5/11, Tòa án nhân dân thành phố Đà Nẵng đã xét xử và tuyên phạt bị cáo Phạm Minh E 15 năm tù giam về tội giết người.",
  },
];

const ENTITY_CONFIG: Record<string, { nameVi: string; badgeClass: string; color: string }> = {
  PERSON: { nameVi: "Người / Cá nhân", badgeClass: "badge-person", color: "#2563eb" },
  ORGANIZATION: { nameVi: "Tổ chức / Cơ quan", badgeClass: "badge-organization", color: "#ea580c" },
  ORG: { nameVi: "Tổ chức / Cơ quan", badgeClass: "badge-organization", color: "#ea580c" },
  LOCATION: { nameVi: "Địa điểm / Nơi xảy ra", badgeClass: "badge-location", color: "#059669" },
  TIME: { nameVi: "Thời gian", badgeClass: "badge-time", color: "#9333ea" },
  MONEY: { nameVi: "Tiền tệ / Thiệt hại", badgeClass: "badge-money", color: "#d97706" },
  DRUG: { nameVi: "Ma túy / Chất cấm", badgeClass: "badge-drug", color: "#db2777" },
  CRIME: { nameVi: "Tội danh", badgeClass: "badge-crime", color: "#dc2626" },
  PRODUCT: { nameVi: "Phương tiện / Vật phẩm", badgeClass: "badge-product", color: "#0891b2" },
};

const EVENT_TYPE_MAP: Record<string, string> = {
  BAT_GIU: "Bắt giữ",
  KHOI_TO: "Khởi tố",
  XET_XU: "Xét xử",
  THU_GIU: "Thu giữ",
  LUA_DAO: "Lừa đảo",
  CUOP_TROM: "Cướp / Trộm",
  BAO_LUC: "Bạo lực / Giết / Cố ý gây thương tích",
  MA_TUY: "Tội phạm Ma túy",
};

const ROLE_MAP: Record<string, string> = {
  DOI_TUONG: "Đối tượng (Nghi can)",
  NAN_NHAN: "Nạn nhân",
  CO_QUAN: "Cơ quan thụ lý",
  DIA_DIEM: "Địa điểm",
  THOI_GIAN: "Thời gian",
  TANG_VAT: "Tang vật",
  TAI_SAN: "Tài sản",
  HUNG_KHI: "Hung khí",
  TOI_DANH: "Tội danh",
  MUC_AN: "Mức án",
};

const API_BASE_URL = "http://127.0.0.1:3001";

function App() {
  const [input, setInput] = useState("");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"visual" | "entities" | "events" | "timeline" | "raw">("visual");
  const [highlightMode, setHighlightMode] = useState<"all" | "entities" | "triggers">("all");
  const [entityFilter, setEntityFilter] = useState<string>("ALL");
  const [searchEntity, setSearchEntity] = useState<string>("");

  // Storage / History state
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [showHistoryModal, setShowHistoryModal] = useState(false);

  // Export menu & toast
  const [showExportModal, setShowExportModal] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Feedback state
  const [feedbackRating, setFeedbackRating] = useState<"positive" | "negative" | null>(null);
  const [feedbackCategory, setFeedbackCategory] = useState("Thiếu thực thể");
  const [feedbackComment, setFeedbackComment] = useState("");
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load history from localStorage on initial render
  useEffect(() => {
    try {
      const saved = localStorage.getItem("nlp_vietnamese_crimes_history");
      if (saved) {
        setHistory(JSON.parse(saved));
      }
    } catch (e) {
      console.error("Không thể đọc lịch sử từ localStorage:", e);
    }
  }, []);

  const saveToHistory = (res: AnalysisResult) => {
    try {
      const newItem: HistoryItem = {
        id: "hist_" + Date.now(),
        timestamp: new Date().toLocaleString("vi-VN"),
        preview: res.input_text.slice(0, 65) + (res.input_text.length > 65 ? "..." : ""),
        result: res,
      };
      const updated = [newItem, ...history.filter((h) => h.result.input_text !== res.input_text)].slice(0, 20);
      setHistory(updated);
      localStorage.setItem("nlp_vietnamese_crimes_history", JSON.stringify(updated));
    } catch (e) {
      console.error("Lỗi lưu lịch sử:", e);
    }
  };

  const clearHistory = () => {
    setHistory([]);
    localStorage.removeItem("nlp_vietnamese_crimes_history");
    showToast("Đã xóa toàn bộ lịch sử phân tích.");
  };

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const handleSendProcess = async (textToProcess?: string) => {
    const text = (textToProcess !== undefined ? textToProcess : input).trim();
    if (!text) {
      setErrorMsg("Vui lòng nhập văn bản tin tức hoặc chọn câu mẫu.");
      return;
    }
    setLoading(true);
    setErrorMsg(null);
    setFeedbackRating(null);
    setFeedbackSubmitted(false);

    try {
      const response = await fetch(`${API_BASE_URL}/api/process`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Server trả về mã lỗi ${response.status}`);
      }

      const data: AnalysisResult = await response.json();
      data.id = "analysis_" + Date.now();
      data.timestamp = new Date().toLocaleString("vi-VN");
      setResult(data);
      saveToHistory(data);
      showToast("Phân tích thành công!");
    } catch (err: any) {
      console.error(err);
      setErrorMsg(
        err.message?.includes("Failed to fetch")
          ? `Không thể kết nối đến Backend (${API_BASE_URL}). Vui lòng đảm bảo server đang chạy (python -m src.main).`
          : `Lỗi: ${err.message}`
      );
    } finally {
      setLoading(false);
    }
  };

  // Upload file text
  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target?.result as string;
      if (text) {
        setInput(text);
        handleSendProcess(text);
      }
    };
    reader.readAsText(file, "UTF-8");
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  // Export functions
  const exportAsJSON = () => {
    if (!result) return;
    const exportData = {
      title: "Hồ sơ trích xuất thông tin vụ án (NLP Vietnamese Crimes)",
      export_time: new Date().toISOString(),
      metadata: {
        model: result.model_used || "Tích hợp",
        word_count: result.word_count || result.input_text.split(/\s+/).length,
        char_count: result.char_count || result.input_text.length,
      },
      input_text: result.input_text,
      entities: result.entities,
      triggers: result.triggers,
      events: result.events,
    };
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json;charset=utf-8" });
    downloadBlob(blob, `crime_analysis_${Date.now()}.json`);
    showToast("Đã xuất file JSON thành công!");
    setShowExportModal(false);
  };

  const exportAsCSV = () => {
    if (!result) return;
    let csvContent = "\uFEFF"; // UTF-8 BOM for Excel
    csvContent += "=== BẢNG THỰC THỂ (NER ENTITIES) ===\n";
    csvContent += "STT,Thực thể (Text),Nhãn (Label),Ý nghĩa,Vị trí bắt đầu (Start),Vị trí kết thúc (End)\n";
    result.entities.forEach((ent, i) => {
      const conf = ENTITY_CONFIG[ent.label] || { nameVi: ent.label };
      csvContent += `${i + 1},"${ent.text.replace(/"/g, '""')}","${ent.label}","${conf.nameVi}",${ent.start},${ent.end}\n`;
    });

    csvContent += "\n=== BẢNG SỰ KIỆN & VAI TRÒ (EVENTS & ROLES) ===\n";
    csvContent += "STT,Loại sự kiện,Động từ kích hoạt (Trigger),Vai trò liên quan,Thực thể gán vai trò\n";
    result.events.forEach((ev, i) => {
      const evName = EVENT_TYPE_MAP[ev.event_type] || ev.event_type;
      const trgText = ev.trigger?.text || "";
      if (ev.arguments && ev.arguments.length > 0) {
        ev.arguments.forEach((arg) => {
          const roleName = ROLE_MAP[arg.role] || arg.role;
          csvContent += `${i + 1},"${evName}","${trgText.replace(/"/g, '""')}","${roleName}","${arg.entity?.text?.replace(/"/g, '""') || ""}"\n`;
        });
      } else {
        csvContent += `${i + 1},"${evName}","${trgText.replace(/"/g, '""')}","Không có vai trò lân cận",""\n`;
      }
    });

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8" });
    downloadBlob(blob, `crime_analysis_${Date.now()}.csv`);
    showToast("Đã xuất file CSV thành công!");
    setShowExportModal(false);
  };

  const exportAsReportTXT = () => {
    if (!result) return;
    const lines: string[] = [];
    lines.push("================================================================================");
    lines.push("              BÁO CÁO TRÍCH XUẤT THÔNG TIN VỤ ÁN HÌNH SỰ (NLP REPORT)");
    lines.push("================================================================================");
    lines.push(`Thời gian phân tích : ${result.timestamp || new Date().toLocaleString("vi-VN")}`);
    lines.push(`Mô hình sử dụng     : ${result.model_used || "Tích hợp"}`);
    lines.push(`Tổng số thực thể    : ${result.entities.length}`);
    lines.push(`Tổng số sự kiện     : ${result.events.length}`);
    lines.push("--------------------------------------------------------------------------------");
    lines.push("I. NỘI DUNG VĂN BẢN GỐC:");
    lines.push(result.input_text);
    lines.push("--------------------------------------------------------------------------------");
    lines.push("II. DANH SÁCH THỰC THỂ PHÁT HIỆN ĐƯỢC (NER):");
    result.entities.forEach((ent, idx) => {
      const conf = ENTITY_CONFIG[ent.label] || { nameVi: ent.label };
      lines.push(`  ${idx + 1}. [${ent.label} - ${conf.nameVi}] "${ent.text}" (Ký tự: ${ent.start} -> ${ent.end})`);
    });
    lines.push("--------------------------------------------------------------------------------");
    lines.push("III. CẤU TRÚC SỰ KIỆN VÀ CÁC VAI TRÒ THAM GIA:");
    if (result.events.length === 0) {
      lines.push("  (Không phát hiện sự kiện hình sự rõ ràng)");
    } else {
      result.events.forEach((ev, idx) => {
        const evName = EVENT_TYPE_MAP[ev.event_type] || ev.event_type;
        lines.push(`  Sự kiện #${idx + 1}: [${ev.event_type}] ${evName}`);
        lines.push(`    - Động từ kích hoạt (Trigger): "${ev.trigger?.text}" (vị trí ${ev.trigger?.start}-${ev.trigger?.end})`);
        if (ev.arguments && ev.arguments.length > 0) {
          lines.push("    - Các vai trò xác định được:");
          ev.arguments.forEach((arg) => {
            const roleName = ROLE_MAP[arg.role] || arg.role;
            lines.push(`        + ${roleName} (${arg.role}): "${arg.entity?.text}"`);
          });
        } else {
          lines.push("    - Chưa tìm thấy vai trò liên kết lân cận.");
        }
      });
    }
    lines.push("================================================================================");

    const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
    downloadBlob(blob, `crime_report_${Date.now()}.txt`);
    showToast("Đã xuất báo cáo TXT thành công!");
    setShowExportModal(false);
  };

  const copyToClipboard = () => {
    if (!result) return;
    navigator.clipboard.writeText(JSON.stringify(result, null, 2));
    showToast("Đã sao chép toàn bộ dữ liệu JSON vào Clipboard!");
  };

  const downloadBlob = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  // Submit Feedback
  const handleSubmitFeedback = async () => {
    if (!feedbackRating || !result) return;
    try {
      await fetch(`${API_BASE_URL}/api/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: result.input_text,
          rating: feedbackRating,
          category: feedbackCategory,
          comment: feedbackComment,
          timestamp: new Date().toISOString(),
        }),
      });
      setFeedbackSubmitted(true);
      showToast("Cảm ơn bạn! Phản hồi đã được ghi nhận để cải thiện mô hình.");
    } catch (e) {
      console.error(e);
      setFeedbackSubmitted(true);
      showToast("Đã ghi nhận phản hồi của bạn.");
    }
  };

  // Render Visual Highlighting (Interactive text)
  const renderVisualText = () => {
    if (!result || !result.input_text) return null;
    const text = result.input_text;

    interface SpanItem {
      start: number;
      end: number;
      type: "entity" | "trigger";
      label: string;
      title: string;
      badgeClass: string;
    }

    const spans: SpanItem[] = [];

    if (highlightMode === "all" || highlightMode === "entities") {
      result.entities?.forEach((ent) => {
        const conf = ENTITY_CONFIG[ent.label] || { nameVi: ent.label, badgeClass: "bg-secondary", color: "#666" };
        spans.push({
          start: ent.start,
          end: ent.end,
          type: "entity",
          label: ent.label,
          title: conf.nameVi,
          badgeClass: conf.badgeClass,
        });
      });
    }

    if (highlightMode === "all" || highlightMode === "triggers") {
      result.triggers?.forEach((trg) => {
        spans.push({
          start: trg.start,
          end: trg.end,
          type: "trigger",
          label: trg.event_type,
          title: EVENT_TYPE_MAP[trg.event_type] || trg.event_type,
          badgeClass: "badge-trigger",
        });
      });
    }

    // Sort spans by start asc, length desc
    spans.sort((a, b) => a.start - b.start || (b.end - b.start) - (a.end - a.start));

    // Remove overlapping spans (keep the first/longer)
    const filteredSpans: SpanItem[] = [];
    spans.forEach((item) => {
      const overlap = filteredSpans.some((f) => item.start < f.end && item.end > f.start);
      if (!overlap) {
        filteredSpans.push(item);
      }
    });

    const elements: React.ReactNode[] = [];
    let curIndex = 0;

    filteredSpans.forEach((span, idx) => {
      if (span.start > curIndex) {
        elements.push(<span key={`text_${idx}`}>{text.substring(curIndex, span.start)}</span>);
      }

      elements.push(
        <span
          key={`span_${idx}`}
          className={`badge ${span.badgeClass} mx-1 px-2 py-1 d-inline-flex align-items-center gap-1`}
          style={{ fontSize: "0.95rem", cursor: "pointer", transition: "transform 0.15s ease" }}
          title={`${span.type === "trigger" ? "Hành vi Sự kiện" : "Thực thể"}: ${span.title} (${span.label})`}
        >
          <span>{text.substring(span.start, span.end)}</span>
          <span
            className="badge bg-dark text-white opacity-75"
            style={{ fontSize: "0.68rem", letterSpacing: "0.5px" }}
          >
            {span.label}
          </span>
        </span>
      );
      curIndex = Math.max(curIndex, span.end);
    });

    if (curIndex < text.length) {
      elements.push(<span key="text_end">{text.substring(curIndex)}</span>);
    }

    return elements;
  };

  // Filtered entities for entities table
  const filteredEntities = result?.entities?.filter((ent) => {
    const matchLabel = entityFilter === "ALL" || ent.label === entityFilter;
    const matchSearch =
      !searchEntity ||
      ent.text.toLowerCase().includes(searchEntity.toLowerCase()) ||
      ent.label.toLowerCase().includes(searchEntity.toLowerCase());
    return matchLabel && matchSearch;
  }) || [];

  return (
    <div className="container-fluid min-vh-100 py-4 px-3 px-md-5 d-flex flex-column align-items-center">
      {/* Toast Alert */}
      {toastMessage && (
        <div
          className="position-fixed top-0 end-0 p-3"
          style={{ zIndex: 1080 }}
        >
          <div className="toast show align-items-center text-white bg-success border-0 shadow-lg px-3 py-2 rounded-3">
            <div className="d-flex align-items-center gap-2">
              <span>{toastMessage}</span>
            </div>
          </div>
        </div>
      )}

      {/* Main Container Card */}
      <div className="w-100 glass-panel rounded-4 p-4 p-md-5" style={{ maxWidth: "1050px" }}>
        {/* Top Header */}
        <div className="d-flex flex-wrap justify-content-between align-items-center border-bottom border-secondary border-opacity-25 pb-3 mb-4 gap-3">
          <div>
            <h2 className="text-white fw-bold m-0 d-flex align-items-center gap-2 fs-3">
              <span style={{ color: "#38bdf8" }}>NLP</span> Vietnamese Crimes
            </h2>
            <p className="text-muted small m-0 mt-1">
              Hệ thống trích xuất Thực thể (NER) &amp; Sự kiện tội phạm tiếng Việt
            </p>
          </div>

          <div className="d-flex align-items-center gap-2 flex-wrap">
            <button
              className="btn btn-sm btn-outline-info rounded-pill px-3 d-flex align-items-center gap-1"
              type="button"
              onClick={() => setShowHistoryModal(true)}
              title="Xem lịch sử các văn bản đã phân tích"
            >
              <span>🕒 Lịch sử ({history.length})</span>
            </button>
            <span className="badge bg-dark border border-secondary text-info px-2 py-2 rounded-pill small">
              API: 127.0.0.1:3001
            </span>
          </div>

          {isExceeded && (
            <div className="text-danger small mt-1 px-1">
              Warning: Input text has exceeded the maximum limit of {MAX_WORDS}{" "}
              words!
            </div>
          )}
        </div>

        {/* Input Section */}
        <div className="mb-4">
          {/* Quick Samples Dropdown */}
          <div className="d-flex flex-wrap align-items-center justify-content-between mb-2 gap-2">
            <span className="text-muted small fw-semibold">
              Nhập nội dung bài báo / tin tức vụ án:
            </span>
            <div className="d-flex align-items-center gap-2 flex-wrap">
              <span className="text-muted small">Mẫu nhanh:</span>
              <div className="btn-group btn-group-sm">
                {SAMPLE_TEXTS.map((sample, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className="btn btn-outline-secondary text-light btn-sm"
                    style={{ fontSize: "0.78rem" }}
                    onClick={() => {
                      setInput(sample.text);
                      handleSendProcess(sample.text);
                    }}
                  >
                    Mẫu {idx + 1}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Text Area */}
          <div className="position-relative">
            <textarea
              className="form-control glass-subpanel text-white rounded-3 p-3 border-secondary"
              rows={4}
              placeholder="Nhập hoặc dán nội dung văn bản vụ án vào đây (Ví dụ: Ngày 15/8, Công an quận Đống Đa đã khởi tố Nguyễn Văn A về hành vi lừa đảo...)"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              style={{ fontSize: "1rem", resize: "vertical" }}
            />
            {input && (
              <button
                type="button"
                className="btn btn-sm btn-link text-muted position-absolute end-0 top-0 mt-2 me-2 text-decoration-none"
                onClick={() => setInput("")}
              >
                ✕ Xóa
              </button>
            )}
          </div>

          {/* Controls below textarea */}
          <div className="d-flex flex-wrap justify-content-between align-items-center mt-3 gap-2">
            <div className="text-muted small">
              <span>{input.trim() ? input.trim().split(/\s+/).length : 0} từ</span>
              <span className="mx-2">•</span>
              <span>{input.length} ký tự</span>
            </div>

            <div className="d-flex align-items-center gap-2 flex-wrap">
              {/* Add file button */}
              <input
                type="file"
                ref={fileInputRef}
                style={{ display: "none" }}
                accept=".txt"
                onChange={handleFileUpload}
              />
              <button
                type="button"
                className="btn btn-outline-secondary text-light rounded-pill px-3 btn-sm"
                onClick={() => fileInputRef.current?.click()}
              >
                📁 Tải file (.txt)
              </button>

              {/* Process Button */}
              <button
                type="button"
                className="btn btn-cyan rounded-pill px-4 fw-semibold d-flex align-items-center gap-2 shadow"
                disabled={loading || !input.trim()}
                onClick={() => handleSendProcess()}
              >
                {loading ? (
                  <>
                    <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true" />
                    <span>Đang phân tích...</span>
                  </>
                ) : (
                  <span>🚀 Phân tích ngay</span>
                )}
              </button>
            </div>
          </div>

          {/* Error Alert */}
          {errorMsg && (
            <div className="alert alert-danger mt-3 rounded-3 py-2 px-3 small border-0 shadow-sm d-flex justify-content-between align-items-center">
              <span>⚠️ {errorMsg}</span>
              <button type="button" className="btn-close btn-close-white" onClick={() => setErrorMsg(null)} />
            </div>
          )}
        </div>

        {/* RESULTS SECTION */}
        {result && (
          <div className="mt-4 pt-3 border-top border-secondary border-opacity-25">
            {/* Top Action Bar of Results: Metrics + Export Button */}
            <div className="d-flex flex-wrap justify-content-between align-items-center mb-3 gap-3">
              <div>
                <h5 className="text-white fw-bold m-0 d-flex align-items-center gap-2">
                  <span>📊 Kết quả phân tích</span>
                  <span className="badge bg-success bg-opacity-25 text-success border border-success border-opacity-50 small" style={{ fontSize: "0.75rem" }}>
                    Mô hình: {result.model_used || "Tích hợp"}
                  </span>
                </h5>
              </div>

              {/* THE EXPORT BUTTON & ACTIONS */}
              <div className="d-flex align-items-center gap-2 flex-wrap">
                <button
                  type="button"
                  className="btn btn-sm btn-outline-light rounded-pill px-3"
                  onClick={copyToClipboard}
                  title="Sao chép dữ liệu JSON"
                >
                  📋 Copy JSON
                </button>

                {/* Main Export Dropdown / Button */}
                <div className="dropdown">
                  <button
                    type="button"
                    className="btn btn-sm btn-purple rounded-pill px-3 fw-bold dropdown-toggle d-flex align-items-center gap-1 shadow-sm"
                    onClick={() => setShowExportModal(true)}
                  >
                    <span>💾 Xuất kết quả (Export)</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Quick Stat Cards */}
            <div className="row g-2 mb-4">
              <div className="col-6 col-md-3">
                <div className="glass-subpanel p-3 rounded-3 text-center border-start border-primary border-3">
                  <div className="text-muted small">Thực thể phát hiện</div>
                  <div className="fs-4 fw-bold text-primary mt-1">{result.entities?.length || 0}</div>
                </div>
              </div>
              <div className="col-6 col-md-3">
                <div className="glass-subpanel p-3 rounded-3 text-center border-start border-warning border-3">
                  <div className="text-muted small">Sự kiện &amp; Triggers</div>
                  <div className="fs-4 fw-bold text-warning mt-1">{result.events?.length || 0}</div>
                </div>
              </div>
              <div className="col-6 col-md-3">
                <div className="glass-subpanel p-3 rounded-3 text-center border-start border-success border-3">
                  <div className="text-muted small">Độ dài văn bản</div>
                  <div className="fs-4 fw-bold text-success mt-1">{result.word_count || result.input_text.split(/\s+/).length} từ</div>
                </div>
              </div>
              <div className="col-6 col-md-3">
                <div className="glass-subpanel p-3 rounded-3 text-center border-start border-info border-3">
                  <div className="text-muted small">Trạng thái</div>
                  <div className="fs-4 fw-bold text-info mt-1">Hoàn tất</div>
                </div>
              </div>
            </div>

            {/* Results Navigation Tabs */}
            <ul className="nav nav-pills gap-2 p-1 glass-subpanel rounded-3 mb-3 border border-secondary border-opacity-25">
              <li className="nav-item">
                <button
                  type="button"
                  className={`nav-link rounded-2 py-2 px-3 small fw-semibold ${activeTab === "visual" ? "active bg-primary text-white" : "text-light"}`}
                  onClick={() => setActiveTab("visual")}
                >
                  🌟 Đánh dấu trực quan
                </button>
              </li>
              <li className="nav-item">
                <button
                  type="button"
                  className={`nav-link rounded-2 py-2 px-3 small fw-semibold ${activeTab === "entities" ? "active bg-primary text-white" : "text-light"}`}
                  onClick={() => setActiveTab("entities")}
                >
                  📋 Bảng Thực thể ({result.entities?.length || 0})
                </button>
              </li>
              <li className="nav-item">
                <button
                  type="button"
                  className={`nav-link rounded-2 py-2 px-3 small fw-semibold ${activeTab === "events" ? "active bg-primary text-white" : "text-light"}`}
                  onClick={() => setActiveTab("events")}
                >
                  ⚖️ Sự kiện &amp; Vai trò ({result.events?.length || 0})
                </button>
              </li>
              <li className="nav-item">
                <button
                  type="button"
                  className={`nav-link rounded-2 py-2 px-3 small fw-semibold ${activeTab === "timeline" ? "active bg-primary text-white" : "text-light"}`}
                  onClick={() => setActiveTab("timeline")}
                >
                  ⏱️ Dòng thời gian
                </button>
              </li>
              <li className="nav-item">
                <button
                  type="button"
                  className={`nav-link rounded-2 py-2 px-3 small fw-semibold ${activeTab === "raw" ? "active bg-primary text-white" : "text-light"}`}
                  onClick={() => setActiveTab("raw")}
                >
                  💻 Dữ liệu JSON
                </button>
              </li>
            </ul>

            {/* TAB 1: VISUAL HIGHLIGHTING */}
            {activeTab === "visual" && (
              <div className="glass-subpanel p-4 rounded-3 border border-secondary border-opacity-25">
                {/* Visual filter mode */}
                <div className="d-flex flex-wrap justify-content-between align-items-center mb-3 pb-2 border-bottom border-secondary border-opacity-25 gap-2">
                  <div className="text-muted small">
                    <span>Chế độ hiển thị:</span>
                  </div>
                  <div className="btn-group btn-group-sm">
                    <button
                      type="button"
                      className={`btn btn-sm ${highlightMode === "all" ? "btn-info text-dark fw-bold" : "btn-outline-secondary text-light"}`}
                      onClick={() => setHighlightMode("all")}
                    >
                      Tất cả
                    </button>
                    <button
                      type="button"
                      className={`btn btn-sm ${highlightMode === "entities" ? "btn-info text-dark fw-bold" : "btn-outline-secondary text-light"}`}
                      onClick={() => setHighlightMode("entities")}
                    >
                      Chỉ Thực thể
                    </button>
                    <button
                      type="button"
                      className={`btn btn-sm ${highlightMode === "triggers" ? "btn-info text-dark fw-bold" : "btn-outline-secondary text-light"}`}
                      onClick={() => setHighlightMode("triggers")}
                    >
                      Chỉ Sự kiện
                    </button>
                  </div>
                </div>

                {/* Highlighted text container */}
                <div
                  className="p-3 rounded-3 bg-black bg-opacity-60 border border-secondary border-opacity-40 lh-lg text-light"
                  style={{ fontSize: "1.05rem", minHeight: "100px" }}
                >
                  {renderVisualText()}
                </div>

                {/* Legend Guide */}
                <div className="mt-3 pt-2">
                  <div className="text-muted small mb-2 fw-semibold">Chú giải màu sắc nhận diện:</div>
                  <div className="d-flex flex-wrap gap-2">
                    {Object.entries(ENTITY_CONFIG).map(([lbl, cfg]) => (
                      <span key={lbl} className={`badge ${cfg.badgeClass} px-2 py-1 small fw-normal`}>
                        {cfg.nameVi} ({lbl})
                      </span>
                    ))}
                    <span className="badge badge-trigger px-2 py-1 small">
                      Hành vi sự kiện (TRIGGER)
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 2: ENTITIES TABLE */}
            {activeTab === "entities" && (
              <div className="glass-subpanel p-3 rounded-3 border border-secondary border-opacity-25">
                {/* Search & Filter Bar */}
                <div className="row g-2 mb-3">
                  <div className="col-12 col-md-8">
                    <input
                      type="text"
                      className="form-control form-control-sm bg-dark text-white border-secondary"
                      placeholder="Tìm kiếm thực thể..."
                      value={searchEntity}
                      onChange={(e) => setSearchEntity(e.target.value)}
                    />
                  </div>
                  <div className="col-12 col-md-4">
                    <select
                      className="form-select form-select-sm bg-dark text-white border-secondary"
                      value={entityFilter}
                      onChange={(e) => setEntityFilter(e.target.value)}
                    >
                      <option value="ALL">Tất cả loại nhãn ({result.entities?.length || 0})</option>
                      {Object.entries(ENTITY_CONFIG).map(([lbl, cfg]) => {
                        const count = result.entities?.filter((e) => e.label === lbl).length || 0;
                        return (
                          <option key={lbl} value={lbl}>
                            {cfg.nameVi} ({lbl}) - [{count}]
                          </option>
                        );
                      })}
                    </select>
                  </div>
                </div>

                {/* Entities Table */}
                {filteredEntities.length === 0 ? (
                  <div className="text-center text-muted py-4">Không tìm thấy thực thể phù hợp với bộ lọc.</div>
                ) : (
                  <div className="table-responsive">
                    <table className="table table-dark table-hover table-striped align-middle mb-0 small">
                      <thead>
                        <tr className="border-secondary text-muted">
                          <th style={{ width: "5%" }}>#</th>
                          <th style={{ width: "35%" }}>Thực thể (Entity Text)</th>
                          <th style={{ width: "25%" }}>Loại nhãn (Label)</th>
                          <th style={{ width: "20%" }}>Ý nghĩa phân loại</th>
                          <th style={{ width: "15%" }}>Vị trí ký tự (Span)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredEntities.map((ent, idx) => {
                          const conf = ENTITY_CONFIG[ent.label] || { nameVi: ent.label, badgeClass: "bg-secondary" };
                          return (
                            <tr key={idx}>
                              <td className="text-muted">{idx + 1}</td>
                              <td>
                                <strong className="text-white">{ent.text}</strong>
                              </td>
                              <td>
                                <span className={`badge ${conf.badgeClass}`}>{ent.label}</span>
                              </td>
                              <td className="text-light">{conf.nameVi}</td>
                              <td className="font-monospace text-muted">
                                {ent.start} → {ent.end}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {/* TAB 3: EVENTS & ROLES TABLE */}
            {activeTab === "events" && (
              <div className="glass-subpanel p-3 rounded-3 border border-secondary border-opacity-25">
                {result.events?.length === 0 ? (
                  <div className="text-center text-muted py-4">
                    Không phát hiện sự kiện hình sự rõ ràng trong câu này.
                  </div>
                ) : (
                  <div className="d-flex flex-column gap-3">
                    {result.events?.map((ev, idx) => {
                      const evName = EVENT_TYPE_MAP[ev.event_type] || ev.event_type;
                      return (
                        <div
                          key={idx}
                          className="p-3 rounded-3 bg-black bg-opacity-40 border border-secondary border-opacity-30"
                        >
                          <div className="d-flex flex-wrap justify-content-between align-items-center mb-2 pb-2 border-bottom border-secondary border-opacity-25 gap-2">
                            <div className="d-flex align-items-center gap-2">
                              <span className="badge bg-danger px-2 py-1 fs-6">Sự kiện #{idx + 1}</span>
                              <span className="badge bg-warning text-dark fw-bold px-2 py-1">
                                {ev.event_type} - {evName}
                              </span>
                            </div>
                            <div className="small text-muted">
                              Động từ kích hoạt: <strong className="text-warning">"{ev.trigger?.text}"</strong> (Vị trí: {ev.trigger?.start}-{ev.trigger?.end})
                            </div>
                          </div>

                          {/* Arguments list */}
                          <div>
                            <div className="small text-muted mb-2 fw-semibold">Các vai trò tham gia sự kiện:</div>
                            {ev.arguments && ev.arguments.length > 0 ? (
                              <div className="row g-2">
                                {ev.arguments.map((arg, aIdx) => {
                                  const roleName = ROLE_MAP[arg.role] || arg.role;
                                  const entConf = ENTITY_CONFIG[arg.entity?.label] || { badgeClass: "bg-secondary" };
                                  return (
                                    <div key={aIdx} className="col-12 col-md-6">
                                      <div className="p-2 rounded bg-dark border border-secondary border-opacity-40 d-flex justify-content-between align-items-center">
                                        <div>
                                          <span className="badge bg-secondary me-2">{arg.role}</span>
                                          <span className="text-info small fw-bold">{roleName}:</span>
                                        </div>
                                        <div className="d-flex align-items-center gap-1">
                                          <strong className="text-white">{arg.entity?.text}</strong>
                                          <span className={`badge ${entConf.badgeClass} ms-1`} style={{ fontSize: "0.65rem" }}>
                                            {arg.entity?.label}
                                          </span>
                                        </div>
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            ) : (
                              <div className="text-muted small fst-italic">Chưa liên kết được vai trò lân cận trong mệnh đề.</div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {/* TAB 4: TIMELINE */}
            {activeTab === "timeline" && (
              <div className="glass-subpanel p-4 rounded-3 border border-secondary border-opacity-25">
                <div className="text-muted small mb-3 fw-semibold">
                  Diễn biến tiến trình các mốc thời gian trong vụ án:
                </div>
                {(() => {
                  const timeEntities = result.entities?.filter((e) => e.label === "TIME") || [];
                  if (timeEntities.length === 0) {
                    return (
                      <div className="text-center text-muted py-4">
                        Không phát hiện thực thể thời gian (TIME) trong bài viết này.
                      </div>
                    );
                  }
                  return (
                    <div className="position-relative ps-4 border-start border-info border-2 my-2">
                      {timeEntities.map((t, idx) => {
                        const startContext = Math.max(0, t.start - 50);
                        const endContext = Math.min(result.input_text.length, t.end + 90);
                        const snippet = result.input_text.substring(startContext, endContext);
                        return (
                          <div key={idx} className="mb-4 position-relative">
                            <span
                              className="position-absolute bg-info rounded-circle shadow"
                              style={{
                                width: "14px",
                                height: "14px",
                                left: "-32px",
                                top: "5px",
                              }}
                            />
                            <div className="bg-black bg-opacity-60 p-3 rounded-3 border border-secondary border-opacity-40">
                              <span className="badge bg-info text-dark fs-6 mb-2">
                                📅 {t.text}
                              </span>
                              <div className="text-light small lh-base">
                                ...{snippet}...
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  );
                })()}
              </div>
            )}

            {/* TAB 5: RAW JSON */}
            {activeTab === "raw" && (
              <div className="glass-subpanel p-3 rounded-3 border border-secondary border-opacity-25 position-relative">
                <button
                  type="button"
                  className="btn btn-sm btn-outline-info position-absolute top-0 end-0 m-3"
                  onClick={copyToClipboard}
                >
                  Sao chép JSON
                </button>
                <pre
                  className="text-light m-0 p-3 bg-black bg-opacity-80 rounded-3 small font-monospace overflow-auto"
                  style={{ maxHeight: "400px" }}
                >
                  {JSON.stringify(result, null, 2)}
                </pre>
              </div>
            )}

            {/* USER FEEDBACK SECTION */}
            <div className="mt-4 p-3 rounded-3 glass-subpanel border border-secondary border-opacity-25">
              <div className="d-flex flex-wrap justify-content-between align-items-center gap-2">
                <div>
                  <h6 className="text-white fw-bold m-0 d-flex align-items-center gap-2">
                    <span>💬 Đánh giá kết quả phân tích</span>
                  </h6>
                  <p className="text-muted small m-0 mt-1">
                    Góp ý của bạn giúp cải thiện độ chính xác của hệ thống nhận diện.
                  </p>
                </div>

                {!feedbackSubmitted ? (
                  <div className="d-flex align-items-center gap-2">
                    <button
                      type="button"
                      className={`btn btn-sm ${feedbackRating === "positive" ? "btn-success" : "btn-outline-success"} rounded-pill px-3`}
                      onClick={() => {
                        setFeedbackRating("positive");
                        handleSubmitFeedback();
                      }}
                    >
                      👍 Chính xác
                    </button>
                    <button
                      type="button"
                      className={`btn btn-sm ${feedbackRating === "negative" ? "btn-danger" : "btn-outline-danger"} rounded-pill px-3`}
                      onClick={() => setFeedbackRating("negative")}
                    >
                      👎 Cần chỉnh sửa
                    </button>
                  </div>
                ) : (
                  <span className="badge bg-success text-white px-3 py-2 rounded-pill">
                    ✓ Đã nhận phản hồi
                  </span>
                )}
              </div>

              {/* Negative Feedback Form */}
              {feedbackRating === "negative" && !feedbackSubmitted && (
                <div className="mt-3 pt-3 border-top border-secondary border-opacity-25">
                  <div className="row g-2 align-items-center">
                    <div className="col-12 col-md-4">
                      <select
                        className="form-select form-select-sm bg-dark text-white border-secondary"
                        value={feedbackCategory}
                        onChange={(e) => setFeedbackCategory(e.target.value)}
                      >
                        <option value="Thiếu thực thể">Bỏ sót thực thể quan trọng</option>
                        <option value="Gán sai loại nhãn">Nhận diện sai loại nhãn (Label)</option>
                        <option value="Sai loại sự kiện">Sai loại sự kiện (Event / Trigger)</option>
                        <option value="Sai vai trò quan hệ">Gán sai đối tượng / nạn nhân</option>
                        <option value="Khác">Lý do khác</option>
                      </select>
                    </div>
                    <div className="col-12 col-md-6">
                      <input
                        type="text"
                        className="form-control form-control-sm bg-dark text-white border-secondary"
                        placeholder="Mô tả cụ thể (Ví dụ: 'Nguyễn Văn A' phải là Nạn nhân chứ không phải Đối tượng...)"
                        value={feedbackComment}
                        onChange={(e) => setFeedbackComment(e.target.value)}
                      />
                    </div>
                    <div className="col-12 col-md-2 text-end">
                      <button
                        type="button"
                        className="btn btn-sm btn-primary rounded-pill w-100"
                        onClick={handleSubmitFeedback}
                      >
                        Gửi góp ý
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* MODAL 1: EXPORT DIALOG (Đáp ứng câu hỏi: nút export đưa ra dạng gì) */}
      {showExportModal && (
        <div
          className="modal show d-block"
          style={{ backgroundColor: "rgba(0, 0, 0, 0.75)", zIndex: 1060 }}
          tabIndex={-1}
        >
          <div className="modal-dialog modal-dialog-centered">
            <div className="modal-content glass-panel border border-secondary text-white rounded-4 shadow-lg">
              <div className="modal-header border-secondary border-opacity-25">
                <h5 className="modal-title fw-bold text-info d-flex align-items-center gap-2">
                  <span>💾 Tùy chọn xuất kết quả (Export)</span>
                </h5>
                <button
                  type="button"
                  className="btn-close btn-close-white"
                  onClick={() => setShowExportModal(false)}
                />
              </div>

              <div className="modal-body py-4">
                <p className="text-muted small mb-3">
                  Chọn định dạng file bạn muốn tải về để lưu trữ hoặc chia sẻ:
                </p>

                <div className="d-flex flex-column gap-3">
                  {/* Option 1: JSON */}
                  <div
                    className="p-3 rounded-3 bg-dark border border-secondary border-opacity-50 d-flex justify-content-between align-items-center"
                    style={{ cursor: "pointer", transition: "all 0.2s" }}
                    onClick={exportAsJSON}
                  >
                    <div>
                      <strong className="text-white d-block">1. Định dạng JSON (.json)</strong>
                      <span className="text-muted small">
                        Dành cho lập trình viên &amp; hệ thống API (chứa đầy đủ entities, triggers, vai trò và vị trí ký tự).
                      </span>
                    </div>
                    <button type="button" className="btn btn-sm btn-outline-info rounded-pill px-3">
                      Tải JSON
                    </button>
                  </div>

                  {/* Option 2: CSV / Excel */}
                  <div
                    className="p-3 rounded-3 bg-dark border border-secondary border-opacity-50 d-flex justify-content-between align-items-center"
                    style={{ cursor: "pointer", transition: "all 0.2s" }}
                    onClick={exportAsCSV}
                  >
                    <div>
                      <strong className="text-white d-block">2. Định dạng Bảng tính CSV (.csv)</strong>
                      <span className="text-muted small">
                        Dễ dàng mở bằng Microsoft Excel hoặc Google Sheets để thống kê và lập báo cáo dữ liệu.
                      </span>
                    </div>
                    <button type="button" className="btn btn-sm btn-outline-success rounded-pill px-3">
                      Tải CSV
                    </button>
                  </div>

                  {/* Option 3: TXT Report */}
                  <div
                    className="p-3 rounded-3 bg-dark border border-secondary border-opacity-50 d-flex justify-content-between align-items-center"
                    style={{ cursor: "pointer", transition: "all 0.2s" }}
                    onClick={exportAsReportTXT}
                  >
                    <div>
                      <strong className="text-white d-block">3. Báo cáo Vụ án Văn bản (.txt)</strong>
                      <span className="text-muted small">
                        Văn bản tổng hợp hồ sơ vụ án: Nội dung tóm tắt, Danh sách đối tượng, Nạn nhân, Tang vật và Tội danh.
                      </span>
                    </div>
                    <button type="button" className="btn btn-sm btn-outline-warning rounded-pill px-3">
                      Tải Báo cáo TXT
                    </button>
                  </div>
                </div>
              </div>

              <div className="modal-footer border-secondary border-opacity-25">
                <button
                  type="button"
                  className="btn btn-secondary rounded-pill px-4 btn-sm"
                  onClick={() => setShowExportModal(false)}
                >
                  Đóng
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 2: HISTORY DIALOG (Lưu trữ lịch sử phân tích) */}
      {showHistoryModal && (
        <div
          className="modal show d-block"
          style={{ backgroundColor: "rgba(0, 0, 0, 0.75)", zIndex: 1060 }}
          tabIndex={-1}
        >
          <div className="modal-dialog modal-dialog-centered modal-lg">
            <div className="modal-content glass-panel border border-secondary text-white rounded-4 shadow-lg">
              <div className="modal-header border-secondary border-opacity-25">
                <h5 className="modal-title fw-bold text-info d-flex align-items-center gap-2">
                  <span>🕒 Lịch sử các lần phân tích ({history.length})</span>
                </h5>
                <button
                  type="button"
                  className="btn-close btn-close-white"
                  onClick={() => setShowHistoryModal(false)}
                />
              </div>

              <div className="modal-body py-3" style={{ maxHeight: "60vh", overflowY: "auto" }}>
                {history.length === 0 ? (
                  <div className="text-center text-muted py-5">Chưa có lịch sử phân tích nào được lưu.</div>
                ) : (
                  <div className="d-flex flex-column gap-2">
                    {history.map((item) => (
                      <div
                        key={item.id}
                        className="p-3 rounded-3 bg-dark border border-secondary border-opacity-40 d-flex justify-content-between align-items-center gap-3"
                      >
                        <div style={{ flex: 1 }}>
                          <div className="d-flex align-items-center gap-2 mb-1">
                            <span className="badge bg-secondary small">{item.timestamp}</span>
                            <span className="badge bg-info text-dark small">
                              {item.result?.entities?.length || 0} thực thể
                            </span>
                            <span className="badge bg-warning text-dark small">
                              {item.result?.events?.length || 0} sự kiện
                            </span>
                          </div>
                          <div className="text-light small text-truncate" style={{ maxWidth: "520px" }}>
                            "{item.preview}"
                          </div>
                        </div>

                        <div className="d-flex align-items-center gap-2">
                          <button
                            type="button"
                            className="btn btn-sm btn-cyan rounded-pill px-3"
                            onClick={() => {
                              setInput(item.result.input_text);
                              setResult(item.result);
                              setShowHistoryModal(false);
                              showToast("Đã tải lại kết quả từ lịch sử lưu trữ!");
                            }}
                          >
                            Xem lại
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="modal-footer border-secondary border-opacity-25 d-flex justify-content-between">
                {history.length > 0 ? (
                  <button
                    type="button"
                    className="btn btn-sm btn-outline-danger rounded-pill px-3"
                    onClick={clearHistory}
                  >
                    🗑️ Xóa toàn bộ lịch sử
                  </button>
                ) : <span />}
                <button
                  type="button"
                  className="btn btn-secondary rounded-pill px-4 btn-sm"
                  onClick={() => setShowHistoryModal(false)}
                >
                  Đóng
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
