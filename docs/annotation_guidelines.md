# Quy ước gán nhãn

Áp dụng cho tập test gold (150 câu). Đơn vị gán nhãn là **một câu**: chỉ dựa vào thông tin có trong câu đó.

## A. Thực thể (8 nhãn)

| Nhãn | Gán | Không gán |
|---|---|---|
| PERSON | Tên riêng, tên viết tắt (`T`, `L.T. V`, `Nguyễn Hùng M`) | Chức danh/cấp bậc (`Thiếu tá`, `BS`, `nguyên Tổng giám đốc`); cách gọi chung (`bị cáo`, `nạn nhân`, `đối tượng`); biệt danh (`đại ca`) |
| ORGANIZATION | Đơn vị có tên cụ thể, lấy trọn cả địa danh trong tên (`Công an huyện Kim Bình`, `TAND tỉnh Gia Lai`, `Bộ Công an`, `Quốc hội`, `phòng Cảnh sát hình sự`) | `công an`, `cảnh sát`, `cơ quan điều tra`, `HĐXX`, `Ban chuyên án`, `ngân hàng` đứng một mình; loại hình chung (`công ty đại chúng`) |
| LOCATION | Địa danh, giữ cấp hành chính đứng trước (`tỉnh Vân Nam`, `TP. Thủ Dầu Một`); công trình có tên (`Trạm biến áp 110 Hưng Nguyên`, `cụm cảng Cái Mép`, `toà nhà Golden Palm`). Chuỗi địa chỉ có dấu phẩy thì **tách** thành nhiều nhãn | Vùng chung (`Bắc`, `Nam`); quốc tịch (`người Lào`); `TP` đứng một mình |
| TIME | Mốc thời gian cụ thể, gồm buổi (`rạng sáng 17/10`, `chiều ngày 12/6`, `mùng 2 Tết`); **mức án** (`3 năm tù`, `tử hình`, `11 năm tù giam`) | Thời gian tương đối (`khoảng một tuần sau`, `cách đây 15 năm`, `mới được 3 tháng`); năm sinh (`SN 1965`); số hiệu văn bản (`kết luận số 10/2017`) |
| MONEY | Số tiền kèm đơn vị (`1,3 tỉ đồng`, `200.000 đ`) | Phần trăm, cổ phần (`18% cổ phần`); đơn vị tính đi kèm (`/lá`) |
| DRUG | Mọi lần nhắc chất ma túy, lấy kèm số lượng (`4 gói heroin`, `1,5kg ma túy`, `ma túy đá`) | `ma túy` nằm trong tên đơn vị (`Cục Phòng, chống ma túy…`) |
| PRODUCT | Đồ vật liên quan vụ việc: tang vật, tài sản bị chiếm đoạt, hung khí (`1 khẩu súng`, `dao`, `xe tay ga hiệu Ari Blade`) | Hàng hóa nói chung trong câu không có sự kiện (`thịt heo`); đồ chứa (`túi ni lông`, `ba lô`) |
| CRIME | Tên tội cụ thể sau chữ "tội", hoặc trong ngoặc kép sau "hành vi" (`Cướp tài sản`, `giết người`, `trộm cắp tài sản`). **Không** lấy chữ "tội" | Mô tả mục đích (`chuyển tiền trái phép`); lĩnh vực luật (`phòng chống tham nhũng`); lời tố (`vi phạm bản quyền`) |

Quy tắc chung:

- **Gán mọi lần xuất hiện** của thực thể trong câu.
- **Không lấy dấu câu** ở hai đầu span (dấu chấm cuối câu, ngoặc, dấu phẩy).
- Thực thể **không lồng nhau**. Gặp cách viết gộp như `công an hai huyện Tĩnh Gia và Như Thanh` thì gán cả cụm là một ORGANIZATION.

## B. Trigger (8 loại sự kiện)

