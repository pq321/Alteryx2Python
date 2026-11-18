# Alteryx 到 Native Python 内部提案、演示与制作交接手册

## 0. 给下一位制作 agent 的简报

**交付物。** 从本文独立做一版新的 PowerPoint 和逐页讲稿，**幻灯片、图表标注、speaker notes、讲稿和 Q&A 全部用英文**。本文中的推荐页序提供内容参考，页数和版式可以重新设计。现有版本用于后续对比，请给新版另取文件名。默认按 15 分钟准备，其中约 6 分钟 demo、3 分钟 Q&A，同时保留 10 和 20 分钟的调整方式。

**项目做什么。** 这个 repo 是一套 Alteryx 到 Python 的确定性转换和验证工具。它读取现有 Alteryx workflow 的工具、配置、表达式和连接，用 Python 实现已支持的 Alteryx 行为。Phase 1 交付可逐节点核对的 Python 执行基线。Phase 2 从保留的 workflow 表示编译出可由工程师接手的 Python。验收时用实际 Designer 结果和两份生成程序的执行结果做对照。典型使用者是负责迁移和后续维护的技术团队，其用户可能通过 GWM 既有渠道收到 Windows `.exe`。

**听众与决策。** 这是 UBS 内部技术提案。听众懂 Python、数据处理或系统交付，可能第一次接触 Alteryx。目标是确认对**适用的现有 workflow**推进 Native Python 迁移。提案人已持有一批 workflow、测试数据和一键验证脚本，可以先跑首轮，再根据结果确认部署路径、需要补的适配和需要业务 owner 参与的例外。

**已经定下来的演示路径。** 主 demo 用提案人已有权限的真实 workflow，从 **Inspect → Designer 原生运行 → Phase 1 逐节点对照 → Phase 2 独立交付**。PPT、Designer、报告和代码沿用同一个节点、字段和业务规则。localhost 编辑器留作技术问答。代码还可以生成原生 `.yxmd`，适合展示如何为原 workflow 创建带探针或本地输出的验证副本。现有 Record ID 案例是已验证的备用材料，主业务 workflow 的 ID、参数和结果由提案人彩排后填入。

**制作边界。** 正文使用下面已确认的提案口径、适用场景和可核对的证据。末尾的 repo 导航、能力缺口和额外试验是给制作 agent 理解项目和回答追问的材料。两项内部数字、GWM 流程和连通性限制来自提案团队。平台通用能力来自供应商文档，平台适用性是本提案基于当前 workload 的判断。

## 1. 时间安排

| 环节 | 10 分钟 | 15 分钟（默认） | 20 分钟 |
| --- | ---: | ---: | ---: |
| PPT 1–3。退役背景、选型、Alteryx workflow 如何转换 | 2:30 | 3:30 | 4:30 |
| PPT 4。两阶段和验收标准 | 1:00 | 1:30 | 2:00 |
| 现场 demo。同一真实 workflow 从图到交付 | 4:00 | 6:00 | 8:00 |
| PPT 5。验证结果、下一步和决策 | 0:30 | 1:00 | 1:30 |
| Q&A | 2:00 | 3:00 | 4:00 |

10 分钟版把平台对比压成一句话，demo 保留一个节点、一次命令、一份报告和一处 Phase 2 代码。20 分钟版加一次可控的业务参数变化或代码修改，再展示一个有实际记录的失败诊断。各版本都给原生对照留时间。

## 2. PPT 内容与英文讲法

| 页 | 建议标题 | 屏幕上放什么 | 口头讲什么 |
| --- | --- | --- | --- |
| 1 | **Alteryx retirement and migration proposal** | `1,000+ workflows`、`End of 2027`、`Native Python for eligible workflows` | 按当前内部口径介绍规模和退役时间。解释重复验证为何比依赖原开发者逐个重写更容易扩展。会前确认数字和日期的内部表述。 |
| 2 | **Platform fit by workload** | Alteryx 作为现状参照，加 Automation Anywhere、Fabric、Databricks 和 Native Python 四个目标选项。用可编辑矩阵展示各自的强项和本次迁移中的取舍。 | 平台按工作负载选。将 GWM 已跑通的内部流程放在下一页或作为该页的独立视觉。 |
| 3 | **What an Alteryx workflow contains** | 从主案例截出 **一个节点、一个关键配置和两条连接**。标出 tool、配置和 output anchor。 | 比如用真实 `Join` 节点说明连接键和未匹配分支。讲清楚解析器保存配置和依赖，Python 实现对应执行规则。同类配置验证过一次后可以复用，组合行为仍有 workflow 级比较。 |
| 4 | **Two phases, two comparisons** | `Designer baseline ↔ Phase 1 Python ↔ Phase 2 Python`，再从 Phase 2 画箭头指向 `Standalone run`。在箭头旁标注验证数据、schema、输出文件和适用的运行行为。 | Phase 1 保留节点边界，便于定位差异。Phase 2 编译出独立脚本，便于团队接手。确定性带来可重复执行，原生对照提供一致性的证据。停在这页切到 demo。 |
| 5 | **What we can validate now** | 三项结果和范围、批量验证的下一步、需要评审团队确认的事项。 | 用实际验收报告填数据。说明首轮由你用现有权限、脚本和测试数据跑，owner 参与业务差异和生产接入的确认。 |

