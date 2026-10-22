# 六爻纳甲 Skill

根据六次三枚铜钱的三位二进制记录排六爻纳甲卦，并根据占问对象和具体目标选择用神候选。固定计算由 Python 完成，问题理解与传统象义解释由模型完成。

## 文件

- `SKILL.md`：技能入口与工作流程。
- `references/rules.md`：装卦规则与来源。
- `references/yongshen.md`：用神与占问对象映射。
- `scripts/liuyao_cli.py`：命令行计算器。
- `scripts/tests/test_liuyao_cli.py`：回归测试。
- `examples/job_offer.json`：合成输入示例。
- `agents/openai.yaml`：技能界面元数据。

## 输入约定

每次记录三枚钱的币面，连续摇六次。`1` 为预先约定的阳面、计 3 分；`0` 为阴面、计 2 分。第一组为初爻，最后一组为上爻。

| 记录 | 分数 | 爻态 | 变化 |
|---|---:|---|---|
| `000` | 6 | 老阴 | 阴变阳 |
| `001`、`010`、`100` | 7 | 少阳 | 不动 |
| `011`、`101`、`110` | 8 | 少阴 | 不动 |
| `111` | 9 | 老阳 | 阳变阴 |

```json
{
  "coins": ["000", "001", "011", "111", "010", "101"],
  "question": "我这次应聘是否会被录用？",
  "topic": "career_position",
  "subject_relation": "self"
}
```

`coins` 必须为六个三位字符串。用户自然语言问题由模型按规则映射到 `topic` 与 `subject_relation`；脚本关键词只提供建议。需要历法时，另传真实起卦时间 `cast_time`，采用带 UTC 偏移量的 ISO 8601 格式。当前历法统一使用北京时间 UTC+08:00，默认零点换日，可显式选用 `zi_start` 在 23 点换日。

## 运行

需要 Python 3.10 或更新版本。基础装卦无需第三方依赖；计算月建、日辰、六神与旬空时需要安装锁定版本的历法依赖：

```sh
python -m pip install -r scripts/requirements.txt
python scripts/liuyao_cli.py --input examples/job_offer.json --output -
```

输入和输出均支持 `-`，表示标准输入或标准输出。运行测试：

```sh
python -B -m unittest discover -s scripts/tests -v
```

仓库保存通用源码。各机器使用自己的 Python 环境；本机专用 Windows 启动器和 Python 运行时不随仓库保存。

## 解释范围

计算本卦、变卦、八宫、世应、纳甲、六亲、伏神及用神候选；有真实起卦时间和历法依赖时，增加历法信息。变爻六亲始终参照本卦宫五行。

旺衰、生克有效性、暗动、合局、应期与事件判断属于后续解释，计算器不会自动确认。六爻作为传统文化参考，不保证现实事件、具体日期或概率。