1. **Chỉ gán sự kiện đã hoặc đang xảy ra.** Không có gán khi sự kiện mới là ý định, kế hoạch, giả định, phủ định, nghi vấn hay suy đoán: `nảy sinh ý định lừa đảo`, `quyết tâm truy bắt`, `để tiến hành khởi tố`, `nếu bắn chết`, `có thể đã chiếm đoạt`, `nằm trong kế hoạch… bắt giữ`, `liên quan… hay không`.
2. **Trigger là động từ chính**, không có lấy phần bổ nghĩa hay kết quả: `đâm` (không lấy `đâm liên tiếp nhiều nhát`, `đâm chết`), `tàng trữ` (không lấy `tàng trữ chất ma túy`). Động từ ghép thì lấy toàn bộ: `giết hại`, `bắt quả tang`, `bắt tạm giam`, `khống chế bắt giữ`, `lừa đảo chiếm đoạt`.
3. **Một sự kiện nhắc nhiều lần trong câu thì chỉ gán 1 trigger**, chọn chỗ khẳng định rõ nhất (`phát hiện bị lừa đảo`, `khởi tố vụ án, khởi tố bị can` → chỉ chữ "khởi tố" đầu). Hai hành động khác nhau thì gán riêng (`xét xử` và `tuyên phạt`; `hành hung` và `bắn`).
4. **Danh từ chỉ người không phải trigger**: `Trộm đột nhập…` → trigger là `đột nhập`.
5. **Thủ đoạn lừa không có chữ "lừa"**: gán LUA_DAO cho động từ chính của thủ đoạn (`giả giọng`, `tự xưng`, `nhắn tin` xin tiền, `đưa ra` thông tin gian dối).
6. **BAO_LUC** chỉ gồm hành vi xâm hại thân thể: giết, đâm, chém, đánh, bắn, ném (lựu đạn), xô xát có hung khí, chống trả bằng vũ khí, hiếp dâm, `tước đoạt / tước đi` tính mạng.
7. **Không phải trigger:** điều tra, truy xét, xác minh, truy đuổi, truy nã, tố giác, cáo buộc, khai, phạm tội, vi phạm, đe dọa, cãi vã, kiểm tra, triệt phá (chung chung), xử phạt / lập biên bản **hành chính**, phong tỏa tài sản, hối lộ, ký khống, làm giả giấy tờ (khi chưa dùng để lừa), vụ kiện dân sự, nghiện ma túy, dương tính ma túy, giết mổ gia súc, đánh bắt (cá).
8. **Từ dễ nhầm:** `bắt` trong `bắt cóc` → không phải BAT_GIU (vụ bắt cóc thật thì gán BAO_LUC cho cả cụm); `bắt` trong `đánh bắt`, `bắt đầu` → không gán; `truy bắt thành công` → BAT_GIU, còn `truy bắt` đơn thuần thì không.

## C. Quan hệ (vai trò)

1. **Luôn nối từ trigger sang thực thể.** Câu không có trigger thì không có quan hệ.
2. **Chỉ nối tới thực thể có nhãn.** Người không có tên (`bị cáo`, `hai anh em`, `mẹ`) thì không nối.
3. **Mỗi vai trò nối tới thực thể gần trigger nhất, trong cùng mệnh đề.** Tên lặp lại ở mệnh đề khác thì không nối lại.
4. **DIA_DIEM** là nơi xảy ra sự kiện. **Không** nối địa danh đứng sau `quê`, `ngụ`, `trú`, `ở` (nơi cư trú), và không nối địa danh chỉ là mục đích (`để tiêu thụ tại Việt Nam`).
5. **THOI_GIAN** chỉ nối khi mốc thời gian là lúc xảy ra sự kiện, không nối ngày đưa tin (`Ngày 16-11, … cho biết`).
6. **CO_QUAN** là đơn vị trực tiếp thực hiện hành động tố tụng. Nơi làm việc của bị can thì không nối.
7. **TANG_VAT** là vật bị thu giữ hoặc vật của vụ ma túy. **HUNG_KHI** là vũ khí dùng để gây án. **TAI_SAN** là tài sản bị chiếm đoạt (giá chào bán không tính).
8. **MUC_AN** nối từ XET_XU tới mức án (TIME/MONEY). **TOI_DANH** nối tới CRIME.

## D. Quy trình kiểm tra

- Sau mỗi lần export: chạy `check_annotations.py`, xem `*_issues.csv`, sửa các lỗi thật (quan hệ ngược chiều, sai kiểu vai trò, span dính dấu câu…).
- Kết quả kiểm tra cuối trên tập test: 17/150 câu có cảnh báo. Sau khi xem từng câu, chỉ 1 câu là lỗi thật và đã được sửa.
