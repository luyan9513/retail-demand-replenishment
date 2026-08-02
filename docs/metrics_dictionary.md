# 指标字典

本文件是 `01_requirements_and_metrics.md` 的查阅版；所有比率均以小数存储、界面可格式化为百分比。

| 字段/指标 | 粒度 | 计算 | 解释与禁止误读 |
|---|---|---|---|
| `daily_qty` | SKU×日 | 有效正向行的数量之和 | 成交需求代理，不是未满足需求 |
| `daily_revenue` | SKU×日 | `quantity×unit_price` 求和 | 销售额，不是毛利/利润 |
| `demand_cv` | SKU | 日销量标准差/日销量均值 | 均值为零时为空；不是预测误差 |
| `nonzero_day_rate` | SKU | 日销量>0 天数/日历天数 | 识别间歇性 |
| `wape` | 模型×SKU/层级 | 绝对误差和/真实销量绝对值和 | 全零真实销量时为空 |
| `forecast_bias` | 模型×SKU/层级 | `(预测-真实)之和/真实销量绝对值和` | 负值=低估；不是缺货率 |
| `residual_sigma` | SKU×模型 | 回测残差总体标准差 | 安全库存的近似输入 |
| `reorder_point` | SKU×情景 | 提前期需求+安全库存 | 连续复核下的理论触发点 |
| `recommended_order_qty` | SKU×情景 | `ceil(max(0, ROP-假设库存))` | 不等于真实采购订单 |
