# H5 selection-event turnover audit

只读审计，不新增 trial。

- 542 个 H5 long 目标事件；
- 208 个事件改变了持币集合，334 个事件集合不变；
- long target L1 turnover 合计 129.7632x；
- same-set 事件贡献 59.2774x，占 **45.68%**；
- same-set 的 gross 变化部分约 39.0910x，relative weight tilt 部分约 32.2448x；
- 两部分有方向重叠，因此不能用二者简单相加解释 total L1。

结论：如果只在同持币集合事件中保留旧相对权重、仍按新 target gross 做统一缩放，可以在不跳过选币
和 gross 风险变化的前提下，消除相当一部分 per-asset relative-weight 换手。
