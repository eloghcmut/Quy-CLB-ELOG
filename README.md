# Web quản lý thu chi cá nhân / nhóm

Project Flask gồm 3 trang:

- Tiền vào
- Tiền ra
- Tổng quan

Bản này chạy được local bằng SQLite và deploy được lên Render bằng PostgreSQL.

## Chạy local

```bash
pip install -r requirements.txt
python3 app.py
```

Mở:

```text
http://127.0.0.1:5000
```

Khi chạy local, app lưu dữ liệu vào file `finance.db`.

## Deploy lên Render

Bản này đã có:

- `gunicorn` để chạy production
- `render.yaml` để Render tự tạo web service + PostgreSQL database
- hỗ trợ biến môi trường `DATABASE_URL`
- hỗ trợ mật khẩu web bằng biến môi trường `APP_PASSWORD`

### Start command

```bash
gunicorn app:app
```

### Build command

```bash
pip install -r requirements.txt
```

### Environment variables cần có trên Render

- `DATABASE_URL`: Render tự nối từ PostgreSQL nếu dùng `render.yaml`
- `SECRET_KEY`: Render tự generate nếu dùng `render.yaml`
- `APP_PASSWORD`: tự nhập mật khẩu để bảo vệ web

Lưu ý: Free Render Postgres có thể hết hạn theo chính sách hiện tại của Render. Nếu dùng lâu dài, nên nâng cấp database hoặc dùng database bền vững khác.