备两页附录。第一页放一张对照报告的局部截图，能看清节点 ID、状态和输出。第二页放部署依赖，分别写出 SMTP 未配置影响 SMTP 发信，Graph 被阻断影响经 Graph 访问 SharePoint 或 Outlook。根据 UBS 内部实际情况确认审批和接入路径。

### 2.1 让观众跟着同一条业务规则看

一次 `migrate --resume` 能生成两份 Python 和各段报告，Designer 直接展示原 workflow 的图和配置。用主案例里的**同一个节点 ID、同一个字段名和同一个业务规则**贯穿 PPT、Designer、报告和代码，减少观众每次切屏重新理解的成本。

- **第 3 页用三列。** 左侧裁一小段实际 workflow，圈出节点并标 ID。中间用一句业务语言解释配置，下面放两到四行有代表性的输入与预期输出。右侧放实际生成的 Phase 2 代码，只截包含该规则的几行。比如备用 Record ID 可写「每个 `Region` 从 1 开始编号」，让大家先看到两条同组记录和一条换组记录，再看 `groupby(...).cumcount() + 1`。主案例换成其实际字段和配置，示意数据标明用途。
- **第 4 页把转换和验证画成两行。** 上面用实线画 `Alteryx workflow → Phase 1 → Phase 2`，说明会生成什么。下面在对应位置标出三项检查 `Designer 基准 ↔ Phase 1`、`Phase 1 ↔ Phase 2`、`运行交付脚本 → 实际输出`。底部放一行「相同的测试输入和参数」。在第一个对照旁标明原生基准是在会前用 Designer 采集的。
- **第 5 页用一张小表替代 JSON 截图。** 三行分别写「关键节点对照」「两阶段对照」「独立脚本输出」，每行放一个实测结果和报告文件名。只提报告实际验证的维度。例如备用案例节点 138 的原生记录显示 6 行的值匹配，物理 schema 未验证。文件逐字节一致可以单列为产物结果。

投屏时保持同一个视觉位置或高亮色标示该规则。完整画布、原始 XML、Phase 1 全文件、完整 JSON 和生成 helper 放在备用标签页。PPT 中的代码截图优先选业务表达式和上下各一行，便于远端观众跟上。

新版的视觉重点放在**实际节点配置、两三行输入输出和可读的 Python**。平台页用清晰的比较矩阵，GWM 页用一条部署流程，验证页用简短结果表。找不到获准的主案例截图时，使用带 `Verified fallback example` 标注的 Record ID 局部截图和实际生成代码。图像裁掉无关窗口边框、数据和路径，代码片段应能投屏阅读。新版可以重新安排留白、字体、配色和构图。

### 2.2 Platform fit by workload

The comparisons below describe workload fit. The three managed candidates can all participate in a wider migration portfolio. Evaluate each one against the required data access, scale, orchestration, user experience and support model.

