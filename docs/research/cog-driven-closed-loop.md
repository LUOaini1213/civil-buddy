# 重心驱动自动闭环（P0）

保持 **全自动**，不可出运时打回重排，不等人点。

## 方法来源（行业/论文/工程惯例）

1. **Multi-start + CoG 选优**：多策略试装，用 mid50/balance 选赢家（非 LLM 坐标）  
2. **重货中段优先序**：重货先装进 25%–75% 柜长（CTU 60/50）  
3. **再平衡模式 `cog_rebalance`**：放置词典序把 mid50 罚分提到最高  
4. **最差柜决策**：多柜时以 **最低 mid50 柜** 触发 risk/replan，不是只看柜1  
5. **R0 校验门**：`validate_cog_r0` — mid50≥60%、纵偏≤5%、横偏≤5%、竖向≤55%（每柜+最差柜）  
6. **R1a 刚性平移**（EasyCargo）：整坨移向质量中心  
7. **R1b 横向镜像**：整坨绕柜宽中线翻转，修左右偏心  
8. **R4 局部修理**：`tools/cog_repair.py` 重货↔轻货 swap + 中段滑动  

管道：

```
装载(多柜重量配额+重货先)
  → multi_start
  → R0/R1 → R2条带 → R4 → R3
  → LNS 最差柜重装 → 横偏半柜/y条带
  → R0/R1 收口 → 评估/风险
```

- **LNS** `cog_lns.py`：卸两端/轻货后置 → 重货中段 EP 重装  
- **配额** `bin3d`：多柜按重量均分，柜内重货优先  
- **横偏** `cog_lateral.py`：左右半柜镜像 + y 条带重排

### 出运停损

| mid50 | 行为 |
|-------|------|
| &lt; 0.40 | 硬拒 + 自动 replan |
| 0.40–0.55 | 最多 1 轮软 replan，之后 WARN 可出运 |
| ≥ 0.55 | 不再因 mid50 空转 replan（理想 60% 仅提示） |

## 自动闭环

```
loader(multi_start含 mid_heavy/cog_rebalance)
  → evaluator: 最差 mid50<60% → need_replan=True
  → critic: packing_options.cog_rebalance=True → 再 loader
  → risk: mid50 硬拒 → auto_replanable → 外环再打回 planner
```

## 关键 options

```python
packing_options = {
  "cog_aware": True,
  "cog_rebalance": True,  # 再平衡加重
  "multi_start": True,
  "prefer_stack": True,
}
```

## 回归

```bash
python scripts/test_cog_rebalance_loop.py
python scripts/test_stack_prefer.py
```
