"""Schema luồng 2 (khớp với docs/annotation_guidelines.md và Label Studio)."""

ENTITY_TYPES = ("PERSON", "ORGANIZATION", "LOCATION", "TIME", "MONEY", "DRUG", "PRODUCT", "CRIME")

EVENT_TYPES = ("LUA_DAO", "MA_TUY", "BAO_LUC", "CUOP_TROM", "BAT_GIU", "THU_GIU", "KHOI_TO", "XET_XU")

# Vai trò -> các nhãn thực thể được phép nối tới
ROLE_TYPES = {
    "DOI_TUONG": {"PERSON", "ORGANIZATION"},
    "NAN_NHAN": {"PERSON", "ORGANIZATION"},
    "CO_QUAN": {"ORGANIZATION"},
    "TAI_SAN": {"MONEY", "PRODUCT"},
    "TANG_VAT": {"DRUG", "PRODUCT"},
    "HUNG_KHI": {"PRODUCT"},
    "TOI_DANH": {"CRIME"},
    "MUC_AN": {"TIME", "MONEY"},
    "THOI_GIAN": {"TIME"},
    "DIA_DIEM": {"LOCATION"},
}
ROLES = tuple(ROLE_TYPES)

CRIME_EVENTS = {"LUA_DAO", "MA_TUY", "BAO_LUC", "CUOP_TROM"}
PROCEDURAL_EVENTS = {"BAT_GIU", "THU_GIU", "KHOI_TO", "XET_XU"}
