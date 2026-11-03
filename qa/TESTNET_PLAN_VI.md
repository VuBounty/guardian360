# GUARDIAN 360 V2.4.1 — BSC TESTNET REVOKE PLAN

**Chưa có giao dịch Revoke thật được xác minh. Không ký mainnet bằng ví giá trị lớn.**

## 1. Mạng thử nghiệm

- BNB Smart Chain Testnet — `chainId = 97 / 0x61`
- Token gas: `tBNB` (test token, không phải BNB thật)
- Explorer: https://testnet.bscscan.com/
- RPC nguồn tham khảo: https://bsc-testnet-dataseed.bnbchain.org
- Kiểm tra RPC bằng `python3 qa/check_bsc_testnet_rpc.py` từ Mac có Internet.

## 2. Điều kiện và cách kiểm thử thực tế

1. Tạo **ví thử nghiệm mới**, không dùng ví chứa tài sản.
2. Nhận tBNB testnet từ nguồn chính thức; không cung cấp seed phrase.
3. Tạo một ERC-20 testnet đã được xác minh, mint token mẫu.
4. Từ ví thử nghiệm, ký một giao dịch cấp allowance nhỏ cho spender thử nghiệm rõ danh tính.
5. Chạy read-only VERIFY và so sánh allowance trên BscScan.
6. Chạy preflight, so sánh account, chainId, `to`, `data`, amount=0, gas.
7. Chỉ với ví thử nghiệm, xác nhận giao dịch revoke trong MetaMask.
8. Kiểm tra `receipt.status=1`, đọc lại `allowance(owner,spender)=0`, hash và block trên explorer.
9. Thử negative cases: sai chain, sai owner, spender không hợp lệ, RPC timeout, tx bị từ chối, tx revert, thay đổi quyền giữa verify/preflight.
10. Chỉ khi tất cả PASS mới chuyển sang review bảo mật độc lập trước mainnet.

## 3. Phạm vi chưa được chứng nhận

- V2.4 backend cấu hình 4 chain **mainnet**; chưa tích hợp mạng BSC Testnet vào API `revoke/verify` như một mạng sản xuất. **Không tự thay chain ID của BSC mainnet thành 97**.
- Tiện ích `check_bsc_testnet_rpc.py` là **chẩn đoán đọc-only**, không ký/gửi tx.
- `eth_call` và `eth_estimateGas` không thay thế mô phỏng đầy đủ; token phi chuẩn có thể gặp lỗi.

Nguồn: https://docs.bnbchain.org/bnb-smart-chain/developers/wallet-configuration/
