# GUARDIAN 360 V1.1.1 — BIÊN BẢN ĐỐI CHỨNG / BENCHMARK

**Phương pháp:** so sánh kết quả quét một địa chỉ ví công khai từ GUARDIAN 360 với dữ liệu do người kiểm thử tự tra cứu trên DeBank và Revoke.cash. KHÔNG gửi seed phrase, private key hoặc kết nối ví để đối chứng. Mọi phát hiện từ ảnh, JSON được đánh dấu nguồn riêng.

| Hạng mục | GUARDIAN 360 V1.1 | Công cụ độc lập | Kết quả | Giới hạn |
|---|---|---|---|---|
| BSC EIP-7702 delegate `0x63c0…DAE32B` | Phát hiện qua RPC | Revoke.cash ảnh người dùng gửi, nhãn `MetaMask` | **KHỚP** | Xác nhận địa chỉ; không kiểm toán mọi quyền ủy quyền |
| Danh tính delegate | Chưa phân loại trong V1.1 | MetaMask tài liệu chính thức + Revoke.cash | **CẬP NHẬT V1.1.1** | Chỉ so khớp địa chỉ công bố |
| BSC ERC-20 approvals = 0 tìm thấy | Indexer 401, RPC logs limit exceeded | Revoke.cash tab Token Approvals | **CHƯA ĐỐI CHỨNG** | 0 tìm thấy **KHÔNG** có nghĩa 0 tồn tại |
| ETH ERC-20 token tự gọi `ETH`, lượng cực lớn | 1 token dị thường, chưa có giá xác minh | DeBank asset/token view | **CHƯA ĐỐI CHỨNG** | Không được tính là native ETH / USD có giá trị |
| Tổng tài sản USD 4 mạng | Dữ liệu USD một phần | DeBank portfolio | **CHƯA ĐỐI CHỨNG** | Nhà cung cấp dữ liệu, spam filter, vị thế DeFi có thể khác nhau |
| Base/Arbitrum permissions | Blockscout 403 | Revoke.cash từng mạng | **CHƯA ĐỐI CHỨNG** | Dữ liệu từ V1.1 chưa đủ độ bao phủ |

Nguồn kiểm tra danh tính EIP-7702:
- MetaMask: https://support.metamask.io/configure/accounts/what-is-a-smart-account/
- Ethereum.org: https://ethereum.org/roadmap/pectra/7702/
- Revoke.cash: https://revoke.cash/ (dùng tab Delegations rồi Approvals trên từng chain)
- DeBank: https://debank.com/ (dùng chế độ tìm bằng địa chỉ công khai)

**Quy trình chấp nhận:**
1. Chạy V1.1.1 trên Mac và xuất báo cáo JSON.
2. Dùng DeBank để đối chiếu *danh sách tài sản*, không chỉ tổng USD. Ghi chain, token contract và số dư.
3. Dùng Revoke.cash để đối chiếu *Token Approvals* trên BSC/ETH/Base/Arbitrum; kiểm tra cả Delegations (EIP-7702).
4. Đánh dấu các sai lệch: thiếu token, token giả, quyền bị bỏ sót, RPC lỗi, định giá thiếu. Không công bố nhãn SAFE khi không có dữ liệu đủ.
5. Chỉ sau khi kiểm tra thực địa / live trên Mac, đánh giá khả năng công bố bản beta.

*Không phân phối ảnh chụp cá nhân hoặc JSON quét ví của người dùng trong mã nguồn công khai.*
