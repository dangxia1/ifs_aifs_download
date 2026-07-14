# IFS stream/type 有效组合

> 来源: `ecmwf-opendata` 官方文档 + 源码分析

## IFS

| stream | type | 含义 | time |
|--------|------|------|------|
| `oper` | `fc` | 确定性大气预报 | 00z, 06z, 12z, 18z |
| `oper` | `tf` | 热带气旋路径 (仅在有气旋时有数据) | 00z, 06z, 12z, 18z |
| `wave` | `fc` | 确定性海浪预报 | 00z, 06z, 12z, 18z |
| `enfo` | `cf` | 集合控制预报 | 00z, 06z, 12z, 18z |
| `enfo` | `pf` | 集合扰动预报 (member 1-50) | 00z, 06z, 12z, 18z |
| `enfo` | `em` | 集合均值 | 00z, 12z |
| `enfo` | `es` | 集合标准差 | 00z, 12z |
| `enfo` | `ep` | 集合概率产品 (EFI/SOT) | 00z, 12z |
| `enfo` | `tf` | 集合热带气旋路径 (仅在有气旋时有数据) | 00z, 06z, 12z, 18z |
| `waef` | `cf` | 集合海浪控制预报 | 00z, 06z, 12z, 18z |
| `waef` | `pf` | 集合海浪扰动预报 | 00z, 06z, 12z, 18z |

> **stream 变更说明 (2026-05-12 起)**: 06z/18z 数据现已统一使用 `stream=oper`(大气场) 和 `stream=wave`(海浪场)，取代了原先的 `scda`/`scwv`。`scda`/`scwv` 仅在拉取 2026-05-12 之前的历史数据时由库自动映射使用，用户无需手动指定。

## AIFS

| model | stream | type | time |
|-------|--------|------|------|
| `aifs-single` | `oper` | `fc` | 00z, 06z, 12z, 18z |
| `aifs-ens` | `enfo` | `cf` / `pf` (member 1-50) | 00z, 06z, 12z, 18z |

> AIFS 模型的 stream/type 由库自动设置，用户传参无效。