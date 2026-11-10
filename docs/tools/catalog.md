# Alteryx → Python 工具映射与逐节点验证

仅用于本地学习和实践。映射使用公开标识、配置及独立编写的实现。

## 验收规则

默认使用 `behavioral`：

- 两边成功：逐节点、逐输出锚点比较字段、完整记录、行列顺序、重复记录、空值和实际数值。
- 两边失败：不要求异常类、报错语言或文字一致；仍核对各节点执行状态和已经成功的上游结果。
- 一边成功、一边失败，或成功输出不同：`mismatch`。
- 少节点/输出、没有运行证据或尚未确认：`incomplete`。
- 缺实现、依赖、模型、数据集、服务权限或许可证：`blocked`，不能靠抛异常冒充等价失败。

例如，同一 Filter 节点的原生 `Unknown variable "missing_field"` 与 Python
`KeyError('missing_field')` 均失败，符合本次验收规则。
`strict` 是可选附加检查，要求物理字段元数据和诊断文本，不改变默认规则。

## 当前范围：2026-11-09

2026-11-10 已补齐通用 CLI 建图、节点模板及编辑、Question/Action 绑定、标准/批次/迭代宏本地 profile、可直接执行并嵌入本地宏的 Python，以及逐节点证明清单。操作见 [Workflow CLI](../workflow_cli.md)，验收见 [CLI 报告](evidence/2026-11-10-cli/README.md)。这些新增能力不改变下面的映射/资源缺口数量，也不把未实测的工具列为已证明等价。

| 项目 | 结果 |
| --- | --- |
| 本机 Designer | 2025.1.2.165，原始引擎 |
| 官方 current 清单 | 323 个分类条目，321 个唯一 XML ID，29 类 |
| 官方 ID 映射 | 323/323 条目、321/321 ID；本地 catalog 共 347 条 |
| 有执行函数的条目 | 226/323，包含有明确边界的本地候选实现 |
| 缺少前提或执行适配器 | 97/323，明确抛出 ToolUnavailableError |
| 静默透传占位 | 0 |
| 原生 Workflow 实测 | 6 个；30/30 节点输入/输出数据检查通过，含两边失败案例 |
| 所有工具、配置、输入的语义等价 | 尚未完成 |