| Option | Strength | Trade-off for this proposal |
| --- | --- | --- |
| **Alteryx Designer** | A visual canvas makes data preparation, blending, branching and intermediate results accessible to analysts. The source configuration and Designer output are valuable migration evidence. | Continued operation depends on the retiring Alteryx estate. Tool semantics, macros, app actions and events can make a full migration more involved than copying the visible canvas. |
| **Automation Anywhere** | RPA for repeatable desktop and web application interactions, especially when the business process depends on operating an application UI. | For file and table transformations, bot deployment and any UI selectors add dependencies to support. Retain it as an option for workloads whose essential behaviour is application interaction. |
| **Microsoft Fabric** | Managed analytics with Data Factory orchestration, OneLake, Spark and Power BI. A strong fit when shared data and reporting belong in the same environment. | Workspace, capacity, orchestration and access need a clear role for a small self-contained user-run workload. Fabric offers multiple ways to transform data, including visual authoring, SQL and Python/PySpark. |
| **Databricks** | Distributed data engineering and streaming, with Spark, Lakeflow orchestration and Unity Catalog for governed shared data. | A small local file workflow may gain little from managed jobs and distributed compute. Choose it where scale, shared lakehouse data or governance requirements warrant that environment. Databricks supports Python alongside SQL and other languages. |
| **Native Python** | Flexible libraries, reviewable Git changes, independently runnable scripts, regression tests and packaging for Windows users. A strong fit for eligible file-based and tabular transformations. | The team owns dependencies, testing and runtime operations. Platform capabilities such as scheduling, monitoring, compute and service access must come from the delivery environment where the workload needs them. |

