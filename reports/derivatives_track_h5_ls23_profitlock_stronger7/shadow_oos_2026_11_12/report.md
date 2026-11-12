# LS43 Shadow Diagnostic 2026-11-12

- window: 2026-09-22 → 2026-11-11 (51 rows / 50 metric returns)
- cost: 20bps; Bitget mark; exact/zero funding
- **not independent OOS**: this window was inspected before LS43 registration

| funding | strategy | multiple | Sharpe | MDD | trims | confirmed recipients | redistributed | cash |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| zero | L125 | 0.9484x | -0.2743 | -17.4670% | 0 | 0 | 0.0000 | 0.0000 |
| zero | LS23 | 0.9403x | -0.5584 | -17.4712% | 8 | 0 | 0.0000 | 0.0000 |
| zero | LS42 | 0.9220x | -0.7874 | -17.4712% | 8 | 0 | 0.7148 | 0.9365 |
| zero | LS43 | 0.9403x | -0.5584 | -17.4712% | 8 | 0 | 0.0000 | 1.6513 |
| exact | L125 | 0.9440x | -0.3270 | -17.6505% | 0 | 0 | 0.0000 | 0.0000 |
| exact | LS23 | 0.9365x | -0.6125 | -17.6547% | 8 | 0 | 0.0000 | 0.0000 |
| exact | LS42 | 0.9183x | -0.8405 | -17.6547% | 8 | 0 | 0.7148 | 0.9365 |
| exact | LS43 | 0.9365x | -0.6125 | -17.6547% | 8 | 0 | 0.0000 | 1.6513 |

LS43 在该窗口没有任何合格接收者，因此与 LS23 完全一致，并避免了 LS42 向 ZEC 再分配后的损失。
该窗口不能用于 promotion；需要预注册后的新 12 个月 OOS。

Research output only; not an order or a live approval.
