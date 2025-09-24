# 🎶 Hệ thống Đăng ký Vé Concert cho Sinh viên (Miễn phí)

## 📌 Giới thiệu
Đề tài xây dựng hệ thống đăng ký vé concert trực tuyến **miễn phí cho sinh viên**, hỗ trợ quản lý bởi **Đoàn trường** và **Admin tổng**.  
Hệ thống giúp sinh viên dễ dàng đăng ký vé, hạn chế gian lận và hỗ trợ ban tổ chức quản lý vé minh bạch, công bằng.

---

## 🎯 Chức năng chính
### 👩‍🎓 Sinh viên
- Đăng ký/đăng nhập bằng tài khoản sinh viên.
- Xem thông tin concert (thời gian, địa điểm, số lượng vé).
- Đăng ký vé miễn phí (giới hạn theo quy định).
- Nhận vé điện tử (mã QR).

### 🏫 Đoàn trường
- Quản lý danh sách sinh viên đã đăng ký.
- Quản lý concert (tạo, sửa, xóa sự kiện).
- Xác nhận hoặc từ chối đăng ký vé.
- Xuất báo cáo danh sách sinh viên tham dự.

### 🔑 Admin
- Quản lý concert (tạo, sửa, xoá sự kiện).
- Quản lý tài khoản Đoàn trường.
- Quản lý số lượng vé, thống kê tổng quan hệ thống.

---

## 🚀 Chạy dự án (chạy file run.py)

---

📝 **Hướng dẫn đăng ký**
👉 Đăng ký tài khoản sinh viên

Truy cập trang chủ hệ thống tại http://localhost:5000.
Nhấn vào nút "Đăng ký" (nếu chưa có tài khoản).
Điền thông tin yêu cầu:

Tên đăng nhập: Tên duy nhất (thường là mã số sinh viên).
Mật khẩu: Mật khẩu cá nhân (tối thiểu 6 ký tự).
Họ tên: Họ và tên đầy đủ.
Email: Địa chỉ email cá nhân (tùy chọn).
Mã số sinh viên: Mã số sinh viên của bạn.
CCCD: Số chứng minh nhân dân/căn cước công dân (tùy chọn).


Nhấn "Đăng ký" để hoàn tất. Hệ thống sẽ gửi thông báo xác nhận (nếu có email).
Sau khi đăng ký thành công, đăng nhập bằng tài khoản vừa tạo.

---

👉 **Đăng ký vé concert**

Đăng nhập vào hệ thống với tài khoản sinh viên.
Vào phần "Sự kiện" để xem danh sách concert hiện có.
Chọn concert bạn muốn tham gia và nhấn "Đăng ký vé".
Kiểm tra thông tin đăng ký (thời gian, địa điểm, số lượng vé còn lại).
Xác nhận đăng ký. Nếu thành công, bạn sẽ nhận vé điện tử (mã QR) trong phần "Vé của tôi".

Lưu ý: Mỗi sinh viên chỉ được đăng ký số lượng vé theo quy định (thường là 1 vé/concert).
