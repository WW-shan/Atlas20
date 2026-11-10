# 双边轮动第五轮：Bottom-Quincile + 75% short buffer（2026-11-10）

## 结论

**拒绝：仍发生 2 次强平。** 预注册文件：`docs/superpowers/specs/2026-11-10-cross-sectional-basket-buffer-round5-design.md`。

R5 保持 R4 的选币、14D/7D、4 币等权和 0.25x 总空头，只把空头 buffer 从 50% 提高到 75%。

| trial | 终值 | Sharpe | MDD | 强平 | short buffer |
|---|---:|---:|---:|---:|---:|
| L125 基线 | 40.2200x | 1.7330 | -40.6506% | 0 | 0.50 |
| `PR2026-11-RS5-X-WEAK4-SB75` | 51.2754x | 1.8817 | -41.5294% | **2** | 0.75 |

强平：2023-07-13 XRP（+75% 左右）和 2024-12-03 TRON；提高 buffer 只是推后强平价，没有消除挤压尾部。预注册声明若 75% 仍失败就停止 buffer 搜索，因此不测试 80/90%。

## 判定

拒绝；bottom-4 裸空头不能通过保证金 buffer 解决。