[官方清单](https://help.alteryx.com/designer/current/en/tools/designer-tools-list.html)
列出了 XML ID 和使用角色；[固定快照](official_inventory.json)保存来源、时间和 HTML SHA-256。
[逐工具覆盖表](official_coverage.json)列出所有官方条目、执行 profile、解析器与运行时状态。
current 与本机 2025.1 可能不同，也不包括未来工具或任意第三方插件。

新增实现涉及[小宏](local_macros.md)、[静态自定义宏](static_macros.md)、
[In-DB](indb.md)、[预测](predictive.md)、[统计](statistics_extra.md)、
[扩展建模](ml_extra.md)、[生存分析](survival.md)、[时间序列](timeseries.md)、
[媒体](local_media.md)、[文本模型](text_models.md)、[视觉](local_vision.md)、
[本地运行时](local_runtimes.md)。
各文档记录本地配置与输出边界。
本地 sklearn/statsmodels 模型字节和原生 R 模型不是相同格式；
本地数值报告也不等于原生报告渲染。函数可调用不能证明全部原生配置兼容。

## 在 Designer 中手动逐节点核对

这条路线适用于你通过菜单创建、保存的 Workflow，不需要 Engine API。

```powershell
Set-Location E:\Automation\Alteryx2Python
uv sync --extra local --extra parity --extra test --extra nlp --extra notebooks
.\.venv\Scripts\python.exe -m alteryx2python.parity review-bundle C:\path\your-workflow.yxmd --output-dir reports\parity\my-review
.\.venv\Scripts\python.exe reports\parity\my-review\workflow.py
```

| 核对包文件 | 用途 |
| --- | --- |
| original.yxmd | 原文件逐字节备份 |
| native-review.yxmd | 在 Designer 打开的副本；相对文件/本地宏路径改为绝对路径，重写记录保存在 bundle.json |
| workflow.py | 对应 Workflow 的 Python 图构建代码，通过正式运行时执行 |
| node-map.md/json | 每个原节点 ID、实际 Python 函数和执行 profile |
| python-runtime.local.json | 本地模型/解释器等配置；不提交凭据 |
| python-results/capture.json | 完整 Python 逐节点输入、输出和状态 |
| python-results/*.csv/*.json | 每个输出锚点的数据；图片单元格另导出 PNG |
| review.json | 由你填写原生状态及逐节点结果是否相同 |

1. 在 Designer 用 **File → Open** 打开 native-review.yxmd 并运行。
2. 运行 workflow.py，对照 Designer 中每个节点输出锚点和对应 CSV/JSON。
3. 填写 review.json 的 Workflow native_status 和每个节点的 success、failed 或 not_run；成功节点确认后填写 outputs_equal: true/false。
4. 执行检查。未填写的节点不会通过；两边失败不要求复制同一报错文字。

```powershell
.\.venv\Scripts\python.exe -m alteryx2python.parity review-check reports\parity\my-review
```

这是**人工检查证据**，报告标记 evidence_method: human_review，
不会伪称自动采集了原生输出。保持两次运行的输入数据不变；
修改 Workflow、配置或输入后重新生成包。
CSV 的 <NULL> 只是显示标记；区分同名字符串、空串、二进制或模型时以 typed JSON 为准。
代码、运行时、原工作流、Designer 副本或运行配置变化使原确认失效。
重跑 Python 保留 review.json，新待确认表写入 review-next.json，重新核对后替换。

已准备并执行的示例包：`reports/parity/manual-count-select/`。
包含 Text Input → Count Records 和 Select Records 分支；人工确认仍为 pending，留给你检查。

## 原生节点导出后自动比较

对于已适配的本地表格工具，可在每个输出锚点挂接 YXDB 导出，手动运行后自动比较：

```powershell
.\.venv\Scripts\python.exe -m alteryx2python.parity prepare examples\parity\local_macros.yxmd --output-dir reports\parity\new-native-run
# 在 Designer 打开 new-native-run/instrumented.yxmd，运行并观察真实结果。
.\.venv\Scripts\python.exe -m alteryx2python.parity attest reports\parity\new-native-run --status success --reviewer "your name"
.\.venv\Scripts\python.exe -m alteryx2python.parity collect reports\parity\new-native-run --manual
```

原生失败时使用 attest ... --status failed --failed-node 2 记录实际失败节点。
不能根据 Python 结果填写原生结论。
成功运行缺少/损坏原生导出会拒绝确认；确认后原生文件改变也会拒绝使用。
collect --refresh-python 在原 Workflow 不变时重新执行当前 Python，保留独立原生结果。
YXDB 使用现有 [yxdb reader](https://github.com/tlarsendataguy-yxdb/yxdb-py) 读取。
自动探针仅覆盖明确允许的表格工具；其他类别使用人工核对包和专项适配器。

本机 Engine 命令行实测缺少 API or FlowChartMode 许可；Designer 手动运行已成功。
许可要求见[官方说明](https://help.alteryx.com/designer/current/en/workflows/run-workflows-via-command-line.html)。
实测见[行为验证报告](evidence/2026-11-09/behavioral-update/README.md)。

## 外部 API 与尚未完成的工作

手动 Designer 可以绕过 **Engine 自动启动 API** 的限制。
Salesforce、云存储、AI 等**工具本身的外部 API**仍需服务、连接配置和双方权限。
具备前提后可用同一测试数据手动运行，比较各节点结果及服务端实际写入。
离线真实响应只能验证后续转换，不能证明当前认证、分页、重试或远端写入等价。
本次没有执行外部业务请求。

97 个条目不只是 API：还包括专有地址/人口/Behavior/Calgary 数据格式、
路网出行时间、部分视觉模板/训练组件、UI/SDK 或尚未编写的适配器。
具体条目以覆盖表为准，不能把“未实现”全部说成“API 验证不了”。
已有执行函数仍需补齐原生配置、锚点、类型、模型/报告和副作用契约，并增加专项原生案例。
AMP、迭代/批次/交互宏及任意界面操作不在已有 6 个通过案例的证明范围内。

```powershell
.\.venv\Scripts\python.exe -m alteryx2python.parity inventory
.\.venv\Scripts\python.exe -m alteryx2python.parity coverage --output reports\parity\coverage.json --require-mapped
.\.venv\Scripts\python.exe -m pytest
```

--require-mapped 只检查 ID 映射完整性，不能充当全部工具实现或等价验收的通过条件。