Official capability references. [Alteryx Designer](https://help.alteryx.com/designer/current/en/get-started/get-started-with-alteryx-designer.html) · [Automation Anywhere Recorder](https://docs.automationanywhere.com/r/automation-360/cloud-recorder-command) · [Microsoft Fabric](https://learn.microsoft.com/en-us/fabric/fundamentals/microsoft-fabric-overview) · [Fabric Data Factory](https://learn.microsoft.com/en-us/fabric/data-factory/data-factory-overview) · [Databricks data engineering](https://docs.databricks.com/aws/en/data-engineering) · [Unity Catalog](https://docs.databricks.com/aws/en/data-governance/unity-catalog/) · [Python standard library](https://docs.python.org/3/library/)

### 2.3 GWM’s existing Python delivery route

**Recommended English slide copy.** “GWM already registers Python applications through ADT/BDC and uses GitLab CI/CD to package Windows executables for users. Eligible migrations can reuse that process.” Label the three steps **ADT/BDC registration**, **GitLab CI/CD build**, and **Windows executable distribution**. Use the appropriate internal registration label for the workload. `ADT-B` was also mentioned in earlier project discussions, so confirm the exact label before using it for a specific example.

**Speaker cue.** “The company process for registering and delivering Python is already in use in GWM. We can reuse that route while keeping the business logic in reviewable Python source. For each new workflow, we still confirm the registration, release ownership, runtime access and any scheduling or monitoring it needs.” Give the internal implementation credit to GWM. The public GitLab documentation supports the general CI/CD capability. [GitLab CI/CD](https://docs.gitlab.com/ci/)

**Deployment boundary.** In the internal environment described by the proposing team, SMTP is unconfigured and Microsoft Graph access is blocked. SMTP affects sending through that route. Graph affects access to SharePoint and Outlook through Graph. These are shared connectivity dependencies across internal automation initiatives. Show the impact only for workloads that require those services. A local `.eml` draft can exercise document generation without establishing live email delivery.

### 2.4 English talk track for the main story

| Beat | Speaker copy to adapt |
| --- | --- |
| **Opening and scale** | “Our planning baseline is more than a thousand Alteryx workflows and retirement by the end of 2027. Some were built years ago and their original developers may have moved on. The workflow file gives us an executable record of the rules. We can capture original results while Designer is available and reuse the same validation process across workflows.” |
| **Why deterministic conversion** | “An Alteryx workflow is a graph of configured tools. The source tells us which operation to apply, how it is configured and where the output goes. The converter reads that structure and applies explicit Python rules. AI can help investigate differences or suggest tests. The source configuration and independent comparisons drive the migration.” |
| **Why two phases** | “Phase 1 keeps the original tool boundaries so we can locate discrepancies. Phase 2 produces Python that a team can run, review and change. The generators can evolve in parallel. For each workflow, we need the Designer baseline, the Phase 1 comparison, the Phase 2 comparison and an independent run of the delivered file.” |
| **What counts as a pass** | “The same inputs and parameters go through each stage. We check the business-critical values and the relevant types, row order, branches and artifacts. Repeatability comes from deterministic conversion. Evidence of agreement comes from the observed outputs. We resolve or explicitly agree on business-relevant differences before cutover.” |
| **Closing ask** | “I’m asking us to use native Python for the workflows that meet our technical and operating criteria. I can run the initial batch with the authorised workflows and test data I already have. We’ll use the reports to decide what is ready, what needs an adapter and what needs a business or platform decision.” |

## 3. 从陌生 workflow 开始的四步命令

在仓库根目录使用 PowerShell 7 和已安装项目依赖的 Python。Designer 步骤需要 Windows 上的 Alteryx Designer。第一次运行只需要提供 workflow 路径。后续命令沿用同一份记录，所有报告路径都由命令打印。

### 第 1 步 · Inspect

```powershell
.\scripts\presentation.ps1 inspect 'C:/approved-test/workflow.yxwz'
```

一屏查看节点与连接数、App 问题、外部依赖、活跃问题的节点 ID 和 Phase 2 编译预检结果。完整的 inspect.json 和 audit.json 自动保存。省略路径时可用 Windows 文件选择器。验证 macro 时，选调用它的 workflow。

### 第 2 步 · Designer

```powershell
.\scripts\presentation.ps1 designer
```

脚本创建独立案例，记录答案、输入快照和 Event，再用 auto 模式打开 Designer。App 按终端提示填值，日期填 YYYY-MM-DD。脚本在日历中切到目标月份并选中日期，同时回读支持的输入控件。全部答案验证后，脚本点击 Finish；遇到需要人工填写的控件时，终端会提示。运行期间识别到的 Alteryx One 注册提示会自动关闭。只记录日志的 After Run Event 按提示选择 ID，原来的批处理由本地 JSONL 记录替代。

Designer 完成后看实际 Results。命令会给出结果截图、案例目录和下一步。需要 AMP 探针导出时，第 3 步会自动处理。

### 第 3 步 · Phase 1 对照

```powershell
.\scripts\presentation.ps1 compare
```

按提示确认实际看到的结果，失败时填写节点 ID，有跳过节点时也如实记录。命令运行 Phase 1 和独立 Phase 2，显示总状态、节点与 anchor、第一处差异或缺失证据，以及报告路径。可在 compare 后加一个节点 ID，例如 138。已有确认记录的案例可以直接重放。

### 第 4 步 · 展示 Phase 2 交付

```powershell
.\scripts\presentation.ps1 deliver
```

沿用第 3 步选择的节点，显示生成脚本位置和实际产物路径。在 Windows 上，验收通过时打开 Python 和一个可预览的输出文件。终端可找到 VS Code 时跳到对应行。只想显示路径可加 --paths-only。现场演示业务规则变更时，才运行另存的脚本副本。

可复用交付会同时显示运行参数文件 `phase-two-bindings.json`。展示如何换一组输入时，只需换这份 JSON，再用 `phase_two.py --bindings <参数文件>` 运行同一脚本。核心 `transform` 直接接收数据表和业务参数。需要其他 I/O 适配的案例会在验收报告中注明交付模式。

### 彩排选项

- designer --prepare-only 只生成隔离案例和 Designer 副本。随后用 designer --case '<案例路径>' 启动。已有答案时，用 designer --answers '<answers.json>'。已确认的日志 Event 可用 --log-event ID。需要执行其他 Event 时，沿用 --allow-event-command。
- Designer 会优先复用可用的 2025.1 窗口，现有 Workflow 标签页可以保留。多个候选窗口无法自动确定时，用 `designer --designer-pid <PID>`。界面阻塞时命令以非零状态退出，终端和 `designer-run.json` 会显示停在哪一步。每个案例的自动化总时限为 180 秒。
- compare 和 deliver 可用 --case '<案例路径>' 打开指定的历史案例。报告包括输入快照、暂存后的审计、Designer 状态、逐节点对照和独立运行结果。
- 路径、文件和工作表不匹配时，从第 3 步打印的报告定位原生节点和差异。用第 2 步建立新案例重跑，每次保留独立的快照和记录。

### 演示彩排与备用案例

附录命令使用与主流程相同的 Python 环境。若使用仓库虚拟环境，先运行 `$py = (Resolve-Path '.venv/Scripts/python.exe').Path`。

可用七类输入示例彩排 App 问答。它在同一个 workflow 中包含 Text Box、Checkbox、Drop Down、Radio Button、Date、Folder Browse 和 File Browse。以下命令会运行三组独立 Python 对照并在 Designer 中打开默认用例。它使用自己的新报告目录，适合技术问答或替代演示。

```powershell
$appDemo = Join-Path 'reports' ('seven-question-demo-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
& $py -m examples.python_pipeline_comparison.compare_app $appDemo --designer
Get-Content "$appDemo/comparison.json"
```

该示例的完整 Designer 采集走过 `auto` 的 Options 回退。三组 Python 对照覆盖默认回答、修改全部七类输入和仅含表头的 CSV。要演示陌生 workflow 的通用入口时，从本节第 1 步开始。 [七类输入示例说明](../examples/python_pipeline_comparison/README.md)

用 **Alteryx Designer** 打开主案例，预先选中要讲的节点，并把配置和输出分支放在可见范围内。保存局部截图。如果要讲代码生成 `.yxmd`，同时备好原 workflow 和生成的验证副本，标出新增的探针或本地输出。采集基准用的 workflow 与报告要对应同一份输入和参数。

localhost 编辑器留给技术问答。浏览器打开 `http://127.0.0.1:18081` 后可以导入主案例检查解析结果。界面里的 Run 使用项目的 Python runtime，原生基准来自 Designer。

```powershell
Set-Location 'E:/Automation/Alteryx2Python'
& .venv/Scripts/python.exe -m webapp.server --port 18081
```

保留上一轮成功彩排的报告、代码和输出，现场异常时用来回放。另准备仓库现有 Record ID 案例作为独立备用。先确认本机有 `reports/parity/record-id-demo/native/manifest.json` 和同目录的 Designer 证据。若用的是另一台机器，按 [Record ID 准备流程](designer_delivery_demo.md) 把本机的基准重新准备好。

```powershell
$backupNative = 'reports/parity/record-id-demo/native'
$backupOut = Join-Path 'reports/parity' ('proposal-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
& $py -m alteryx2python.parity verify-delivery $backupNative --output-dir $backupOut
if ($LASTEXITCODE -ne 0) { throw 'Record ID backup did not pass' }
Import-Csv "$backupOut/delivery-output/grouped-records.csv" |
    Select-Object Region, 'Grouped Record ID' | Format-Table -AutoSize
```

备用案例可以演示 `groupby(...).cumcount() + 1`。在临时副本把这一条规则的 `+ 1` 改成 `+ 100`，单独运行。编号应从 `1, 2, 1, 1, 2, 1` 变为 `100, 101, 100, 100, 101, 100`。展示时说明这一步是模拟一次业务规则变更。把修改好的副本放在 `$backupOut/phase_two_edit.py`，现场只需运行它并显示输出。

```powershell
if (Test-Path "$backupOut/edited-bindings.json") {
    & $py -I "$backupOut/phase_two_edit.py" --bindings "$backupOut/edited-bindings.json"
} else {
    & $py -I "$backupOut/phase_two_edit.py" --output-dir "$backupOut/edited-output"
}
if ($LASTEXITCODE -ne 0) { throw 'Edited delivery failed' }
Import-Csv "$backupOut/edited-output/grouped-records.csv" |
    Select-Object Region, 'Grouped Record ID' | Format-Table -AutoSize
```

彩排时，如果验收报告提供了 `phase-two-bindings.json`，复制为 `edited-bindings.json`，将 CSV 对应的 `output_file_*` 值改到 `edited-output/grouped-records.csv` 的绝对路径。

## 4. 现场操作顺序（默认 6 分钟 demo）

1. **0:00–0:45 · Inspect。** 展示一屏摘要，选一个业务节点。
2. **0:45–2:00 · Designer。** 展示同一节点的配置和原生结果。六分钟版可会前完成原生采集。
3. **2:00–4:15 · Phase 1。** 运行 compare，看同一个节点的 anchor 和第一处差异。已有原生确认的案例直接重放。
4. **4:15–5:30 · Phase 2。** 运行 deliver，打开对应 Python 和实际产物。
5. **5:30–6:00 · 回到 PPT。** 用验收结果说明该案例验证了哪些行为。

### 4.1 每个屏幕的英文讲法

| 屏幕 | 操作 | 可以直接说 |
| --- | --- | --- |
| **Inspect in terminal** | 运行 Inspect 并指出选定的节点。 | “I’m starting with an unfamiliar workflow. The inventory tells me what it contains and which node I’ll follow.” |
| **Alteryx Designer** | 点开 PPT 已圈出的节点，指向该工具的配置。 | “This is the original rule in Designer. I’ll follow this same node through the comparison and into the generated Python.” |
| **生成的验证副本，可选** | 展示保留的原节点与一个新增的探针或输出点。 | “The verifier generates this copy so we can capture the native result at this point and compare it with Python.” |
| **终端** | 运行一次验证，显示三项状态。等待时可展示原生基准。 | “Both generated programs use the same test inputs and settings. The Designer results were captured ahead of time and serve as the reference for this run.” |
| **证据** | 从总体结果展开到同一个节点的一条 `Output` 记录，再打开最终产物。 | “Here is the comparison for the node we just saw. The standalone Python process produced this output file.” |
| **Phase 2 代码** | 跳到预先标记的函数，高亮对应规则。最后回到同一字段的输出。 | “This is the rule we saw in Designer. A future change to that rule has a specific place in the Python source and a regression test we can rerun.” |

想现场展示一次 change request 时，让观众先猜会改哪一列，再执行已准备好的脚本副本并切到两列对照 `原值 / 改后值`。这段适合 20 分钟版或 Q&A。仓库的 [手写 Python 与 Phase 2 对照实验](../examples/python_pipeline_comparison/README.md) 也适合作为维护性追问的附录。里面有加分组字段和改邮件主题的具体例子，适合说明生成代码中哪些部分是业务规则，哪些部分在保留格式、类型和交付行为。

## 5. 现场故障切换

| 发生什么 | 当场怎么做和怎么说 |
| --- | --- |
| Designer 打不开、界面卡住 | 切到 Designer 局部截图，沿用同一个节点。可说 “This capture shows the configuration we were about to inspect. I’ll continue with its comparison.” |
| 终端跑得比彩排慢 | 到预定切换时间，打开已成功彩排的报告和输出，说清楚屏幕上的是「同一案例的上一次完整运行」。当前任务可继续执行，最后有结果再补报。 |
| `incomplete`、`blocked` 或 `mismatch` | 显示实际状态和第一条关键证据。缺少基准时说清楚缺哪一项，结果不同时说清楚差异发生在哪层。继续讲维护性时，优先打开已验证的交付代码。 |
| 主案例失效或数据临时不可展示 | 切到 Record ID。明确这是用于展示机制的备用案例，企业 workflow 的结论以它自己的验证记录为准。 |
| 网络、SharePoint 或 Outlook 被问到 | 打开部署附录。说明测试比较是否包含该行为，以及生产需要的获批访问路径。 |
| 时间被压缩 | 保留一个 Designer 节点、一次真实验证结果和一处 Phase 2 代码。把验证副本、平台展开和额外改动留到 Q&A。 |

## 6. 预备 Q&A

| Likely question | Suggested answer |
| --- | --- |
| **Why use deterministic conversion?** | The source already describes tool settings, expressions and connections. Explicit rules make a conversion repeatable and traceable. AI can assist investigation or test design. Native comparisons determine whether the required behaviour is preserved. |
| **How do we know the results match?** | We run with the same inputs and settings and compare against captured Designer results. The report tells us which nodes, outputs and behaviours were checked. The fallback covers values at the selected node and identical CSV bytes. |
| **Why keep two phases?** | Phase 1 keeps the original tool boundaries for verification. Phase 2 is the Python source the team can maintain. The phases can develop in parallel, with a native baseline for acceptance of each workflow. |
| **Can someone really edit the generated code?** | Show the rule in `phase_two.py`. In the fallback, changing the starting ID from 1 to 100 changed the expected column when we ran the script on its own. The programme still needs its Python dependencies and any external input resources. |
| **Can this cover all 1,000+ workflows?** | Scope coverage by the actual tool configurations, macros, app Actions, inputs, outputs and external dependencies. The first batch will establish what runs, what differs and what requires more work. |
| **Will users have to test every workflow by hand?** | I can run the first batch with the workflows, data and scripts I already have access to. A business owner can review cases that involve material differences or decisions about expected behaviour. |
| **What if EngineCmd is unavailable?** | We can capture the reference in Designer and replay the comparison from that baseline. The Python verification can rerun independently from the original capture. |
| **When would we use another platform?** | Automation Anywhere fits application interaction. Fabric fits shared Microsoft analytics, and Databricks fits governed lakehouse workloads and distributed processing. Use native Python when the workload fits the GWM delivery route and the team can operate it. |
| **Does the GWM precedent cover every new release?** | The registration and delivery process already exists. We confirm the relevant registration, ownership, access and runtime setup for the individual workflow. |
| **How do SharePoint and Outlook affect the proposal?** | Graph access and SMTP delivery are separate dependencies. For any affected workflow, record the behaviour covered by the test and confirm the approved production access path. |
| **What happens when the results differ?** | Locate the first discrepancy in the evidence, the Phase 1 execution or the Phase 2 compiler. Fix the relevant rule, regenerate and rerun the affected comparisons. After handover, application changes go through the owning team’s Git and test process. |

## 7. 最后一轮彩排检查

- [ ] 确认主 demo workflow、测试数据、参数和共享屏幕展示权限。
- [ ] 用干净的输出目录重跑一次主案例，记录耗时，确认三项 `match`，记录原生基准采集方式。
- [ ] 逐一打开 Designer 节点、报告、Python 函数和最终输出，确认四处对应同一条业务规则。
- [ ] 从备用原生证据重跑 Record ID，打开上次通过的报告和局部截图。
- [ ] 分别按 10 和 15 分钟版本计时，至少模拟一次 Designer 打不开或验证超时的切换。
- [ ] 在最后一页写清当场需要确认的决定，并核对所有展示的数字和证据范围。

## 8. Appendix for the next agent

### 8.1 What the repo actually does

The migration direction is **Alteryx workflow to Python**. The implementation first models supported Alteryx semantics in Python. `WorkflowIR` is the intermediate representation for the workflow graph and its configuration. It preserves node IDs, named input and output anchors, expressions, configuration, and graph or runtime metadata. The parser’s ability to preserve configuration is distinct from the runtime’s ability to execute it.

1. **Parsing and normalisation.** The XML parser reads `.yxmd` workflows, `.yxwz` analytic apps and `.yxmc` macros. Tool-specific parsers normalise settings while retaining raw configuration. An Action can bind an app answer to a node setting before execution. The workflow can also contain containers, macros, constants or variables, and events whose behaviour needs separate coverage.
2. **Phase 1 execution.** The generated baseline reconstructs the preserved IR and uses the canonical Python runtime and tool registry. This gives node and anchor-level traces. The native verification path can generate an instrumented workflow, capture native Designer outputs or file artifacts, and compare those with the actual Phase 1 entrypoint. Phase 1 prioritises compatibility and diagnostics, and its runtime-oriented source is verbose for routine business changes.
3. **Phase 2 compilation.** The compiler accepts a native workflow, preserved IR, or a recognised generated Phase 1 file with literal IR. It can lower supported configuration into ordinary expressions, pandas operations, dependency-based functions and audited helper code. A fixed-parameter build applies the selected app answers before compiling. Supported dynamic parameters can be explicit Python arguments. The manifest maps source node IDs to generated functions and lines. The delivery script runs with ordinary Python dependencies and case-specific inputs, independently of the converter. A separate generated verification build records checkpoints. Arbitrary hand-edited Phase 1 scripts need explicit review because the Phase 2 compiler relies on the preserved representation.
4. **Verification and handover.** Use the same input, parameters, and relevant run conditions for each execution. Compare Designer with Phase 1, Phase 1 with Phase 2, and the delivered script’s outputs with the verification build. Validate tool/configuration behaviour and full workflow composition at their appropriate levels. Compare field types, nulls, precision, row order, output anchors, failures and actual file artifacts according to what the case requires and what the native evidence captures. Fix mismatches in the relevant parser, runtime or compiler template and rerun the checks. After handover, the delivered Python becomes the source for business changes and regression tests.
5. **Authoring and preview.** The repo can construct and export native `.yxmd` workflow files. This also supports instrumented Designer copies used to capture original behaviour. The localhost editor imports graphs and configuration, previews using the canonical Python runtime, and can export supported workflows. The presentation uses Designer as its primary interface.

### 8.2 Evidence and status labels

| Item | What a presenter may say | Scope |
| --- | --- | --- |
| **UBS planning premise** | More than 1,000 existing workflows and planned retirement by the end of 2027. GWM has a working Python registration and Windows distribution process. | Provided by the proposing team. Use as internal context and confirm wording before external circulation. |
| **Record ID fallback** | Three `match` statuses on a fresh Python rerun against already collected Designer data. Eight native comparisons, nineteen Phase 1 to Phase 2 node checks, and byte-identical CSV. Node 138 produced six rows across four `Region` groups. | Installed Designer sample and fixed local output. The node’s native comparison checked values and row order. Native physical schema was outside this comparison. |
| **Editability check** | The delivered Record ID `.py` ran in an isolated directory with project imports blocked. A temporary copy changed the group start from 1 to 100. IDs changed from `1, 2, 1, 1, 2, 1` to `100, 101, 100, 100, 101, 100`; the other fields stayed the same in that check. | Demonstrates the handover of one supported rule. The edited run has new intended behaviour and its own expected output. |
| **Iris engineering benchmark** | A recorded run matched 38 outer nodes and eight artifacts between the two Python phases, including standalone execution. | Python-to-Python evidence. The benchmark’s independent native Alteryx status was `unverified`. |
| **Handwritten Python comparison** | The synthetic transaction fixture compares generated Phase 2 with independent handwritten Python. It supplies an example of changing group keys and email subject, and has documented Designer checks for selected Formula/Filter probes and CSV and HTML results. | Supporting maintenance and test material. The `.eml` artifact is a local draft. Review the fixture’s README and evidence before quoting counts. |
| **Company main demo** | Use actual results from a selected authorised workflow. First prepare the local case and run its acceptance checks. | The main workflow ID, real input set, elapsed time and match status are still to be supplied for the deck. |

`match` is scoped to the named checks and their inputs. `incomplete` indicates missing evidence for a required check. `blocked` indicates a case or step could not be verified. `mismatch` indicates a recorded difference. Use the actual report to explain the cause. Inventory or parser coverage, registration counts, tests passing, execution success and observed native equivalence are different kinds of evidence.

### 8.3 Code and evidence map

| Question | Where to look in the workspace |
| --- | --- |
| How do XML and tool settings become IR? | [`xml_parser.py`](../alteryx2python/parser/xml_parser.py), [`ir/models.py`](../alteryx2python/ir/models.py), [architecture](architecture.md) |
| What does Phase 1 run? | [`python_generator.py`](../alteryx2python/generator/python_generator.py), [`runtime/executor.py`](../alteryx2python/runtime/executor.py), [Workflow CLI](workflow_cli.md) |
| How is Phase 2 assembled and mapped back to nodes? | [`generator/readable.py`](../alteryx2python/generator/readable.py), [`generator/business_source.py`](../alteryx2python/generator/business_source.py), [Readable Python guide](readable_python.md) |
| What actually runs against the native evidence? | [`parity/delivery.py`](../alteryx2python/parity/delivery.py), [`parity/runner.py`](../alteryx2python/parity/runner.py), [Designer delivery demo](designer_delivery_demo.md), [Phase 1 Designer parity](tools/phase_one_parity.md) |
| How are unsupported configurations diagnosed and added? | [Support diagnostics](support_diagnostics.md), [Adding Alteryx tool support](adding_tool_support.md), [Component mapping status](component_mapping_status.md) |
| What can the browser editor display? | [Visual editor guide](visual_editor.md) |
| What examples help explain the generated code? | [Record ID verification](designer_delivery_demo.md), [Iris benchmark](../examples/readable_benchmark/README.md), [handwritten Python comparison](../examples/python_pipeline_comparison/README.md) |

Prior audits found File Action and question binding gaps in the repository copies of `MIFID II.yxwz` and `DraftEmail_1.yxmc`. Those are starting points for diagnosis. Recheck the current code and candidate before describing either as a supported full workflow. The codebase and tool coverage continue to change. External dependencies, macros, app Actions, events, unusual field types and I/O options need configuration-level evidence.

### 8.4 Assets and handoff checklist for the deck builder

- Record ID Designer screenshots, instrumented workflow and native output are under `reports/parity/record-id-demo/native/`. Use `designer-result.png` for a cropped canvas and `results-detail.png` for the Results view. The prepared source is `reports/parity/record-id-demo/record-id-demo.yxmd`.
- Regenerate the paired reports and editable `phase_two.py` using the Record ID fallback commands in section 3. `phase_two.manifest.json` identifies the function and generated line for a source node. `delivery-output/grouped-records.csv` provides the two or three actual rows for a slide. For node 138, use the group key `Region` and the output column `Grouped Record ID`.
- Previous-version files are `reports/migration-proposal/Alteryx_Migration_Proposal.pptx` and `reports/migration-proposal/Alteryx_Migration_Speaker_Script.md`. These provide a comparison version if available. The proposal facts, presentation flow, wording and evidence scope needed for a fresh version are in this runbook.
- Before authoring, fill the main-case brief with the authorised workflow name, node ID, rule, input and output fields, native capture date, observable result and screenshot permissions. If these are unavailable, make the live walkthrough instructions reusable and label Record ID visuals and numbers as fallback evidence.
- Keep public source links next to the corresponding platform claims in speaker notes or a references appendix. Attribute the GWM process and retirement premise to internal project context.
- `reports/` is local and Git-ignored. Another agent on a different machine can use this runbook and the tracked docs immediately. Provide approved screenshots or evidence files separately if those local materials are needed for the new deck.
