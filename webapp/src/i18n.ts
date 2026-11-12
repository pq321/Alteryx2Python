export type Language = 'zh' | 'en';
const STORAGE = 'alteryx2python.language';
export const dictionary = {
  '工作流': 'Workflow', '未命名工作流': 'Untitled workflow', '工作流名称': 'Workflow name', '工作流编辑器': 'Workflow editor',
  '打开': 'Open', '保存': 'Save', '生成代码': 'Generate Python', '▶ 运行': 'Run', '新建': 'New', '示例': 'Example',
  '工具库': 'Tools', '展开工具库': 'Expand tools', '折叠工具库': 'Collapse tools', '搜索工具…': 'Search tools…', '搜索工具': 'Search tools',
  '打开工作流 JSON': 'Open workflow JSON or Alteryx XML', '保存工作流 JSON': 'Save workflow JSON', '本地草稿': 'Local draft',
  '撤销': 'Undo', '重做': 'Redo', '撤销 (Ctrl+Z)': 'Undo (Ctrl+Z)', '重做 (Ctrl+Shift+Z)': 'Redo (Ctrl+Shift+Z)',
  '↥ 导入数据': 'Import data', '从数据开始': 'Start with data', '新建数据表': 'New table', '导入文件': 'Import file',
  '打开销售分析示例 →': 'Open sales analysis example', '导入数据文件': 'Drop data or workflow files', '工作流画布': 'Workflow canvas', '工作流节点与连线': 'Workflow nodes and connections',
  '缩小': 'Zoom out', '放大': 'Zoom in', '适应画布': 'Fit canvas', '调整配置区宽度': 'Resize configuration', '调整结果区高度': 'Resize results',
  '节点配置': 'Node configuration', '删除节点': 'Delete node', '删除': 'Delete', '关闭配置': 'Close configuration',
  '工作流结果': 'Workflow results', '结果视图': 'Result views', '数据结果': 'Results', '选择节点输出': 'Select output', '下载当前结果': 'Download current result', '折叠结果区': 'Collapse results',
  '暂无运行结果': 'No results yet', '正在连接…': 'Connecting…', '本地执行': 'Local execution', '取消': 'Cancel', '确认': 'Confirm',
  '重命名': 'Rename', '小数位': 'Scale', '选择宏文件': 'Choose macro files', '选择宏目录': 'Choose macro folder', '入口宏': 'Entry macro',
  '执行记录与文件': 'Execution log and files', '文件未包含在响应中': 'File omitted from response', 'Alteryx2Python 首页': 'Alteryx2Python home',
  '工作目录': 'Working directory', '发件人': 'From', '收件人': 'To', '主题': 'Subject', '正文': 'Body', 'SMTP 服务器': 'SMTP server', '工作流 JSON 已下载': 'Workflow JSON downloaded',
  '运行错误后': 'After run with errors', '运行警告后': 'After run with warnings', '运行错误或警告后': 'After run with errors or warnings', '发送邮件': 'Send email', '端口': 'Port', '加密': 'Encryption', '认证': 'Authentication', '用户名': 'Username', '超时（秒）': 'Timeout (seconds)',
  '重置': 'Reset', '配置源已更新，请重置后重新编辑': 'Configuration changed. Reset this editor before editing again.', '完整运行参数 JSON': 'Complete runtime JSON',
  '下载代码映射清单': 'Download code mapping manifest',
  '文本输入': 'Text Input', '文件输入': 'Input Data', '输出数据': 'Output Data', '公式': 'Formula', '筛选': 'Filter', '选择字段': 'Select',
  '排序': 'Sort', '去重': 'Unique', '多行公式': 'Multi-Row Formula', '日期转换': 'DateTime', '汇总': 'Summarize', '交叉表': 'Cross Tab',
  '转置': 'Transpose', '记录 ID': 'Record ID', '抽样': 'Sample', '累计求和': 'Running Total', '排名': 'Rank', '文本分列': 'Text To Columns', '连接': 'Connections', '合并': 'Union', '正则解析': 'RegEx',
  '输入 / 输出': 'In / Out', '数据准备': 'Preparation', '数据转换': 'Transform', '数据连接': 'Join', '解析': 'Parse',
  '输出文件名 (.csv)': 'Output filename (.csv)', '筛选条件': 'Filter expression', '去重字段': 'Unique field', '左侧关联字段': 'Left join field', '右侧关联字段': 'Right join field',
  '输入字段': 'Input field', '正则表达式': 'Regular expression', '输出字段名': 'Output field name', '日期格式': 'Date format', '表达式': 'Expression', '抽样方式': 'Sample mode', '行数': 'Rows',
  '分组字段': 'Group field', '列标题字段': 'Header field', '值字段': 'Value field', '聚合方式': 'Aggregation', '记录 ID 字段名': 'Record ID field', '累计字段': 'Running total field', '排名字段': 'Rank field', '排名方向': 'Rank order',
  '分隔符': 'Delimiter', '输出列数 (1–100)': 'Output columns (1–100)', '输出字段前缀（默认使用输入字段名）': 'Output prefix (defaults to input field)',
  '未选择节点': 'No node selected', '输出字段': 'Output field', '类型': 'Type', '长度（可选）': 'Length (optional)', '排序字段': 'Sort field', '方向': 'Order', '汇总方式': 'Summary operation', '输出名称（可选）': 'Output name (optional)',
  '保留字段': 'Key fields', '转置字段': 'Data fields', '按字段名称合并全部输入。': 'Combine inputs by field name.', '+ 添加': '+ Add',
  '输入数据': 'Input data', '展开或收起数据表': 'Expand or collapse table', '字段名不能为空或重复。': 'Field names must be unique and nonempty.',
  '选择或拖入 CSV、TSV、XLSX 文件': 'Choose or drop CSV, TSV or XLSX files', '替换数据文件': 'Replace data file', '选择或拖入文件': 'Choose or drop file', 'CSV · TSV · XLSX / 最大 20 MB': 'CSV · TSV · XLSX / max 20 MB',
  '工作表': 'Worksheet', '数据预览': 'Data preview', '保留未列出的字段': 'Keep unlisted fields', '添加字段': 'Add field', '+ 添加字段': '+ Add field', '连接数据源后选择字段。': 'Connect a data source to select fields.', '暂无连接': 'No connections', '移除连线': 'Remove connection',
  '+ 行': '+ Row', '+ 列': '+ Column', '添加一行': 'Add row', '添加一列': 'Add column',
  '当前工作流已自动保存在本地。替换后可使用撤销恢复，也可以先下载 JSON 保存。': 'The workflow is saved locally. Undo restores it after replacement. You can also download its JSON.',
  '已切换工作表': 'Worksheet changed', '已自动保存': 'Saved automatically', '自动保存失败': 'Autosave failed', '本地存储不可用或空间不足，请下载 JSON 保存工作流': 'Local storage unavailable or full. Download JSON to save the workflow.',
  '保存中…': 'Saving…', '已撤销': 'Undone', '已重做': 'Redone', '已删除节点': 'Node deleted', '没有匹配的工具': 'No matching tools', '无法读取文件': 'Cannot read file',
  '工作流已切换，未添加导入节点': 'Workflow changed; imported node was not added', '目标节点已移除，未添加文件': 'Target node removed; file was not added',
  '工作流已修改，当前显示的是上一次结果。请重新运行或生成代码。': 'Workflow changed. Run or generate Python again to refresh these results.', '请先添加数据节点': 'Add a data node first', '正在运行…': 'Running…', '正在生成代码…': 'Generating Python…', '运行完成': 'Run completed', '代码已生成': 'Python generated',
  '替换当前工作流？': 'Replace current workflow?', '工作流已载入': 'Workflow loaded', '工作流文件超过 25 MB': 'Workflow file exceeds 25 MB', '工具列表为空': 'Tool catalogue is empty', '本地存储不可用': 'Local storage unavailable',
  '本地草稿无法读取，已保留原草稿；请打开有效的工作流 JSON': 'Local draft could not be read and has been preserved. Open a valid workflow JSON.', '已恢复本地草稿': 'Local draft restored', '就绪': 'Ready', '服务未连接': 'Service disconnected',
  '连线引用了不存在的节点': 'Connection references a missing node', '输入或输出端口不存在': 'Input or output port does not exist', '节点不能连接到自身': 'A node cannot connect to itself', '这条连线已存在': 'Connection already exists', '该输入已有连线，请先移除原连线': 'Input already connected; remove its connection first', '连线会形成循环': 'Connection would create a cycle',
  '工作流需要 name、nodes 和 edges': 'Workflow requires name, nodes and edges', '工作流包含无效或重复节点': 'Workflow contains invalid or duplicate nodes', '工作流包含无效的节点配置': 'Workflow contains invalid node configuration', '文本输入的字段配置无效': 'Text Input field configuration is invalid', '连线格式无效': 'Invalid connection format',
  '双击移除连线': 'Double-click to remove connection', '等待导入文件': 'Waiting for file', '选择输入端口': 'Select input port', '已连接': 'Connected',
  '工作流设置': 'Workflow settings', '高级配置': 'Advanced configuration', '完整节点配置': 'Full node configuration', '配置 XML': 'Configuration XML', '引擎设置 XML': 'EngineSettings XML',
  '应用': 'Apply', '恢复表单配置': 'Use form configuration', '配置已应用': 'Configuration applied', '配置未应用': 'Unapplied configuration', '无效 XML': 'Invalid XML', '无效 JSON': 'Invalid JSON',
  '工作流属性 XML': 'Properties XML', '运行属性 XML': 'RuntimeProperties XML (questions and actions)', '事件 XML': 'Events XML', '常量 XML': 'Constants XML', '原始工作流 XML': 'Original workflow XML',
  '运行参数': 'Runtime parameters', '用户回答 JSON': 'Question answers JSON', '变量覆盖 JSON': 'Variable overrides JSON', '允许的命令 JSON': 'Allowed commands JSON', '交付模式': 'Delivery profile',
  '参数导出方式': 'Export parameter mode', '动态参数': 'Dynamic named parameters', '固定当前回答': 'Specialize with current answers',
  '导入宏': 'Import macro', '宏文件': 'Macro file', '宏已导入': 'Macro imported', '宏路径': 'Macro path', 'Python 代码': 'Python code',
  '运行前': 'Before run', '运行后': 'After run', '运行成功后': 'After run without errors', '运行无警告后': 'After run without errors or warnings', '添加事件': 'Add event', '程序': 'Program', '命令参数': 'Arguments', '触发时机': 'When', '启用': 'Enabled',
  '事件': 'Events', '变量': 'Variables', '问题与动作': 'Questions and actions',
  '包含未知配置的完整 XML': 'Complete XML, including unknown configuration', 'JSON 对象': 'JSON object', 'JSON 字符串数组': 'JSON string array', 'XML 根元素必须为 {name}': 'XML root must be {name}',
  '{rows} 行 · {columns} 列': '{rows} rows · {columns} columns', '{count} 个节点': '{count} nodes', '{count} 条连接': '{count} connections',
  '字段 {n}': 'Field {n}', '删除字段 {n}': 'Delete field {n}', '删除第 {n} 行': 'Delete row {n}', '第 {row} 行第 {column} 列': 'Row {row} column {column}', '前 {n} 行': 'First {n} rows',
  '插入字段 {name}': 'Insert field {name}', '移除配置 {n}': 'Remove configuration {n}', '运行耗时 {seconds}s': 'Completed in {seconds}s',
  '正在导入 {name}…': 'Importing {name}…', '已导入 {name} · {rows} 行': 'Imported {name} · {rows} rows', '文件超过 20 MB：{name}': 'File exceeds 20 MB: {name}',
  '支持 CSV、TSV、TXT 和 XLSX 文件：{name}': 'Supported data formats: CSV, TSV, TXT, XLSX: {name}', '连接失败：{message}': 'Connection failed: {message}', '请求失败 ({status})': 'Request failed ({status})',
  '独立 Python 导出存在限制：{details}': 'Standalone Python export blocked: {details}', '预览前 {n} 行': 'Previewing first {n} rows',
  '配置 JSON': 'Configuration JSON', '配置格式错误：{message}': 'Invalid configuration: {message}',
} as const;
export type TranslationKey = keyof typeof dictionary;
const catalogue: Record<string, string> = {
  'AB Testing': 'AB 测试', 'Computer Vision': '计算机视觉', Connect: '连接器', 'Data Investigation': '数据探索', Developer: '开发', Documentation: '文档', Interface: '界面控件', Laboratory: '实验室', 'Machine Learning': '机器学习', Macro: '宏', Macros: '宏', Predictive: '预测分析', 'Predictive Grouping': '预测分组', Prescriptive: '决策优化', Reporting: '报表', Spatial: '空间分析', 'Text Mining': '文本挖掘', 'Time Series': '时间序列',
  'AB Analysis': 'AB 分析', 'AB Controls': 'AB 对照组', 'AB Treatments': 'AB 处理组', 'AB Trend': 'AB 趋势', 'Image Output': '图像输出', Download: '下载',
  'Association Analysis': '关联分析', 'Basic Data Profile': '基础数据概况', 'Contingency Table': '列联表', 'Distribution Analysis': '分布分析', 'Frequency Table': '频率表', 'Heat Plot': '热力图', Histogram: '直方图', 'Importance Weights': '重要性权重', 'Pearson Correlation': '皮尔逊相关系数', 'Plot of Means': '均值图', Scatterplot: '散点图', 'Violin Plot': '小提琴图',
  'Blob Convert': '二进制转换', BlockUntilDone: '等待前序完成', 'Control Container': '控制容器', 'Apache Spark Code': 'Apache Spark 代码', Detour: '分支入口', DetourEnd: '分支出口', Test: '测试', 'Field Info': '字段信息', 'JSON Schema': 'JSON 结构', Python: 'Python', 'Spark Browse': 'Spark 浏览', 'Spark DynamicInput': 'Spark 动态输入', 'Spark DynamicOutput': 'Spark 动态输出', 'Spark Filter': 'Spark 筛选', 'Spark Formula': 'Spark 公式', 'Spark Input': 'Spark 输入', 'Spark Join': 'Spark 连接', 'Spark MacroInput': 'Spark 宏输入', 'Spark MacroOutput': 'Spark 宏输出', 'Spark Output': 'Spark 输出', 'Spark Sample': 'Spark 抽样', 'Spark Select': 'Spark 选择', 'Spark StreamIn': 'Spark 流输入', 'Spark StreamOut': 'Spark 流输出', 'Spark Summarize': 'Spark 汇总', 'Spark Transpose': 'Spark 转置', 'Spark Union': 'Spark 合并', MacroBoundaryInput: '宏边界输入', Message: '消息', NaiveBayesClassifier: '朴素贝叶斯分类器', Runner: '运行器', TestOfMeans: '均值检验', Throttle: '限速', WaitASecond: '等待一秒', WaitSeconds: '等待指定秒数',
  'HTML Box': 'HTML 区块', 'Text Box (note)': '文本注释', 'Tool Container': '工具容器', 'Blob Input': '二进制输入', Browse: '浏览', 'Date Time Now (engine macro)': '当前日期时间（引擎宏）', 'Input File': '输入文件', 'Output Data (CSV)': '输出数据（CSV）', Directory: '目录', 'Run Command': '运行命令',
  Action: '动作', 'Check Box Group': '复选框组', Condition: '条件', 'Control Param': '控制参数', Date: '日期', 'Drop Down': '下拉框', Error: '错误', 'Folder Browse': '选择文件夹', Label: '标签', 'Label Group': '标签组', Link: '链接', 'List Box': '列表框', 'Macro Input': '宏输入', 'Macro Output': '宏输出', Map: '地图', 'Numeric Up Down': '数值输入', 'File Browse': '选择文件', Tab: '选项卡', 'Text Box': '文本框', 'Radio Button Group': '单选框组', Tree: '树形选择', 'Join Multiple': '多表连接', 'Jupyter Flow': 'Jupyter 流程',
  AutoML: '自动机器学习', Barcode: '条形码', BuildFeatures: '构建特征', Classification: '分类', 'Data Health': '数据健康度', FeatureTypes: '特征类型', Fit: '拟合', ImageProcessing: '图像处理', ImageProfile: '图像概况', ImageToText: '图像转文本', Insights: '数据洞察', Modeling: '建模', NamedEntityRecognition: '命名实体识别', PartOfSpeechTagger: '词性标注', Predict: '预测', Regression: '回归', Sentiment: '情感分析', TextPreProcessing: '文本预处理', TextSummary: '文本摘要', TopicModel: '主题模型', Transformation: '变换', WordCloud: '词云', ZeroShotTextClassification: '零样本文本分类',
  'Base64 Encoder': 'Base64 编码', 'Count Records': '记录计数', 'Create Samples': '创建样本', 'Data Cleansing': '数据清洗', 'Field Summary': '字段概况', Imputation: '缺失值填充', 'Multi-Field Binning': '多字段分箱', 'Oversample Field': '过采样字段', 'Random Records': '随机记录', 'Select Records': '选择记录', 'Spearman Corr Coeff': '斯皮尔曼相关系数', 'Weighted Average': '加权平均', 'Custom Macro': '自定义宏',
  'JSON Build': '构建 JSON', 'JSON Parse': '解析 JSON', 'XML Parse': '解析 XML', 'Boosted Model': '提升模型', 'Count Regression': '计数回归', 'Cross-Validation': '交叉验证', 'Decision Tree': '决策树', 'Forest Model': '随机森林模型', 'Gamma Regression': '伽马回归', 'Lift Chart': '提升图', 'Linear Regression': '线性回归', 'Logistic Regression': '逻辑回归', 'Model Coefficients': '模型系数', 'Model Comparison': '模型比较', 'Naive Bayes Classifier': '朴素贝叶斯分类器', 'Nested Test': '嵌套检验', 'Network Analysis': '网络分析', 'Neural Network': '神经网络', Score: '评分', 'Spline Model': '样条模型', Stepwise: '逐步回归', 'Support Vector Machine': '支持向量机', 'Survival Analysis': '生存分析', 'Survival Score': '生存评分', 'Test of Means': '均值检验', 'Variance Inflation Factors': '方差膨胀因子',
  'Append Cluster': '追加聚类', 'Find Nearest Neighbors': '查找最近邻', 'K-Centroids Cluster Analysis': 'K 中心聚类分析', 'K-Centroids Diagnostics': 'K 中心诊断', 'MB Affinity': '购物篮亲和度', 'MB Inspect': '购物篮检查', 'MB Rules': '购物篮规则', 'Multidimensional Scaling': '多维尺度分析', 'Principal Components': '主成分分析',
  'Append Fields': '追加字段', Arrange: '排列', 'Auto Field': '自动字段类型', 'Data Cleanse': '数据清洗', 'Dynamic Rename': '动态重命名', 'Dynamic Replace': '动态替换', 'Dynamic Select': '动态选择', 'Find Replace': '查找替换', 'Generate Rows': '生成行', 'Multi-Field Formula': '多字段公式', Tile: '分组编号',
  Optimization: '优化', 'Simulation Sampling': '模拟抽样', 'Simulation Scoring': '模拟评分', 'Simulation Summary': '模拟汇总', Email: '邮件', Layout: '布局', Render: '生成报表文件', Table: '报表表格', Text: '报表文本',
  Buffer: '缓冲区', CreatePoints: '创建点', Distance: '距离', FindNearest: '查找最近空间对象', Generalize: '简化空间对象', MakeGrid: '创建网格', MapInput: '地图输入', PolyBuild: '构建多边形', PolySplit: '拆分多边形', Smooth: '平滑', SpatialInfo: '空间信息', SpatialMatch: '空间匹配', SpatialProcess: '空间处理', TradeArea: '商圈分析', 'Text Classification': '文本分类',
  'TS Compare': '时间序列比较', 'TS Covariate Forecast': '协变量预测', 'TS Filler': '时间序列填充', 'TS Forecast': '时间序列预测', 'TS Forecast Factory': '批量序列预测', 'TS Model Factory': '批量序列建模', 'TS Plot': '时间序列图', 'Make Columns': '生成列', 'Make Group': '生成分组', 'Text to Columns': '文本分列',
};
let language: Language = 'zh';
try { if (globalThis.localStorage?.getItem(STORAGE) === 'en') language = 'en'; } catch { /* Storage is optional. */ }
export const getLanguage = (): Language => language;
export function setLanguage(next: Language): void {
  language = next;
  try { globalThis.localStorage?.setItem(STORAGE, next); } catch { /* Keep the in-memory preference. */ }
}
export function t(key: TranslationKey, values: Record<string, string | number> = {}): string {
  const value = language === 'en' ? dictionary[key] : key;
  return value.replace(/\{(\w+)\}/g, (token, name: string) => String(values[name] ?? token));
}
export function tr(value: string): string {
  if (Object.hasOwn(dictionary, value)) return t(value as TranslationKey);
  if (Object.hasOwn(catalogue, value)) return language === 'zh' ? catalogue[value]! : value;
  if (language === 'zh') return Object.entries(dictionary).find(([, english]) => english === value)?.[0] ?? value;
  return value;
}
const originals = new WeakMap<Node, string>();
export function localizeStatic(root: HTMLElement): void {
  const visit = (node: Node): void => {
    if (node instanceof Element && (node.namespaceURI === 'http://www.w3.org/2000/svg' || ['status', 'saveState', 'graphCount', 'canvasMeta', 'configTitle', 'configCategory', 'resultCount', 'resultNotice', 'runTime', 'confirmTitle', 'confirmMessage', 'tabResult'].includes(node.id))) return;
    if (node.nodeType === Node.TEXT_NODE && node.textContent?.trim()) {
      const source = originals.get(node) ?? node.textContent;
      originals.set(node, source); node.textContent = source.replace(source.trim(), tr(source.trim()));
    }
    if (node instanceof HTMLElement) {
      for (const attr of ['title', 'aria-label', 'placeholder']) {
        const key = 'i18n' + attr.replace(/-([a-z])/g, (_, c: string) => c.toUpperCase()).replace(/^./, c => c.toUpperCase());
        const source = node.dataset[key] ?? node.getAttribute(attr);
        if (source) { node.dataset[key] = source; node.setAttribute(attr, tr(source)); }
      }
      if (node.hasAttribute('data-i18n-skip') || ['INPUT', 'TEXTAREA', 'SELECT', 'PRE'].includes(node.tagName)) return;
    }
    node.childNodes.forEach(visit);
  };
  visit(root); document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en'; document.title = 'Alteryx2Python · ' + t('工作流');
}
