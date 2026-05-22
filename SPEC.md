Below is a comprehensive **foundation / constitution spec** for your Alteryx-to-Python AI migration project. I wrote it as a document you can give directly to an AI agent, engineering team, reviewer, or governance group.

I’m intentionally making it strict, because your core risk is not that the AI cannot write Python — it is that the AI writes *plausible, elegant, optimized Python that no longer behaves like Alteryx*. Internal migration context also supports that this needs to be treated carefully: the Alteryx migration material says alternatives depend on workflow complexity and calls out complex tools/custom code such as Python, R, CMD, API, Blob, ML, custom code, and third-party macros as special cases; the FAQ also explicitly says Fabric is not a 1:1 replacement and that some Alteryx features may not be replicated. [\[Alteryx Mi...ion Update \| SharePoint\]](https://ubscloud.sharepoint.com/teams/TechServicesDataScience/SitePages/Alteryx-Migration-Update.aspx?web=1), [\[FAQs - Alt...ly Roadmap \| SharePoint\]](https://ubscloud.sharepoint.com/teams/TechServicesDataScience/Alteryx/SitePages/FAQs-related-t.aspx?web=1)

***

# Alteryx-to-Python Migration Constitution

## Canonical Specification for AI-Agent-Based 1:1 Workflow Transformation

**Document status:** Foundation specification  
**Primary objective:** Faithful, testable, explainable, modular migration of Alteryx workflows to Python  
**Non-objective:** Producing the shortest, most idiomatic, or most optimized pandas code  
**Guiding motto:**

> **Correctness before elegance. Alteryx semantics before Python idioms. Node-level equivalence before workflow-level optimization.**

***

## 1. Purpose

This document defines the mandatory rules, architectural constraints, transformation principles, testing expectations, and escalation criteria for converting Alteryx workflows into Python.

The purpose of the migration is to reproduce Alteryx workflow behavior as faithfully as possible in Python, such that for the same approved input data, the generated Python implementation produces the same output as the original Alteryx workflow, subject only to explicitly documented and approved differences.

This document must be treated as the **constitution** for all AI agents, code generators, reviewers, testing frameworks, and migration utilities involved in the project.

No AI agent, developer, reviewer, optimizer, or automation process may override this specification unless an exception is explicitly recorded, reviewed, and approved.

***

## 2. Core Migration Principle

The migration must preserve Alteryx execution semantics.

The generated Python must behave as an **Alteryx-compatible execution graph**, not as a generic pandas script.

Alteryx workflows are:

* graph-based;
* node-oriented;
* anchor-driven;
* modular;
* configuration-heavy;
* tool-semantics-driven;
* sensitive to ordering, typing, null handling, and intermediate behavior.

Therefore, Python migration must preserve:

* the workflow graph;
* the individual Alteryx tool boundaries;
* input/output anchors;
* tool configuration;
* schema transformations;
* row counts;
* column order;
* data types;
* intermediate outputs;
* warnings and error behavior where known;
* final outputs.

The AI agent must never assume that a visually obvious pandas simplification is semantically safe.

***

## 3. Absolute Non-Negotiable Rules

The following rules are mandatory.

### Rule 1: One Alteryx tool maps to one Python node by default

Each Alteryx tool instance must be represented as one corresponding Python execution node.

If an Alteryx workflow contains:

```text
Input → Select → Filter → Formula → Summarize → Output
```

the generated Python must preserve that structure:

```python
node_1 = input_tool(config_1)
node_2 = select_tool(node_1, config_2)
node_3_true, node_3_false = filter_tool(node_2, config_3)
node_4 = formula_tool(node_3_true, config_4)
node_5 = summarize_tool(node_4, config_5)
output_tool(node_5, config_6)
```

The AI agent must not collapse the workflow into:

```python
df = (
    pd.read_csv(...)
      .query(...)
      .assign(...)
      .groupby(...)
)
```

unless this is generated as a **separate optional optimized layer** after baseline equivalence has already been proven.

***

### Rule 2: Baseline faithful migration comes before optimization

The first generated Python implementation must be the **baseline faithful implementation**.

The baseline implementation must prioritize:

1. semantic equivalence;
2. node-level traceability;
3. testability;
4. debuggability;
5. schema preservation;
6. reproducibility.

Optimization is explicitly secondary.

Optimized Python may only be produced after:

* the baseline implementation passes workflow-level golden-output comparison;
* all node-level tests pass;
* tool-level semantic tests pass;
* intermediate outputs are either verified or explicitly waived;
* the optimization preserves a reversible mapping to the original Alteryx graph;
* the optimized implementation is marked as non-canonical unless separately certified.

***

### Rule 3: Alteryx semantics override pandas semantics

If pandas, NumPy, Python, Spark, Polars, DuckDB, or any other runtime behaves differently from Alteryx, the Python implementation must emulate Alteryx.

This applies even when pandas behavior appears more natural, efficient, or conventional.

Known areas requiring special care include:

* null handling;
* empty string handling;
* whitespace handling;
* data type inference;
* numeric precision;
* integer-to-float coercion;
* decimal rounding;
* date parsing;
* datetime timezone behavior;
* string comparison;
* case sensitivity;
* boolean truthiness;
* formula expression evaluation;
* missing fields;
* duplicate column names;
* column order;
* row order;
* sort stability;
* join ordering;
* duplicate key joins;
* multi-anchor outputs;
* warning versus error behavior;
* output formatting.

The AI agent must not silently accept Python-native behavior when Alteryx behavior is different, unknown, or ambiguous.

***

### Rule 4: The AI agent must not infer business intent

The workflow structure and configuration define the migration behavior.

The AI agent must not infer business intent beyond what is explicitly represented in:

* the Alteryx workflow file;
* tool configuration;
* input/output metadata;
* golden datasets;
* approved migration annotations;
* documented business rules;
* approved user comments;
* approved macro definitions.

The agent must not decide that a filter is obsolete, that a column is unnecessary, that a formula can be simplified, or that two steps are “clearly equivalent” based on intuition.

If business semantics are required to determine correctness, the workflow must be escalated.

***

### Rule 5: Unknown behavior must be escalated, not guessed

If the agent encounters unsupported, ambiguous, undocumented, or partially understood behavior, it must stop and classify the issue.

Acceptable classifications include:

```text
UNSUPPORTED_TOOL
AMBIGUOUS_SEMANTICS
MISSING_INPUT_SCHEMA
MISSING_GOLDEN_OUTPUT
CUSTOM_CODE_REQUIRED
MACRO_UNRESOLVED
EXTERNAL_DEPENDENCY
BUSINESS_RULE_REQUIRED
NON_DETERMINISTIC_BEHAVIOR
OWNER_REVIEW_REQUIRED
```

The AI agent must not silently generate approximate logic.

***

### Rule 6: Final-output equality alone is insufficient

A migrated workflow cannot be certified solely because one final output matches one Alteryx run.

Certification requires evidence across multiple levels:

1. tool-level semantic tests;
2. node-level tests;
3. graph-level wiring tests;
4. workflow-level golden-output tests;
5. schema comparison;
6. row count comparison;
7. column order comparison;
8. data type comparison;
9. edge-case coverage;
10. documented treatment of unsupported features.

Final-output equality is useful, but it is not a proof of correctness.

***

## 4. Scope

This specification applies to all components involved in the migration, including:

* Alteryx workflow parsers;
* XML/YXMD/YXMC/YXWZ readers;
* intermediate representation builders;
* tool semantic libraries;
* AI prompt templates;
* AI code generation agents;
* Python DAG builders;
* generated Python code;
* test harnesses;
* golden-output comparison utilities;
* workflow classification tools;
* review dashboards;
* exception logs;
* optimization engines;
* documentation generators.

***

## 5. Definitions

### 5.1 Alteryx workflow

An Alteryx workflow is the source artifact describing a graph of configured tools connected by anchors.

Typical workflow artifacts may include:

```text
.yxmd
.yxmc
.yxwz
```

The workflow is the source of structural truth.

***

### 5.2 Tool

A tool is an individual Alteryx operation, such as:

```text
Input Data
Select
Filter
Formula
Join
Union
Summarize
Sort
Unique
Sample
Multi-Row Formula
Multi-Field Formula
Transpose
Cross Tab
Output Data
```

Each tool instance has:

* a unique ID;
* a tool type;
* configuration;
* input anchors;
* output anchors;
* metadata;
* position in the graph.

***

### 5.3 Node

A Python node is the generated Python representation of one Alteryx tool instance.

Each node must have:

* node ID;
* source Alteryx tool ID;
* tool type;
* input references;
* output references;
* configuration object;
* execution function;
* output metadata;
* test hooks;
* trace hooks.

***

### 5.4 Anchor

An anchor is a named input or output port on an Alteryx tool.

Examples:

```text
Input anchor
Output anchor
True anchor
False anchor
Left anchor
Right anchor
Join anchor
Left Unjoined anchor
Right Unjoined anchor
```

Python migration must preserve anchor semantics.

***

### 5.5 Canonical Intermediate Representation

The Canonical Intermediate Representation, or IR, is the normalized internal model of the Alteryx workflow.

It sits between Alteryx XML and generated Python.

The migration path must be:

```text
Alteryx workflow file
    ↓
Parsed Alteryx model
    ↓
Canonical Workflow IR
    ↓
Python DAG
    ↓
Executable Python baseline
    ↓
Tested migration artifact
```

Direct Alteryx XML to free-form Python generation is prohibited for production migration.

***

### 5.6 Baseline implementation

The baseline implementation is the first faithful Python implementation generated from the workflow.

It must preserve node boundaries and Alteryx semantics.

The baseline implementation is the canonical migration output.

***

### 5.7 Optimized implementation

The optimized implementation is a secondary, optional Python implementation that may combine operations or use more efficient execution patterns.

It must never replace the baseline unless separately certified.

***

### 5.8 Golden dataset

A golden dataset is an approved input and output dataset pair generated or validated against the original Alteryx workflow.

Golden datasets are used to verify equivalence.

***

### 5.9 Equivalence

Equivalence means that the Python implementation reproduces the Alteryx result under defined comparison rules.

Equivalence may be:

```text
EXACT
TOLERANCE_BASED
SCHEMA_ONLY
MANUALLY_APPROVED_DIFFERENCE
NOT_EQUIVALENT
```

Exact equivalence is preferred.

Tolerance-based equivalence must be explicitly justified.

***

## 6. Architectural Requirements

### 6.1 Required architecture

The migration system must use the following architecture:

```text
+-------------------------+
| Alteryx Source Workflow |
+-------------------------+
            |
            v
+-------------------------+
| Source Parser           |
+-------------------------+
            |
            v
+-------------------------+
| Canonical Workflow IR   |
+-------------------------+
            |
            v
+-------------------------+
| Semantic Validator      |
+-------------------------+
            |
            v
+-------------------------+
| Python DAG Generator    |
+-------------------------+
            |
            v
+-------------------------+
| Tool Semantics Library  |
+-------------------------+
            |
            v
+-------------------------+
| Baseline Python Runtime |
+-------------------------+
            |
            v
+-------------------------+
| Test Harness            |
+-------------------------+
            |
            v
+-------------------------+
| Certification Report    |
+-------------------------+
```

The AI agent may participate in parts of this process, but it must operate within the constraints of this architecture.

***

### 6.2 Prohibited architecture

The following architecture is prohibited for certified migration:

```text
Alteryx workflow
    ↓
AI prompt
    ↓
Free-form pandas script
```

This is not acceptable because it bypasses:

* canonical IR;
* tool-level semantics;
* node-level mapping;
* anchor preservation;
* intermediate testing;
* equivalence traceability;
* controlled escalation.

***

## 7. Canonical Intermediate Representation Specification

Every workflow must be converted into an IR before Python generation.

### 7.1 IR workflow object

The IR must contain:

```yaml
workflow:
  workflow_id: string
  workflow_name: string
  source_file: string
  source_hash: string
  parser_version: string
  migration_spec_version: string
  nodes: list
  edges: list
  inputs: list
  outputs: list
  macros: list
  external_dependencies: list
  warnings: list
  errors: list
  classification: string
```

***

### 7.2 IR node object

Each node must contain:

```yaml
node:
  node_id: string
  source_tool_id: string
  tool_type: string
  tool_name: string
  config: object
  input_anchors: list
  output_anchors: list
  incoming_edges: list
  outgoing_edges: list
  expected_input_schema: object
  expected_output_schema: object
  execution_semantics_version: string
  supported_status: string
  warnings: list
  errors: list
```

***

### 7.3 IR edge object

Each edge must contain:

```yaml
edge:
  edge_id: string
  source_node_id: string
  source_anchor: string
  target_node_id: string
  target_anchor: string
  metadata: object
```

***

### 7.4 IR validation requirements

Before Python generation, the IR must be validated for:

* unique node IDs;
* valid edge references;
* valid anchor references;
* acyclic graph, unless explicitly supported loop constructs exist;
* complete tool configuration;
* known tool type;
* supported anchors;
* available input sources;
* output destinations;
* macro resolution;
* external dependency resolution;
* schema availability where required.

Invalid IR must not produce certified Python.

***

## 8. Python Runtime Requirements

### 8.1 Runtime style

Generated Python must execute as a graph of nodes.

A recommended style is:

```python
context = WorkflowContext()

node_1_out = run_node(
    node_id="1",
    tool_type="InputData",
    function=input_data_tool,
    inputs={},
    config=config_1,
    context=context,
)

node_2_out = run_node(
    node_id="2",
    tool_type="Select",
    function=select_tool,
    inputs={"Input": node_1_out["Output"]},
    config=config_2,
    context=context,
)
```

The exact implementation may vary, but the runtime must preserve node-level identity and traceability.

***

### 8.2 Required node function signature

Each tool implementation should follow a stable contract.

Example:

```python
def select_tool(inputs: dict, config: dict, context: WorkflowContext) -> dict:
    """
    Executes one Alteryx Select tool.
    
    inputs:
        Anchor-name-to-dataframe mapping.
    
    config:
        Parsed Alteryx tool configuration.
    
    context:
        Runtime context, logging, tracing, schema policy, comparison policy.
    
    returns:
        Anchor-name-to-dataframe mapping.
    """
```

All tools must return a dictionary keyed by output anchor name.

***

### 8.3 Tool implementation requirements

Each tool implementation must define:

```yaml
tool_semantics:
  tool_type: string
  supported_alteryx_versions: list
  semantics_version: string
  input_anchors: list
  output_anchors: list
  config_schema: object
  input_schema_rules: object
  output_schema_rules: object
  null_handling_rules: object
  type_handling_rules: object
  ordering_rules: object
  error_rules: object
  warning_rules: object
  test_suite: list
```

***

### 8.4 Traceability requirements

Each executed node must record:

* source tool ID;
* Python node ID;
* tool type;
* input row count per anchor;
* output row count per anchor;
* input schema per anchor;
* output schema per anchor;
* column order;
* data types;
* null counts;
* execution status;
* warnings;
* errors;
* data hash where enabled;
* sample rows where enabled and permitted.

***

## 9. AI Agent Rules

### 9.1 AI agent role

The AI agent may assist with:

* parsing support;
* IR generation;
* tool configuration extraction;
* Python node code generation;
* test generation;
* documentation generation;
* error explanation;
* migration classification;
* reviewer assistance.

The AI agent must not be the sole authority on correctness.

Correctness must be determined by:

* this specification;
* canonical tool semantics;
* deterministic tests;
* golden-output comparison;
* approved exceptions.

***

### 9.2 AI agent must obey the specification hierarchy

When generating output, the AI agent must follow this priority order:

```text
1. This migration constitution
2. Approved tool semantic specifications
3. Canonical IR
4. Alteryx source workflow configuration
5. Approved golden datasets
6. Approved exception records
7. Project coding standards
8. Python idioms
9. AI model discretion
```

AI discretion is the lowest-priority authority.

***

### 9.3 Forbidden AI behaviors

The AI agent must not:

* combine multiple Alteryx tools into one Python function in the baseline implementation;
* remove intermediate nodes;
* drop columns unless the Alteryx tool explicitly does so;
* reorder columns unless the Alteryx tool explicitly does so;
* reorder rows unless the Alteryx semantics require or allow it;
* replace explicit workflow logic with inferred business meaning;
* infer missing formulas;
* silently ignore unsupported tools;
* silently ignore unsupported macros;
* silently ignore external dependencies;
* convert custom code approximately;
* change data types for convenience;
* use pandas defaults without checking Alteryx semantics;
* assume null behavior;
* assume date parsing behavior;
* assume join behavior;
* assume sort stability;
* generate optimized code as the canonical implementation;
* present unverified migration as certified;
* mark workflows as equivalent without passing required tests.

***

### 9.4 Required AI behavior when uncertain

When uncertain, the AI agent must produce an explicit uncertainty record.

Example:

```yaml
uncertainty:
  node_id: "17"
  tool_type: "Formula"
  issue_type: "AMBIGUOUS_SEMANTICS"
  description: "Formula uses function whose Alteryx semantics are not mapped."
  required_action: "Add semantic implementation or request review."
  certification_blocking: true
```

The AI agent must prefer escalation over guessing.

***

## 10. Tool Semantics Library

### 10.1 Purpose

The tool semantics library is the trusted implementation of Alteryx tool behavior in Python.

The AI agent must call this library instead of rewriting each tool from scratch.

***

### 10.2 Tool maturity levels

Each tool implementation must have a maturity level:

```text
L0_NOT_STARTED
L1_PARSED_ONLY
L2_BASIC_IMPLEMENTATION
L3_EDGE_CASE_TESTED
L4_GOLDEN_VALIDATED
L5_CERTIFIED
```

Only L5 tools may be used in certified fully automated migration.

L3 or L4 tools may be used with review.

L0 to L2 tools must trigger escalation.

***

### 10.3 Minimum tool contract

Each supported Alteryx tool must have:

1. semantic description;
2. config parser;
3. Python implementation;
4. unit tests;
5. edge-case tests;
6. schema tests;
7. null tests;
8. ordering tests;
9. error tests;
10. golden comparison tests;
11. version tag;
12. known limitations.

***

## 11. Required Semantics by Category

### 11.1 Schema semantics

For every node, the implementation must define:

* which columns are retained;
* which columns are added;
* which columns are removed;
* column order;
* duplicate name behavior;
* rename behavior;
* type change behavior;
* metadata propagation;
* unknown field behavior.

Column order must be treated as significant unless explicitly declared otherwise.

***

### 11.2 Row semantics

For every node, the implementation must define:

* whether row count is preserved;
* whether row order is preserved;
* whether rows may be filtered;
* whether rows may be duplicated;
* whether rows may be aggregated;
* whether rows may be generated;
* whether sort order changes;
* whether grouping order matters.

***

### 11.3 Type semantics

The implementation must define handling for:

* string;
* integer;
* floating point;
* fixed decimal;
* boolean;
* date;
* datetime;
* time;
* blob/binary;
* spatial objects, if applicable;
* unknown or unsupported types.

No automatic type coercion may be introduced unless it matches Alteryx behavior.

***

### 11.4 Null and missing value semantics

The implementation must explicitly define behavior for:

* null;
* empty string;
* blank string;
* whitespace-only string;
* zero;
* false;
* missing field;
* NaN;
* NaT;
* Python None;
* pandas NA.

The AI agent must not treat these as interchangeable.

***

### 11.5 Formula semantics

Formula tools require special handling because formula languages differ.

The migration must not translate formula expressions directly into arbitrary Python expressions without passing through a controlled expression parser.

Required formula migration path:

```text
Alteryx formula text
    ↓
Alteryx formula parser
    ↓
Canonical expression AST
    ↓
Validated semantic mapping
    ↓
Python expression/runtime
    ↓
Formula test cases
```

Direct free-form AI translation from Alteryx formula to Python is prohibited for certified migration.

***

### 11.6 Join semantics

Join tools must preserve:

* left input anchor;
* right input anchor;
* join keys;
* joined output anchor;
* left-unjoined output anchor;
* right-unjoined output anchor;
* duplicate-key behavior;
* null-key behavior;
* output column naming;
* output column order;
* row ordering;
* type coercion rules.

The AI agent must not replace a Join tool with a simple `pandas.merge` unless the wrapper explicitly enforces Alteryx-compatible behavior.

***

### 11.7 Filter semantics

Filter tools must preserve:

* true anchor output;
* false anchor output;
* expression semantics;
* null handling;
* type coercion;
* error behavior;
* row order.

A filter must return both outputs if both anchors exist or are used downstream.

***

### 11.8 Select semantics

Select tools must preserve:

* selected fields;
* deselected fields;
* renamed fields;
* reordered fields;
* type changes;
* size changes;
* unknown field behavior;
* duplicate field handling.

Select is not merely a pandas column subset.

***

### 11.9 Summarize semantics

Summarize tools must preserve:

* group-by fields;
* aggregation operations;
* aggregation names;
* output order;
* null aggregation behavior;
* type output behavior;
* empty group behavior;
* numeric precision;
* count behavior;
* distinct count behavior.

***

### 11.10 Sort semantics

Sort tools must preserve:

* sort keys;
* ascending/descending direction;
* data type comparison behavior;
* null ordering;
* stability;
* locale or string comparison behavior where known.

***

### 11.11 Union semantics

Union tools must preserve:

* field alignment mode;
* output column order;
* missing field behavior;
* type mismatch behavior;
* row ordering by input anchor/order;
* warning/error behavior.

***

### 11.12 Multi-row and multi-field semantics

Multi-row and multi-field tools must be treated as high-risk.

They require explicit semantic implementation and edge-case tests for:

* row offsets;
* group boundaries;
* initial values;
* missing previous/next rows;
* type handling;
* formula evaluation;
* field iteration order.

***

### 11.13 Custom tools, macros, and external tools

The following must be classified as high-risk unless fully resolved:

* custom macros;
* chained macros;
* batch macros;
* iterative macros;
* Python tools;
* R tools;
* Run Command tools;
* API calls;
* Blob tools;
* ML tools;
* third-party macros;
* external scripts;
* database stored procedures;
* manual file dependencies.

Internal migration context also identifies complex advanced tools and custom code, including Python, R, CMD, API, Blob, ML, custom code, and third-party macros, as special cases where alternatives depend on workflow complexity. [\[Alteryx Mi...ion Update \| SharePoint\]](https://ubscloud.sharepoint.com/teams/TechServicesDataScience/SitePages/Alteryx-Migration-Update.aspx?web=1)

Such workflows must not be marked fully auto-migrated unless the external behavior is captured and tested.

***

## 12. Workflow Classification

Each workflow must receive a classification before migration certification.

### 12.1 Classification levels

```text
CLASS_A_AUTO_SAFE
CLASS_B_AUTO_WITH_GOLDEN_TEST
CLASS_C_REVIEW_REQUIRED
CLASS_D_PARTIAL_MIGRATION_ONLY
CLASS_E_UNSUPPORTED
```

***

### 12.2 Class A: Auto-safe

A workflow may be Class A only if:

* all tools are certified;
* all configs are parsed;
* all inputs are available;
* no custom code exists;
* no unresolved macros exist;
* no external side effects exist;
* golden-output tests pass;
* no semantic warnings remain.

***

### 12.3 Class B: Auto with golden test

A workflow may be Class B if:

* tools are supported;
* some edge cases require golden-output confirmation;
* no unsupported tool exists;
* no unresolved business rule exists;
* golden-output comparison passes.

***

### 12.4 Class C: Review required

A workflow must be Class C if:

* tool semantics are partially supported;
* formulas contain ambiguous functions;
* data types are uncertain;
* outputs differ within unapproved areas;
* custom macros are present but partially understood;
* owner validation is needed.

***

### 12.5 Class D: Partial migration only

A workflow must be Class D if:

* only part of the workflow can be translated;
* unsupported tools exist;
* external systems are required;
* manual steps exist;
* custom code cannot be resolved.

***

### 12.6 Class E: Unsupported

A workflow must be Class E if:

* critical behavior cannot be parsed;
* workflow graph cannot be built;
* required inputs are unavailable;
* custom behavior cannot be reproduced;
* no meaningful test can be performed.

***

## 13. Testing Constitution

Testing is not optional.

No migrated workflow may be certified without passing the required tests for its class.

***

### 13.1 Test levels

The migration project must include the following levels of testing:

```text
1. Parser tests
2. IR validation tests
3. Tool semantic unit tests
4. Tool edge-case tests
5. Node-level tests
6. Anchor-level tests
7. Schema tests
8. Workflow graph tests
9. Golden-output tests
10. Regression tests
11. Performance sanity tests
12. Exception and warning tests
```

***

### 13.2 Tool-level tests

Each tool must have dedicated tests for:

* normal input;
* empty input;
* single-row input;
* null-heavy input;
* mixed-type input;
* duplicate columns;
* missing columns;
* unexpected types;
* boundary numeric values;
* date edge cases;
* string edge cases;
* ordering;
* schema preservation;
* error behavior.

***

### 13.3 Interaction tests

Tool interaction tests must verify that combinations behave correctly.

Examples:

```text
Select → Formula
Formula → Filter
Filter → Join
Join → Summarize
Union → Select
Sort → Unique
Multi-row Formula → Filter
Transpose → Cross Tab
```

This is necessary because a tool may pass unit tests but fail when chained with another tool due to schema, type, or ordering differences.

***

### 13.4 Workflow-level golden-output tests

For each migrated workflow, the system must compare Python outputs against Alteryx outputs.

Comparison must include:

* file presence;
* sheet/table presence, where applicable;
* row count;
* column count;
* column names;
* column order;
* data types;
* null counts;
* values;
* row order, if significant;
* formatting, where relevant;
* output path/name, where relevant.

***

### 13.5 Intermediate-output testing

Where possible, intermediate outputs must be captured and compared at node boundaries.

If intermediate Alteryx outputs cannot be captured, the certification report must say so.

Intermediate-output testing is especially important for:

* high-risk tools;
* joins;
* formulas;
* multi-row formulas;
* type conversions;
* sorting;
* aggregations;
* macros;
* workflows with mismatching final outputs.

***

### 13.6 Data comparison modes

Comparison must support the following modes:

```text
EXACT_VALUE_MATCH
EXACT_SCHEMA_MATCH
ORDER_INSENSITIVE_VALUE_MATCH
NUMERIC_TOLERANCE_MATCH
DATETIME_TOLERANCE_MATCH
STRING_NORMALIZED_MATCH
MANUAL_REVIEW_REQUIRED
```

The default mode is exact value match.

Tolerance-based comparison must be explicitly configured and justified.

***

### 13.7 No silent tolerance

The test framework must not silently allow differences.

Every difference must be classified as:

```text
ACCEPTED
REJECTED
UNDER_REVIEW
IGNORED_BY_POLICY
UNSUPPORTED_COMPARISON
```

Any ignored difference must have a documented reason.

***

## 14. Certification Report Requirements

Every migrated workflow must produce a certification report.

The report must include:

```yaml
certification_report:
  workflow_id: string
  workflow_name: string
  source_file: string
  source_hash: string
  migration_timestamp: string
  migration_spec_version: string
  parser_version: string
  generator_version: string
  runtime_version: string
  classification: string
  certification_status: string
  tools_total: integer
  tools_supported: integer
  tools_unsupported: integer
  warnings: list
  errors: list
  golden_tests: list
  node_tests: list
  schema_comparison: object
  output_comparison: object
  exceptions: list
  reviewer_notes: list
```

Certification status must be one of:

```text
CERTIFIED_EQUIVALENT
CERTIFIED_WITH_APPROVED_DIFFERENCES
NOT_CERTIFIED
PARTIAL_ONLY
FAILED
BLOCKED
```

***

## 15. Exception Management

### 15.1 Exception requirement

Any deviation from this specification must be recorded as an exception.

Exceptions must include:

```yaml
exception:
  exception_id: string
  workflow_id: string
  node_id: string
  rule_violated: string
  reason: string
  risk: string
  approved_by: string
  approval_date: string
  expiry_date: string
  test_evidence: string
```

***

### 15.2 Examples of exceptions

Examples include:

* combining two nodes after equivalence proof;
* allowing numeric tolerance;
* accepting output row order differences;
* replacing a custom macro with approved Python logic;
* excluding unused output anchors;
* manually approving business-rule behavior.

***

### 15.3 Forbidden exceptions

The following must not be approved as routine exceptions:

* skipping tests because the workflow is “simple”;
* accepting unverified AI-generated formula logic;
* ignoring unsupported tools;
* deleting nodes for convenience;
* changing output schema without approval;
* changing business logic without owner approval;
* certifying without golden-output evidence.

***

## 16. AI Prompting Requirements

All AI prompts used for migration must include the constitutional rules.

A minimum prompt header should include:

```text
You are migrating Alteryx workflows to Python under a strict equivalence constitution.

Your task is not to write idiomatic pandas code.
Your task is to preserve Alteryx semantics.

You must:
- preserve one Python node per Alteryx tool;
- preserve anchors;
- preserve schema;
- preserve row behavior;
- preserve column order;
- use canonical tool implementations;
- avoid optimization;
- escalate uncertainty;
- never infer business intent;
- never silently approximate unsupported behavior.
```

***

### 16.1 Required AI output structure

When generating migration output, the AI agent must produce:

```text
1. Workflow summary
2. Parsed node list
3. Parsed edge list
4. Unsupported or ambiguous items
5. Generated IR
6. Generated Python DAG code
7. Required tests
8. Golden-output comparison plan
9. Certification readiness status
10. Escalation items
```

***

### 16.2 Required AI self-check

Before returning generated code, the AI agent must answer:

```text
- Did I preserve every Alteryx node?
- Did I preserve every edge?
- Did I preserve every anchor?
- Did I preserve column order?
- Did I preserve row order where required?
- Did I use canonical tool implementations?
- Did I avoid combining tools?
- Did I avoid business assumptions?
- Did I classify unsupported behavior?
- Did I generate tests?
```

If any answer is “no,” the output must be marked not certified.

***

## 17. Generated Python Code Standards

### 17.1 Code organization

Generated code should be organized as:

```text
migration_project/
  workflows/
    workflow_<id>/
      workflow_ir.yaml
      baseline.py
      optimized_optional.py
      configs/
      tests/
      reports/
  alteryx_runtime/
    tools/
    expressions/
    schemas/
    comparison/
    tracing/
```

***

### 17.2 Baseline code requirements

`baseline.py` must:

* be deterministic;
* preserve node order by topological execution;
* use canonical tool functions;
* not combine tools;
* include node IDs;
* include source tool IDs;
* log node execution;
* support trace output;
* support test mode;
* support golden comparison.

***

### 17.3 Example baseline style

```python
from alteryx_runtime.context import WorkflowContext
from alteryx_runtime.tools import (
    input_data_tool,
    select_tool,
    filter_tool,
    formula_tool,
    output_data_tool,
)

def run_workflow(runtime_config):
    context = WorkflowContext(runtime_config)

    n1 = input_data_tool(
        inputs={},
        config=runtime_config["nodes"]["1"],
        context=context,
    )

    n2 = select_tool(
        inputs={"Input": n1["Output"]},
        config=runtime_config["nodes"]["2"],
        context=context,
    )

    n3 = filter_tool(
        inputs={"Input": n2["Output"]},
        config=runtime_config["nodes"]["3"],
        context=context,
    )

    n4 = formula_tool(
        inputs={"Input": n3["True"]},
        config=runtime_config["nodes"]["4"],
        context=context,
    )

    output_data_tool(
        inputs={"Input": n4["Output"]},
        config=runtime_config["nodes"]["5"],
        context=context,
    )

    return context.execution_report()
```

***

### 17.4 Prohibited baseline style

```python
df = pd.read_csv(path)
df = df[df["Amount"] > 0]
df["Net"] = df["Amount"] - df["Fee"]
df = df[["Account", "Net"]]
df.to_csv(out)
```

This style is prohibited as a baseline because it hides the original tool boundaries.

***

## 18. Formula Translation Specification

Formula translation is one of the highest-risk areas.

### 18.1 Formula migration pipeline

Formula migration must follow:

```text
Raw Alteryx expression
    ↓
Lexing
    ↓
Parsing
    ↓
Canonical expression AST
    ↓
Function mapping
    ↓
Type/null validation
    ↓
Python runtime expression
    ↓
Expression unit tests
```

***

### 18.2 Formula function registry

Each supported formula function must have:

```yaml
function:
  alteryx_name: string
  canonical_name: string
  python_implementation: string
  argument_rules: object
  null_rules: object
  type_rules: object
  test_cases: list
  known_differences: list
```

***

### 18.3 Formula uncertainty

If any formula function is unknown, partially supported, or context-dependent, the node must be marked:

```text
AMBIGUOUS_SEMANTICS
```

or:

```text
UNSUPPORTED_FORMULA_FUNCTION
```

The agent must not invent a Python equivalent.

***

## 19. Data Source and Output Handling

### 19.1 Input sources

Input sources must be represented explicitly.

The migration must capture:

* input path;
* file type;
* sheet/table name;
* delimiter;
* encoding;
* header behavior;
* schema inference behavior;
* missing file behavior;
* connection string, if applicable;
* database query, if applicable.

***

### 19.2 Output destinations

Output tools must preserve:

* output path;
* file type;
* overwrite/append behavior;
* sheet/table name;
* delimiter;
* encoding;
* header behavior;
* formatting behavior, where relevant;
* database write behavior, where relevant.

***

### 19.3 External systems

If a workflow depends on external systems, the migration must document them.

Examples:

```text
database
shared drive
SharePoint
API
macro repository
local file path
network path
credential store
scheduler
Alteryx Gallery
```

If the external dependency cannot be reproduced in Python, certification must be blocked or limited.

***

## 20. Governance and Review

### 20.1 Review gates

A workflow must pass through these gates:

```text
Gate 1: Parse successful
Gate 2: IR valid
Gate 3: Tool support sufficient
Gate 4: Baseline Python generated
Gate 5: Tool tests pass
Gate 6: Workflow tests pass
Gate 7: Golden-output comparison pass
Gate 8: Exceptions reviewed
Gate 9: Certification report generated
Gate 10: Release approval
```

***

### 20.2 Required reviewer focus

Reviewers must check:

* whether all Alteryx nodes are represented;
* whether anchors are preserved;
* whether generated code uses canonical tool functions;
* whether unsupported tools are escalated;
* whether formula translation is verified;
* whether tests are meaningful;
* whether output comparison is strict enough;
* whether exceptions are justified.

***

## 21. Migration Workflow

The standard migration process is:

```text
1. Ingest workflow file
2. Compute source hash
3. Parse workflow XML/config
4. Build canonical IR
5. Validate graph
6. Classify workflow complexity
7. Resolve macros and dependencies
8. Generate baseline Python DAG
9. Generate node-level tests
10. Run tool-level tests
11. Run baseline Python
12. Run or retrieve Alteryx golden output
13. Compare outputs
14. Produce certification report
15. Escalate unresolved issues
16. Optionally generate optimized implementation
17. Re-test optimized implementation against baseline and golden outputs
```

***

## 22. Risk-Based Owner Engagement

The migration should not require speaking to every workflow owner.

However, the system must trigger owner or SME review when structural evidence is insufficient.

### 22.1 No owner review required when

Owner review may be skipped only when:

* all tools are supported and certified;
* all inputs are available;
* golden-output tests pass;
* no unsupported macros exist;
* no custom code exists;
* no output differences exist;
* no business assumptions are required.

***

### 22.2 Owner review required when

Owner or SME review is required when:

* output differences exist;
* custom code exists;
* macros cannot be resolved;
* business rules are embedded but unclear;
* input data is unavailable;
* output purpose is unclear;
* downstream dependency is unknown;
* hardcoded thresholds/dates require interpretation;
* workflow contains manual steps;
* golden-output test data is insufficient;
* high-risk tools are used.

***

## 23. Handling High-Risk Workflows

High-risk workflows must receive additional scrutiny.

A workflow is high-risk if it contains:

* financial control logic;
* regulatory reporting logic;
* reconciliation logic;
* production automation;
* complex joins;
* random sampling;
* custom code;
* external commands;
* macros;
* database writes;
* API calls;
* non-deterministic operations;
* manually maintained input files.

An internal “Stay on Alteryx” example describes workflows used for process control checks, file comparisons, random samples, and output files, emphasizing consistency, reliability, repeatability, and auditability; such patterns should be treated as high-risk and should not rely on “looks equivalent” migration. [\[Stay on Alteryx \| Excel\]](https://ubscloud.sharepoint.com/teams/TechServicesDataScience/_layouts/15/Doc.aspx?sourcedoc=%7BA7A07BEE-12A2-40E5-99A5-C7D8BC8B5BAA%7D&file=Stay%20on%20Alteryx.xlsx&action=default&mobileredirect=true&DefaultItemOpen=1)

***

## 24. Equivalence Policy

### 24.1 Default equivalence

The default equivalence requirement is:

```text
same inputs → same outputs
```

Where “same outputs” means:

* same rows;
* same columns;
* same values;
* same column order;
* same row order, where significant;
* same data types, where observable;
* same output files/tables;
* same null/blank behavior.

***

### 24.2 Approved differences

Differences may be accepted only if documented.

Examples:

```text
floating point representation difference within approved tolerance
timestamp formatting difference approved by downstream consumer
row order difference where order is proven irrelevant
metadata-only difference
file formatting difference with identical data payload
```

***

### 24.3 Unapproved differences

The following are not acceptable without explicit review:

* missing rows;
* extra rows;
* changed filter behavior;
* changed join behavior;
* changed aggregation result;
* changed null handling;
* changed column name;
* changed column order;
* changed data type;
* changed output destination;
* changed business rule.

***

## 25. Logging and Auditability

The migration runtime must produce logs sufficient for audit.

Logs must include:

* workflow ID;
* source hash;
* runtime version;
* tool semantics version;
* node execution order;
* row counts;
* schema changes;
* warnings;
* errors;
* comparison results;
* exception references.

For sensitive workflows, logs must avoid exposing confidential data values unless explicitly approved.

***

## 26. Security and Data Handling

The migration system must respect data governance requirements.

It must not:

* send confidential data to unapproved systems;
* expose sensitive data in prompts;
* store golden datasets in uncontrolled locations;
* log full data values unnecessarily;
* use AI services with unapproved data exposure;
* bypass access controls.

When using AI, prefer structural metadata, configs, schemas, and synthetic examples unless real data use is approved.

***

## 27. Performance Policy

Performance is important but secondary to correctness.

The baseline implementation may be slower than optimized pandas code if required for traceability.

Performance optimization is allowed only after equivalence is established.

Performance changes must not alter:

* outputs;
* schema;
* ordering;
* null behavior;
* warnings/errors;
* traceability.

***

## 28. Versioning Policy

The following must be versioned:

* migration constitution;
* parser;
* IR schema;
* Python generator;
* tool semantics library;
* formula function registry;
* test harness;
* comparison engine;
* generated workflow package.

Every certification report must include versions.

***

## 29. Reproducibility Requirements

A certified migration must be reproducible.

Given the same:

* source workflow;
* input data;
* tool semantics version;
* runtime version;
* configuration;
* golden comparison policy;

the migration should produce the same result.

If reproducibility is not possible due to non-determinism, the workflow must be classified accordingly.

***

## 30. Required Deliverables Per Workflow

Each migrated workflow package must contain:

```text
1. Original workflow reference
2. Source hash
3. Parsed IR
4. Baseline Python code
5. Node configuration files
6. Tool support report
7. Test suite
8. Golden-output comparison results
9. Certification report
10. Exception log
11. Known limitations
12. Optional optimized Python implementation
```

***

## 31. Minimal Certification Checklist

A workflow cannot be certified unless every item below is true:

```text
[ ] Source workflow parsed successfully
[ ] Canonical IR generated
[ ] All nodes represented
[ ] All edges represented
[ ] All anchors represented
[ ] All tool configs parsed
[ ] Unsupported tools classified
[ ] Baseline Python generated
[ ] Baseline uses canonical tool library
[ ] No unauthorized tool combination
[ ] Node-level traces produced
[ ] Schema comparison completed
[ ] Golden-output comparison completed
[ ] Differences documented
[ ] Exceptions approved
[ ] Certification report generated
```

***

## 32. AI Agent Compliance Checklist

Before returning any migrated code, the AI agent must include this checklist:

```text
AI Agent Compliance Checklist

[ ] I preserved one Python node per Alteryx tool.
[ ] I preserved all input and output anchors.
[ ] I preserved graph topology.
[ ] I did not combine tools in the baseline implementation.
[ ] I did not infer business intent.
[ ] I did not silently ignore unsupported behavior.
[ ] I used canonical tool implementations.
[ ] I preserved schema behavior.
[ ] I preserved row behavior.
[ ] I preserved column order.
[ ] I classified uncertain behavior.
[ ] I generated or referenced required tests.
[ ] I marked certification status accurately.
```

If any checkbox is false, the output must be marked:

```text
NOT CERTIFIED
```

***

## 33. Recommended Prompt Template for Migration Agents

Use the following as a reusable prompt header:

```text
You are an Alteryx-to-Python migration agent.

You must follow the Alteryx-to-Python Migration Constitution.

Your objective is to generate a faithful baseline Python DAG implementation that reproduces Alteryx semantics.

You must not optimize, simplify, combine, remove, or reinterpret Alteryx tools unless an approved exception exists.

You must preserve:
- every tool as a Python node;
- every edge;
- every anchor;
- every tool configuration;
- schema behavior;
- row behavior;
- column order;
- null behavior;
- type behavior;
- output behavior.

You must use the canonical tool semantics library.

If behavior is unsupported, ambiguous, or unknown, you must classify and escalate it. You must not guess.

Your output must include:
1. parsed node list;
2. parsed edge list;
3. unsupported items;
4. generated IR;
5. baseline Python DAG code;
6. required tests;
7. certification status;
8. compliance checklist.
```

***

## 34. Example “Do Not Deviate” Policy

The following policy should appear at the top of the actual project repository:

```text
This repository implements a faithful Alteryx-to-Python migration framework.

Generated Python must preserve Alteryx workflow semantics.

The baseline migration layer is not allowed to optimize across tool boundaries.
Every Alteryx tool must map to a corresponding Python node unless an approved exception exists.

Any unsupported, ambiguous, or unknown behavior must be escalated.
Approximate migration is not certification.

A workflow is certified only when tool-level, node-level, schema-level, and golden-output tests pass or when differences are explicitly approved.
```

***

## 35. Practical Implementation Roadmap

I recommend implementing this constitution in phases.

### Phase 1: Foundation

Build:

* IR schema;
* graph parser;
* node/edge validator;
* tool registry;
* runtime context;
* trace framework;
* comparison framework.

Focus on correctness infrastructure first.

***

### Phase 2: Core tools

Implement certified semantics for common tools:

```text
Input Data
Output Data
Select
Filter
Formula
Join
Union
Summarize
Sort
Unique
Sample
```

These likely cover a large share of straightforward workflows.

***

### Phase 3: Formula engine

Build controlled formula parsing and execution.

Do not rely on AI-only formula translation.

***

### Phase 4: Golden-output framework

Automate:

* running migrated Python;
* comparing against Alteryx output;
* producing certification reports;
* classifying differences.

***

### Phase 5: Workflow inventory and classification

Run all workflows through:

```text
Parse → IR → classify → support matrix → risk score
```

This lets you prioritize easy wins and identify workflows needing review.

***

### Phase 6: Optional optimization

Only after baseline certification, generate optimized implementations.

The optimized version must be compared against:

1. baseline Python;
2. Alteryx golden output.

***

## 36. Final Foundation Statement

The project must be governed by this principle:

```text
The generated Python is not a rewrite of the workflow.
It is an executable semantic reconstruction of the Alteryx graph.
```

AI may assist with migration, but AI must remain constrained by:

* canonical IR;
* tool semantics;
* graph preservation;
* test evidence;
* golden-output comparison;
* explicit escalation;
* approved exceptions.

If this constitution is followed, large-scale Alteryx-to-Python migration is achievable without speaking to every workflow owner. But the project must not assume every workflow can be safely migrated from structure alone. Instead, it should use structure-first automation plus evidence-based escalation.

This gives you the right operating model:

```text
Automate what is structurally provable.
Test what is semantically risky.
Escalate what requires business meaning.
Never guess.
```
